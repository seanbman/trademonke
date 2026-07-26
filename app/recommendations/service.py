from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from app.settings import get_settings

from app.telemetry.models import (ImbalanceRecord, LiquidityLevelRecord,
                                  RecommendationEventRecord, RecommendationRecord,
                                  RiskEvaluationRecord, StrategyEpisodeRecord, TradePlanRecord)


class RecommendationService:
    def __init__(self, session_factory, strategy_version: str, git_sha: str,
                 validity_candles: int = 12):
        self.session_factory = session_factory
        self.strategy_version = strategy_version
        self.git_sha = git_sha
        self.validity_candles = validity_candles

    def create_for_approved_episode(self, episode_id: str) -> RecommendationRecord:
        with self.session_factory() as session:
            episode = session.get(StrategyEpisodeRecord, episode_id)
            if episode is None or episode.current_state != "approved":
                raise ValueError("episode must be risk-approved")
            risk = session.scalar(select(RiskEvaluationRecord).where(
                RiskEvaluationRecord.episode_id == episode.id,
                RiskEvaluationRecord.decision == "approved"
            ).order_by(RiskEvaluationRecord.evaluated_at.desc()).limit(1))
            if risk is None:
                raise ValueError("approved risk evaluation is required")
            existing = session.scalar(select(RecommendationRecord).where(
                RecommendationRecord.episode_id == episode.id,
                RecommendationRecord.recommendation_type == "trade_plan",
                RecommendationRecord.status == "valid").order_by(
                    RecommendationRecord.version.desc()).limit(1))
            version = (existing.version + 1) if existing else 1
            entry = Decimal(risk.inputs["entry"])
            stop = Decimal(risk.inputs["stop"])
            primary_target = Decimal(risk.inputs["target"])
            gap = session.scalar(select(ImbalanceRecord).where(
                ImbalanceRecord.episode_id == episode.id).order_by(
                    ImbalanceRecord.created_at.desc()).limit(1))
            if gap is None:
                raise ValueError("linked imbalance is required")
            targets = self._targets(session, episode, entry, stop, primary_target)
            now = datetime.now(timezone.utc)
            valid_until = now + timedelta(seconds=self._timeframe_seconds(
                episode.timeframe) * self.validity_candles)
            recommendation_id = f"rec_{hashlib.sha256(f'{episode.id}|{version}|{risk.id}'.encode()).hexdigest()[:20]}"
            geometry = {
                "entry_region": {"lower": str(gap.lower_price), "upper": str(gap.upper_price),
                                 "model": "linked_fvg_retest"},
                "initial_stop": {"price": str(stop), "model": "structural_invalidation"},
                "profit_boxes": targets,
                "breakeven_trigger": {"after": "tp1", "price": str(entry)},
                "trailing_stop": {"activation": "after_tp1", "model": "confirmed_structure",
                                  "may_move_away_from_safety": False},
                "position_size": risk.size_calculation,
                "risk_evaluation_id": risk.id,
            }
            if existing:
                existing.status = "superseded"
                self._event(session, existing, "superseded", "valid", "superseded", now,
                            ["newer_version_created"])
            recommendation = RecommendationRecord(
                id=recommendation_id, episode_id=episode.id, setup_id=None,
                recommendation_type="trade_plan", version=version, status="valid",
                geometry=geometry, source_rules=["linked_fvg_retest", "structural_invalidation",
                                                "opposing_liquidity_targets", "risk_approved_size"],
                source_object_ids=[episode.liquidity_level_id, gap.id, risk.id],
                valid_from=now, valid_until=valid_until,
                supersedes_id=existing.id if existing else None, created_at=now,
                strategy_version=self.strategy_version, config_hash=get_settings().config_hash, git_sha=self.git_sha)
            session.add(recommendation)
            session.flush()
            self._event(session, recommendation, "created", None, "valid", now,
                        ["risk_approved_geometry"])
            plan = TradePlanRecord(
                id=f"plan_{recommendation_id[4:]}", recommendation_id=recommendation.id,
                risk_evaluation_id=risk.id, version=version, status="research_approved",
                entry_geometry=geometry["entry_region"], targets=targets,
                initial_stop=geometry["initial_stop"], trailing_policy=geometry["trailing_stop"],
                position_size=risk.size_calculation,
                validity={"valid_from": now.isoformat(), "valid_until": valid_until.isoformat(),
                          "execution_connected": False}, created_at=now,
                strategy_version=self.strategy_version, config_hash=get_settings().config_hash, git_sha=self.git_sha)
            session.add(plan)
            session.commit()
            return recommendation

    def _targets(self, session, episode, entry, stop, primary_target):
        side = "short" if episode.direction == "long" else "long"
        candidates = list(session.scalars(select(LiquidityLevelRecord).where(
            LiquidityLevelRecord.exchange == episode.exchange,
            LiquidityLevelRecord.symbol == episode.symbol,
            LiquidityLevelRecord.timeframe == episode.timeframe,
            LiquidityLevelRecord.direction == side,
            LiquidityLevelRecord.status.in_(["active", "swept"]))))
        prices = ([item.price for item in candidates if item.price > entry]
                  if episode.direction == "long" else
                  [item.price for item in candidates if item.price < entry])
        prices.append(primary_target)
        risk = abs(entry - stop)
        minimum_rr = get_settings().minimum_risk_reward
        prices = [price for price in sorted(set(prices), reverse=episode.direction == "short")
                  if risk > 0 and abs(price - entry) / risk >= minimum_rr][:3]
        return [{"label": f"tp{index}", "price": str(price),
                 "r_multiple": str(abs(price - entry) / risk), "source": "opposing_liquidity"}
                for index, price in enumerate(prices, start=1)]

    def _event(self, session, recommendation, event_type, prior, current, timestamp, reasons):
        session.add(RecommendationEventRecord(
            event_id=f"recommendation:{recommendation.id}:{timestamp.isoformat()}:{event_type}",
            recommendation_id=recommendation.id, event_type=event_type, occurred_at=timestamp,
            prior_status=prior, current_status=current, reason_codes=reasons,
            geometry_snapshot=recommendation.geometry, actor_id=None,
            strategy_version=self.strategy_version, config_hash=get_settings().config_hash, git_sha=self.git_sha))

    @staticmethod
    def _timeframe_seconds(timeframe):
        amount, unit = int(timeframe[:-1]), timeframe[-1]
        return amount * {"m": 60, "h": 3600, "d": 86400}[unit]
