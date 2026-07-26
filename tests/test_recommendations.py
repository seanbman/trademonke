from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import sessionmaker

from app.recommendations.service import RecommendationService
from app.telemetry.db import Base, build_engine
from app.telemetry.models import (ImbalanceRecord, LiquidityLevelRecord,
                                  RecommendationEventRecord, RecommendationRecord,
                                  RiskEvaluationRecord, StrategyEpisodeRecord, TradePlanRecord)


def test_approved_episode_creates_versioned_nonexecuting_geometry_and_supersedes():
    engine = build_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    now = datetime.now(timezone.utc)
    provenance = {"strategy_version": "v1", "config_hash": "cfg", "git_sha": "sha"}
    with Session() as session:
        origin = LiquidityLevelRecord(
            id="origin", exchange="kraken", symbol="BTC/USDT", timeframe="5m",
            direction="long", level_type="swing_low", price=Decimal("98"), status="swept",
            observed_at=now, updated_at=now, measurements={}, **provenance)
        target1 = LiquidityLevelRecord(
            id="target1", exchange="kraken", symbol="BTC/USDT", timeframe="5m",
            direction="short", level_type="swing_high", price=Decimal("106"), status="active",
            observed_at=now, updated_at=now, measurements={}, **provenance)
        target2 = LiquidityLevelRecord(
            id="target2", exchange="kraken", symbol="BTC/USDT", timeframe="5m",
            direction="short", level_type="swing_high", price=Decimal("110"), status="active",
            observed_at=now, updated_at=now, measurements={}, **provenance)
        session.add_all([origin, target1, target2])
        session.flush()
        session.add(StrategyEpisodeRecord(
            id="ep", liquidity_level_id="origin", exchange="kraken", symbol="BTC/USDT",
            timeframe="5m", direction="long", current_state="approved",
            highest_state_reached="approved", started_at=now, updated_at=now,
            terminal_reason=None, current_gate_snapshot={}, **provenance))
        session.flush()
        session.add(ImbalanceRecord(
            id="imb", episode_id="ep", exchange="kraken", symbol="BTC/USDT",
            timeframe="5m", direction="long", imbalance_type="fvg",
            lower_price=Decimal("100"), upper_price=Decimal("102"), status="retested",
            created_at=now, updated_at=now, measurements={}, **provenance))
        risk = RiskEvaluationRecord(
            episode_id="ep", setup_id=None, evaluated_at=now, decision="approved",
            reason_codes=[], inputs={"entry": "102", "stop": "98", "target": "110"},
            limits_snapshot={}, size_calculation={"quantity": "2", "notional": "204",
                                                  "risk_amount": "8"}, **provenance)
        session.add(risk)
        session.commit()
    service = RecommendationService(Session, "v1", "sha")
    first = service.create_for_approved_episode("ep")
    second = service.create_for_approved_episode("ep")
    assert first.version == 1 and second.version == 2
    with Session() as session:
        old = session.get(RecommendationRecord, first.id)
        assert old.status == "superseded"
        current = session.get(RecommendationRecord, second.id)
        assert current.geometry["entry_region"] == {"lower": "100.000000000000000000",
                                                     "upper": "102.000000000000000000",
                                                     "model": "linked_fvg_retest"}
        assert current.geometry["trailing_stop"]["may_move_away_from_safety"] is False
        plan = session.query(TradePlanRecord).filter_by(recommendation_id=current.id).one()
        assert plan.validity["execution_connected"] is False
        assert session.query(RecommendationEventRecord).count() == 3
