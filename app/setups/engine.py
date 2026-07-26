from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from sqlalchemy import select
from app.settings import get_settings

from app.telemetry.models import (ControlStateRecord, IndicatorSnapshotRecord,
                                  IndicatorAlertEventRecord, SetupRecord,
                                  SetupTransitionRecord)

ACTIVE_STATES = ("detected", "developing", "watch", "strong_watch", "eligible")
STATE_RANK = {"detected": 0, "developing": 1, "watch": 2, "strong_watch": 3, "eligible": 4}


class SetupLifecycleEngine:
    """Converts closed-candle snapshots into auditable research setups; never orders."""

    def __init__(self, session_factory, exchange: str, strategy_version: str, git_sha: str,
                 detection_min_score: int = 2, expiry_candles: int = 40):
        self.session_factory = session_factory
        self.exchange = exchange
        self.strategy_version = strategy_version
        self.git_sha = git_sha
        self.detection_min_score = detection_min_score
        self.expiry_candles = expiry_candles

    def process(self, snapshot: IndicatorSnapshotRecord) -> SetupRecord | None:
        with self.session_factory() as session:
            active = session.scalar(select(SetupRecord).where(
                SetupRecord.pair == snapshot.symbol,
                SetupRecord.timeframe == snapshot.timeframe,
                SetupRecord.direction == snapshot.direction,
                SetupRecord.state.in_(ACTIVE_STATES),
            ).order_by(SetupRecord.detected_at.desc()).limit(1))
            if active and active.components.get("last_candle_timestamp") == snapshot.candle_timestamp.isoformat():
                return active
            control_reason = self._control_reason(session)
            if control_reason:
                if active and active.state == "eligible":
                    self._transition(session, active, "strong_watch", snapshot,
                                     f"setup disarmed: {control_reason}")
                    active.components = self._evidence(snapshot, control_reason)
                    session.commit()
                return active
            if active and self._age_candles(active, snapshot) > self.expiry_candles:
                self._transition(session, active, "expired", snapshot,
                                 f"maximum age of {self.expiry_candles} candles exceeded")
                active = None
            if active and active.state in {"watch", "strong_watch", "eligible"} and snapshot.score == 0:
                self._transition(session, active, "invalidated", snapshot,
                                 "all six current components became false")
                session.commit()
                return active
            meaningful = self._meaningful(snapshot)
            if active is None and not meaningful:
                session.commit()
                return None
            if active is None:
                setup_id = self._setup_id(snapshot)
                existing = session.get(SetupRecord, setup_id)
                if existing:
                    return existing
                state, gate_reason = self._target_state(session, snapshot.score)
                initial_state = "detected" if state == "developing" else state
                active = SetupRecord(
                    id=setup_id, pair=snapshot.symbol, timeframe=snapshot.timeframe,
                    direction=snapshot.direction, state=initial_state,
                    highest_state_reached=initial_state,
                    components=self._evidence(snapshot, gate_reason),
                    detected_at=snapshot.candle_timestamp,
                    strategy_version=self.strategy_version, config_hash=get_settings().config_hash,
                    git_sha=self.git_sha,
                )
                session.add(active)
                session.flush()
                session.add(SetupTransitionRecord(
                    setup_id=active.id, from_state="none", to_state=initial_state,
                    occurred_at=snapshot.candle_timestamp,
                    reason=self._creation_reason(snapshot, gate_reason),
                ))
                self._setup_event(session, active, snapshot, "none", initial_state,
                                  self._creation_reason(snapshot, gate_reason))
            else:
                target, gate_reason = self._target_state(session, snapshot.score)
                active.components = self._evidence(snapshot, gate_reason)
                is_downgrade = STATE_RANK[target] < STATE_RANK.get(active.state, -1)
                if target != active.state and (meaningful or is_downgrade):
                    self._transition(session, active, target, snapshot,
                                     self._transition_reason(snapshot, target, gate_reason))
            session.commit()
            return active

    def _meaningful(self, snapshot: IndicatorSnapshotRecord) -> bool:
        components = snapshot.components
        contextual = ("liquidity_sweep", "fvg_retest", "retest_confirmation", "structure")
        return snapshot.score >= self.detection_min_score or any(
            components.get(name, {}).get("passed", False) for name in contextual)

    @staticmethod
    def _target_state(session, score: int) -> tuple[str, str | None]:
        if score >= 6:
            kill = session.get(ControlStateRecord, "kill_switch")
            pause = session.get(ControlStateRecord, "paused")
            if kill and kill.enabled:
                return "strong_watch", "kill switch blocks eligibility"
            if pause and pause.enabled:
                return "strong_watch", "global pause blocks eligibility"
            return "eligible", None
        if score >= 5:
            return "strong_watch", None
        if score >= 4:
            return "watch", None
        return "developing", None

    @staticmethod
    def _control_reason(session) -> str | None:
        kill = session.get(ControlStateRecord, "kill_switch")
        pause = session.get(ControlStateRecord, "paused")
        if kill and kill.enabled:
            return "kill switch blocks setup processing"
        if pause and pause.enabled:
            return "global pause blocks setup processing"
        return None

    @staticmethod
    def _evidence(snapshot: IndicatorSnapshotRecord, gate_reason: str | None) -> dict:
        return {
            "score": snapshot.score,
            "setup_state_from_score": snapshot.setup_state,
            "components": snapshot.components,
            "last_candle_timestamp": snapshot.candle_timestamp.isoformat(),
            "last_evaluated_at": snapshot.evaluated_at.isoformat(),
            "eligibility_gate": gate_reason,
            "execution_connected": False,
        }

    @staticmethod
    def _age_candles(setup: SetupRecord, snapshot: IndicatorSnapshotRecord) -> int:
        unit, amount = setup.timeframe[-1], int(setup.timeframe[:-1])
        seconds = amount * {"m": 60, "h": 3600, "d": 86400}.get(unit, 60)
        detected = setup.detected_at if setup.detected_at.tzinfo else setup.detected_at.replace(tzinfo=timezone.utc)
        return int((snapshot.candle_timestamp - detected).total_seconds() // seconds)

    @staticmethod
    def _setup_id(snapshot: IndicatorSnapshotRecord) -> str:
        raw = (f"{snapshot.exchange}|{snapshot.symbol}|{snapshot.timeframe}|"
               f"{snapshot.direction}|{snapshot.candle_timestamp.isoformat()}")
        return "stp_" + hashlib.sha256(raw.encode()).hexdigest()[:20]

    def _transition(self, session, setup: SetupRecord, target: str,
                    snapshot: IndicatorSnapshotRecord, reason: str) -> None:
        previous = setup.state
        setup.state = target
        if STATE_RANK.get(target, -1) > STATE_RANK.get(setup.highest_state_reached, -1):
            setup.highest_state_reached = target
        session.add(SetupTransitionRecord(setup_id=setup.id, from_state=previous,
                                          to_state=target, occurred_at=snapshot.candle_timestamp,
                                          reason=reason))
        self._setup_event(session, setup, snapshot, previous, target, reason)

    def _setup_event(self, session, setup: SetupRecord, snapshot: IndicatorSnapshotRecord,
                     previous: str, target: str, reason: str) -> None:
        event_id = f"setup:{setup.id}:{snapshot.candle_timestamp.isoformat()}:{target}"
        alert_score = max(snapshot.score, int((setup.components or {}).get("score", 0)))
        session.add(IndicatorAlertEventRecord(
            event_id=event_id, exchange=self.exchange, symbol=setup.pair,
            timeframe=setup.timeframe, candle_timestamp=snapshot.candle_timestamp,
            direction=setup.direction, event_type="setup_transition", component="setup_state",
            old_value=previous, new_value=target, score=alert_score,
            message=(f"{setup.pair} {setup.direction}: setup {setup.id} "
                     f"{previous} → {target}; {reason}"),
            created_at=datetime.now(timezone.utc), delivered_at=None,
        ))

    @staticmethod
    def _creation_reason(snapshot: IndicatorSnapshotRecord, gate_reason: str | None) -> str:
        passed = [name for name, value in snapshot.components.items() if value.get("passed")]
        reason = f"meaningful evidence detected at score {snapshot.score}/6: {', '.join(passed) or 'context trigger'}"
        return reason + (f"; {gate_reason}" if gate_reason else "")

    @staticmethod
    def _transition_reason(snapshot: IndicatorSnapshotRecord, target: str,
                           gate_reason: str | None) -> str:
        passed = [name for name, value in snapshot.components.items() if value.get("passed")]
        reason = f"score {snapshot.score}/6 reached {target}; passing: {', '.join(passed) or 'none'}"
        return reason + (f"; {gate_reason}" if gate_reason else "")
