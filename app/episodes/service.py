from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select

from app.domain.episodes import (EpisodeState, TERMINAL_EPISODE_STATES,
                                 classify_displacement, classify_recovery, zone_retested)
from app.domain.models import Candle, Direction
from app.domain.signals import detect_fvgs
from app.settings import get_settings
from app.telemetry.models import (CandleRecord, EpisodeEventRecord, ImbalanceRecord,
                                  LiquidityLevelEventRecord, LiquidityLevelRecord,
                                  StrategyEpisodeRecord)


PROGRESS_RANK = {state.value: index for index, state in enumerate((
    EpisodeState.OBSERVED, EpisodeState.SWEPT, EpisodeState.RECLAIMED,
    EpisodeState.DISPLACED, EpisodeState.IMBALANCE_CREATED, EpisodeState.RETESTED,
    EpisodeState.ARMED, EpisodeState.APPROVED))}


class EpisodeEngine:
    def __init__(self, session_factory, exchange: str, strategy_version: str, git_sha: str,
                 minimum_displacement_body_bps: Decimal = Decimal("20")):
        self.session_factory = session_factory
        self.exchange = exchange
        self.strategy_version = strategy_version
        self.git_sha = git_sha
        self.minimum_displacement_body_bps = minimum_displacement_body_bps

    def update(self, symbol: str, timeframe: str) -> int:
        with self.session_factory() as session:
            candle_rows = list(session.scalars(select(CandleRecord).where(
                CandleRecord.exchange == self.exchange, CandleRecord.symbol == symbol,
                CandleRecord.timeframe == timeframe, CandleRecord.closed.is_(True)
            ).order_by(CandleRecord.timestamp.desc()).limit(100)))
            candle_rows.reverse()
            if not candle_rows:
                return 0
            candles = [self._candle(row) for row in candle_rows]
            changes = self._create_swept_episodes(session, symbol, timeframe)
            episodes = list(session.scalars(select(StrategyEpisodeRecord).where(
                StrategyEpisodeRecord.exchange == self.exchange,
                StrategyEpisodeRecord.symbol == symbol,
                StrategyEpisodeRecord.timeframe == timeframe,
                StrategyEpisodeRecord.terminal_reason.is_(None))))
            for episode in episodes:
                changes += self._advance(session, episode, candles)
            session.commit()
            return changes

    def _create_swept_episodes(self, session, symbol, timeframe) -> int:
        events = list(session.scalars(select(LiquidityLevelEventRecord).join(
            LiquidityLevelRecord,
            LiquidityLevelRecord.id == LiquidityLevelEventRecord.liquidity_level_id).where(
                LiquidityLevelRecord.exchange == self.exchange,
                LiquidityLevelRecord.symbol == symbol,
                LiquidityLevelRecord.timeframe == timeframe,
                LiquidityLevelEventRecord.event_type == "level_swept")))
        changes = 0
        for event in events:
            episode_id = "ep_" + hashlib.sha256(event.event_id.encode()).hexdigest()[:20]
            if session.get(StrategyEpisodeRecord, episode_id):
                continue
            level = session.get(LiquidityLevelRecord, event.liquidity_level_id)
            episode = StrategyEpisodeRecord(
                id=episode_id, liquidity_level_id=level.id, exchange=self.exchange,
                symbol=symbol, timeframe=timeframe, direction=level.direction,
                current_state=EpisodeState.SWEPT.value,
                highest_state_reached=EpisodeState.SWEPT.value,
                started_at=event.candle_timestamp, updated_at=event.candle_timestamp,
                terminal_reason=None,
                current_gate_snapshot={"last_candle_timestamp": event.candle_timestamp.isoformat()},
                strategy_version=self.strategy_version, config_hash=get_settings().config_hash, git_sha=self.git_sha)
            session.add(episode)
            session.flush()
            self._event(session, episode, None, EpisodeState.SWEPT, event.candle_timestamp,
                        ["linked_level_sweep"], event.measurements)
            changes += 1
        return changes

    def _advance(self, session, episode, candles: list[Candle]) -> int:
        last_raw = episode.current_gate_snapshot.get("last_candle_timestamp")
        last = datetime.fromisoformat(last_raw) if last_raw else episode.started_at
        last = self._aware(last)
        new_candles = [candle for candle in candles if candle.timestamp > last]
        changes = 0
        for candle in new_candles:
            state = EpisodeState(episode.current_state)
            if state in TERMINAL_EPISODE_STATES:
                break
            level = session.get(LiquidityLevelRecord, episode.liquidity_level_id)
            direction = Direction(episode.direction)
            decision = None
            if state is EpisodeState.SWEPT:
                decision = classify_recovery(direction, level.price, candle)
            elif state is EpisodeState.RECLAIMED:
                decision = classify_displacement(direction, candle,
                                                 self.minimum_displacement_body_bps)
            elif state is EpisodeState.DISPLACED:
                gap = self._new_gap(session, candles, candle, episode)
                if gap:
                    session.add(gap)
                    decision = self._decision(EpisodeState.IMBALANCE_CREATED,
                                              "linked_directional_fvg", {"imbalance_id": gap.id})
            elif state is EpisodeState.IMBALANCE_CREATED:
                gap = session.scalar(select(ImbalanceRecord).where(
                    ImbalanceRecord.episode_id == episode.id,
                    ImbalanceRecord.status == "active").order_by(ImbalanceRecord.created_at.desc()))
                if gap and candle.timestamp > self._aware(gap.created_at) and zone_retested(
                        direction, gap.lower_price, gap.upper_price, candle):
                    gap.status, gap.updated_at = "retested", candle.timestamp
                    decision = self._decision(EpisodeState.RETESTED, "linked_zone_retested",
                                              {"imbalance_id": gap.id})
            snapshot = dict(episode.current_gate_snapshot)
            snapshot["last_candle_timestamp"] = candle.timestamp.isoformat()
            episode.current_gate_snapshot = snapshot
            if decision:
                previous = EpisodeState(episode.current_state)
                episode.current_state = decision.next_state.value
                if decision.next_state is EpisodeState.DISPLACED:
                    snapshot["displaced_at"] = candle.timestamp.isoformat()
                    episode.current_gate_snapshot = snapshot
                episode.updated_at = candle.timestamp
                if PROGRESS_RANK.get(decision.next_state.value, -1) > PROGRESS_RANK.get(
                        episode.highest_state_reached, -1):
                    episode.highest_state_reached = decision.next_state.value
                if decision.next_state in TERMINAL_EPISODE_STATES:
                    episode.terminal_reason = decision.reason_codes[0]
                self._event(session, episode, previous, decision.next_state, candle.timestamp,
                            list(decision.reason_codes), decision.measurements)
                changes += 1
        return changes

    def _new_gap(self, session, candles, current, episode):
        available = [item for item in candles if item.timestamp <= current.timestamp]
        displaced_at = self._aware(datetime.fromisoformat(
            episode.current_gate_snapshot["displaced_at"]))
        gaps = [gap for gap in detect_fvgs(available[-4:], episode.symbol, episode.timeframe)
                if gap.direction.value == episode.direction
                and gap.creation_timestamp >= displaced_at]
        if not gaps:
            return None
        gap = gaps[-1]
        gap_id = f"imb_{gap.id}"
        if session.get(ImbalanceRecord, gap_id):
            return None
        return ImbalanceRecord(
            id=gap_id, episode_id=episode.id, exchange=self.exchange, symbol=episode.symbol,
            timeframe=episode.timeframe, direction=episode.direction, imbalance_type="fvg",
            lower_price=gap.lower, upper_price=gap.upper, status="active",
            created_at=gap.creation_timestamp, updated_at=gap.creation_timestamp,
            measurements={"origin": "post_displacement"}, strategy_version=self.strategy_version,
            config_hash=get_settings().config_hash, git_sha=self.git_sha)

    def _event(self, session, episode, previous, current, timestamp, reasons, measurements):
        event_id = f"episode:{episode.id}:{timestamp.isoformat()}:{current.value}"
        if session.scalar(select(EpisodeEventRecord.id).where(EpisodeEventRecord.event_id == event_id)):
            return
        session.add(EpisodeEventRecord(
            event_id=event_id, episode_id=episode.id, event_type="state_changed",
            prior_state=previous.value if previous else None, current_state=current.value,
            occurred_at=timestamp, candle_timestamp=timestamp, reason_codes=reasons,
            measurements=measurements, strategy_version=self.strategy_version,
            config_hash=get_settings().config_hash, git_sha=self.git_sha))

    @staticmethod
    def _decision(state, reason, measurements):
        from app.domain.episodes import EpisodeDecision
        return EpisodeDecision(state, (reason,), measurements)

    @staticmethod
    def _aware(value):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

    @classmethod
    def _candle(cls, row):
        return Candle(cls._aware(row.timestamp), row.open, row.high, row.low, row.close, row.volume)
