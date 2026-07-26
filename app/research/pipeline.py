from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select

from app.domain.risk import RiskLimits
from app.qualification.service import MANDATORY_GATES, QualificationService
from app.recommendations.service import RecommendationService
from app.settings import Settings
from app.telemetry.models import (CandidateEvidenceRecord, CandleRecord, ControlStateRecord,
                                  FeatureSnapshotRecord, ImbalanceRecord, LiquidityLevelRecord,
                                  OutcomeLabelRecord, RecommendationRecord, StrategyEpisodeRecord,
                                  TradePlanRecord)


class ResearchPipeline:
    """Orchestrates research decisions only; it never calls an execution adapter."""

    def __init__(self, session_factory, settings: Settings):
        self.session_factory = session_factory
        self.settings = settings
        self.qualification = QualificationService(
            session_factory, settings.strategy_version, settings.git_sha)
        self.recommendations = RecommendationService(
            session_factory, settings.strategy_version, settings.git_sha)

    def update(self, symbol: str, timeframe: str) -> int:
        changes = 0
        with self.session_factory() as session:
            latest_candle = session.scalar(select(CandleRecord).where(
                CandleRecord.exchange == self.settings.market_data_exchange,
                CandleRecord.symbol == symbol, CandleRecord.timeframe == timeframe,
                CandleRecord.closed.is_(True)).order_by(CandleRecord.timestamp.desc()).limit(1))
            if latest_candle is None:
                return 0
            episodes = list(session.scalars(select(StrategyEpisodeRecord).where(
                StrategyEpisodeRecord.exchange == self.settings.market_data_exchange,
                StrategyEpisodeRecord.symbol == symbol,
                StrategyEpisodeRecord.timeframe == timeframe,
                StrategyEpisodeRecord.current_state == "retested")))
            episode_ids = [episode.id for episode in episodes]
        for episode_id in episode_ids:
            if self._qualify_and_plan(episode_id, latest_candle.timestamp):
                changes += 1
        changes += self._label_open_plans(symbol, timeframe)
        return changes

    def _qualify_and_plan(self, episode_id: str, candle_timestamp: datetime) -> bool:
        with self.session_factory() as session:
            existing = session.scalar(select(FeatureSnapshotRecord.id).where(
                FeatureSnapshotRecord.episode_id == episode_id,
                FeatureSnapshotRecord.candle_timestamp == candle_timestamp))
            if existing:
                return False
            episode = session.get(StrategyEpisodeRecord, episode_id)
            gap = session.scalar(select(ImbalanceRecord).where(
                ImbalanceRecord.episode_id == episode_id,
                ImbalanceRecord.status == "retested").order_by(ImbalanceRecord.created_at.desc()))
            origin = session.get(LiquidityLevelRecord, episode.liquidity_level_id)
            target = self._target(session, episode, gap)
            candidate = session.scalar(select(CandidateEvidenceRecord).where(
                CandidateEvidenceRecord.exchange == episode.exchange,
                CandidateEvidenceRecord.symbol == episode.symbol).order_by(
                    CandidateEvidenceRecord.observed_at.desc()).limit(1))
            controls_clear = not any(bool(record and record.enabled) for record in (
                session.get(ControlStateRecord, "paused"),
                session.get(ControlStateRecord, "kill_switch")))
            candidate_fresh = bool(candidate and self._aware(candidate.observed_at) >=
                                   self._aware(candle_timestamp) - timedelta(hours=1))
            spread_ok = bool(candidate_fresh and candidate.spread_bps is not None and
                             candidate.spread_bps <= Decimal(str(self.settings.candidate_max_spread_bps)))
            entry = (gap.lower_price + gap.upper_price) / 2 if gap else None
            stop = None
            if gap:
                stop = (gap.lower_price - self.settings.research_tick_size
                        if episode.direction == "long" else
                        gap.upper_price + self.settings.research_tick_size)
            geometry_ok = bool(entry is not None and stop is not None and target is not None and
                               self._rr(episode.direction, entry, stop, target) >=
                               self.settings.minimum_risk_reward)
            features = {
                "liquidity_event": origin is not None and origin.status == "swept",
                "recovery_displacement": episode.highest_state_reached in {
                    "displaced", "imbalance_created", "retested", "armed", "approved"},
                "linked_imbalance": gap is not None,
                "entry_condition": episode.current_state == "retested",
                "invalidation_target": geometry_ok,
                "execution_quality": spread_ok and controls_clear,
            }
            session.add(FeatureSnapshotRecord(
                episode_id=episode_id, setup_id=None, candle_timestamp=candle_timestamp,
                features=features,
                thresholds={"minimum_rr": str(self.settings.minimum_risk_reward),
                            "maximum_spread_bps": str(self.settings.candidate_max_spread_bps)},
                data_quality={"candidate_fresh": candidate_fresh,
                              "spread_available": bool(candidate and candidate.spread_bps is not None)},
                calculation_versions={"qualification": "mandatory-gates.v1"},
                strategy_version=self.settings.strategy_version,
                config_hash=self.settings.config_hash, git_sha=self.settings.git_sha))
            session.commit()
        gates = {name: {"passed": features[name], "data_quality": "ok" if features[name] else "missing",
                        "reason_codes": [f"{name}_{'passed' if features[name] else 'failed'}"]}
                 for name in MANDATORY_GATES}
        if not self.qualification.evaluate_gates(episode_id, gates):
            return False
        limits = RiskLimits(
            account_risk_fraction=self.settings.risk_fraction,
            minimum_risk_reward=self.settings.minimum_risk_reward,
            maximum_spread_bps=Decimal(str(self.settings.candidate_max_spread_bps)),
            maximum_slippage_bps=self.settings.research_slippage_bps,
            maximum_notional=self.settings.maximum_notional,
            minimum_notional=self.settings.minimum_notional)
        risk = self.qualification.evaluate_risk(
            episode_id, entry=entry, stop=stop, target=target,
            account_balance=self.settings.research_account_balance,
            spread_bps=Decimal(str(candidate.spread_bps)),
            slippage_bps=self.settings.research_slippage_bps,
            limits=limits, controls_clear=controls_clear)
        if risk.decision == "approved":
            self.recommendations.create_for_approved_episode(episode_id)
            return True
        return False

    def _label_open_plans(self, symbol: str, timeframe: str) -> int:
        changes = 0
        with self.session_factory() as session:
            plans = list(session.scalars(select(TradePlanRecord).join(
                RecommendationRecord, RecommendationRecord.id == TradePlanRecord.recommendation_id
            ).join(StrategyEpisodeRecord, StrategyEpisodeRecord.id == RecommendationRecord.episode_id).where(
                StrategyEpisodeRecord.symbol == symbol,
                StrategyEpisodeRecord.timeframe == timeframe)))
            for plan in plans:
                recommendation = session.get(RecommendationRecord, plan.recommendation_id)
                if session.scalar(select(OutcomeLabelRecord.id).where(
                        OutcomeLabelRecord.trade_plan_id == plan.id)):
                    continue
                episode = session.get(StrategyEpisodeRecord, recommendation.episode_id)
                candles = list(session.scalars(select(CandleRecord).where(
                    CandleRecord.exchange == episode.exchange, CandleRecord.symbol == symbol,
                    CandleRecord.timeframe == timeframe,
                    CandleRecord.timestamp > plan.created_at).order_by(CandleRecord.timestamp)))
                outcome = self._outcome(episode.direction, plan, candles)
                if outcome:
                    session.add(OutcomeLabelRecord(
                        episode_id=episode.id, trade_plan_id=plan.id,
                        labelled_at=outcome["timestamp"], label=outcome["label"],
                        target_stop_ordering=outcome["ordering"], mae=outcome["mae"],
                        mfe=outcome["mfe"], duration_seconds=outcome["duration_seconds"],
                        path_metrics={"candles": outcome["candles"]},
                        strategy_version=self.settings.strategy_version,
                        config_hash=self.settings.config_hash, git_sha=self.settings.git_sha))
                    changes += 1
            session.commit()
        return changes

    @staticmethod
    def _outcome(direction, plan, candles):
        if not candles:
            return None
        entry = Decimal(plan.entry_geometry.get("upper") if direction == "long" else
                        plan.entry_geometry.get("lower"))
        stop = Decimal(plan.initial_stop["price"])
        target = Decimal(plan.targets[0]["price"])
        mae = mfe = Decimal("0")
        for index, candle in enumerate(candles, start=1):
            adverse = entry - candle.low if direction == "long" else candle.high - entry
            favorable = candle.high - entry if direction == "long" else entry - candle.low
            mae, mfe = max(mae, adverse), max(mfe, favorable)
            stop_hit = candle.low <= stop if direction == "long" else candle.high >= stop
            target_hit = candle.high >= target if direction == "long" else candle.low <= target
            if stop_hit or target_hit:
                # Same-candle ambiguity fails conservatively to stop-first.
                ordering = "stop_first" if stop_hit else "target_first"
                return {"timestamp": candle.timestamp, "label": ordering,
                        "ordering": ordering, "mae": mae, "mfe": mfe,
                        "duration_seconds": int((candle.timestamp - candles[0].timestamp).total_seconds()),
                        "candles": index}
        return None

    @staticmethod
    def _target(session, episode, gap):
        if gap is None:
            return None
        entry = (gap.lower_price + gap.upper_price) / 2
        opposing = "short" if episode.direction == "long" else "long"
        levels = list(session.scalars(select(LiquidityLevelRecord).where(
            LiquidityLevelRecord.exchange == episode.exchange,
            LiquidityLevelRecord.symbol == episode.symbol,
            LiquidityLevelRecord.timeframe == episode.timeframe,
            LiquidityLevelRecord.direction == opposing,
            LiquidityLevelRecord.status.in_(["active", "swept"]))))
        prices = [level.price for level in levels if
                  (level.price > entry if episode.direction == "long" else level.price < entry)]
        return (min(prices) if episode.direction == "long" else max(prices)) if prices else None

    @staticmethod
    def _rr(direction, entry, stop, target):
        risk = entry - stop if direction == "long" else stop - entry
        reward = target - entry if direction == "long" else entry - target
        return reward / risk if risk > 0 and reward > 0 else Decimal("0")

    @staticmethod
    def _aware(value):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
