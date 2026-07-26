from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from app.domain.models import Direction
from app.domain.risk import RiskLimits, evaluate_risk
from app.settings import get_settings
from app.telemetry.models import (EpisodeEventRecord, GateEvaluationRecord,
                                  RiskEvaluationRecord, StrategyEpisodeRecord)


MANDATORY_GATES = (
    "liquidity_event", "recovery_displacement", "linked_imbalance",
    "entry_condition", "invalidation_target", "execution_quality",
)


class QualificationService:
    def __init__(self, session_factory, strategy_version: str, git_sha: str):
        self.session_factory = session_factory
        self.strategy_version = strategy_version
        self.git_sha = git_sha

    def evaluate_gates(self, episode_id: str, gates: dict[str, dict]) -> bool:
        with self.session_factory() as session:
            episode = session.get(StrategyEpisodeRecord, episode_id)
            if episode is None:
                raise ValueError("episode not found")
            now = datetime.now(timezone.utc)
            passed_all = True
            snapshot = {}
            for name in MANDATORY_GATES:
                evidence = gates.get(name, {})
                passed = bool(evidence.get("passed", False)) and evidence.get("data_quality", "ok") == "ok"
                reasons = list(evidence.get("reason_codes", []))
                if not passed and not reasons:
                    reasons = ["missing_or_failed_mandatory_gate"]
                passed_all &= passed
                snapshot[name] = {"passed": passed, "reason_codes": reasons,
                                  "data_quality": evidence.get("data_quality", "missing")}
                session.add(GateEvaluationRecord(
                    episode_id=episode.id, setup_id=None, evaluated_at=now, gate_name=name,
                    mandatory=True, passed=passed, reason_codes=reasons,
                    inputs=evidence.get("inputs", {}), thresholds=evidence.get("thresholds", {}),
                    data_quality={"status": evidence.get("data_quality", "missing")},
                    strategy_version=self.strategy_version, config_hash=get_settings().config_hash, git_sha=self.git_sha))
            previous = episode.current_state
            if passed_all and previous == "retested":
                episode.current_state = "armed"
                episode.highest_state_reached = "armed"
                self._event(session, episode, previous, "armed", now, ["all_mandatory_gates_passed"])
            elif not passed_all and previous == "armed":
                episode.current_state = "retested"
                self._event(session, episode, previous, "retested", now, ["mandatory_gate_failed", "disarmed"])
            episode.updated_at = now
            current_snapshot = dict(episode.current_gate_snapshot or {})
            current_snapshot["mandatory_gates"] = snapshot
            episode.current_gate_snapshot = current_snapshot
            session.commit()
            return passed_all

    def evaluate_risk(self, episode_id: str, *, entry: Decimal, stop: Decimal,
                      target: Decimal, account_balance: Decimal, spread_bps: Decimal,
                      slippage_bps: Decimal, limits: RiskLimits,
                      controls_clear: bool) -> RiskEvaluationRecord:
        with self.session_factory() as session:
            episode = session.get(StrategyEpisodeRecord, episode_id)
            if episode is None or episode.current_state != "armed":
                raise ValueError("episode must be armed before risk evaluation")
            decision = evaluate_risk(Direction(episode.direction), entry, stop, target,
                                     account_balance, spread_bps, slippage_bps, limits,
                                     controls_clear)
            now = datetime.now(timezone.utc)
            record = RiskEvaluationRecord(
                episode_id=episode.id, setup_id=None, evaluated_at=now,
                decision="approved" if decision.approved else "rejected",
                reason_codes=list(decision.reason_codes),
                inputs={"entry": str(entry), "stop": str(stop), "target": str(target),
                        "account_balance": str(account_balance), "spread_bps": str(spread_bps),
                        "slippage_bps": str(slippage_bps)},
                limits_snapshot={key: str(value) for key, value in limits.__dict__.items()},
                size_calculation={"quantity": str(decision.quantity),
                                  "notional": str(decision.notional),
                                  "risk_amount": str(decision.risk_amount)},
                strategy_version=self.strategy_version, config_hash=get_settings().config_hash, git_sha=self.git_sha)
            session.add(record)
            if decision.approved:
                episode.current_state = episode.highest_state_reached = "approved"
                episode.updated_at = now
                self._event(session, episode, "armed", "approved", now, ["risk_approved"])
            session.commit()
            return record

    def _event(self, session, episode, previous, current, timestamp, reasons):
        session.add(EpisodeEventRecord(
            event_id=f"episode:{episode.id}:{timestamp.isoformat()}:{current}",
            episode_id=episode.id, event_type="state_changed", prior_state=previous,
            current_state=current, occurred_at=timestamp, candle_timestamp=timestamp,
            reason_codes=reasons, measurements={}, strategy_version=self.strategy_version,
            config_hash=get_settings().config_hash, git_sha=self.git_sha))
