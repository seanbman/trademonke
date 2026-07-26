from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import sessionmaker

from app.research.pipeline import ResearchPipeline
from app.settings import Settings
from app.telemetry.db import Base, build_engine
from app.telemetry.models import (CandidateEvidenceRecord, CandleRecord, FeatureSnapshotRecord,
                                  GateEvaluationRecord, ImbalanceRecord, LiquidityLevelRecord,
                                  RecommendationRecord, RiskEvaluationRecord, StrategyEpisodeRecord)


def test_retested_episode_automatically_records_features_gates_risk_and_plan():
    engine = build_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    provenance = {"strategy_version": "v", "config_hash": "cfg", "git_sha": "sha"}
    with Session() as session:
        session.add_all([
            LiquidityLevelRecord(id="origin", exchange="kraken", symbol="BTC/USDT",
                                 timeframe="5m", direction="long", level_type="swing_low",
                                 price=Decimal("98"), status="swept", observed_at=now,
                                 updated_at=now, measurements={}, **provenance),
            LiquidityLevelRecord(id="target", exchange="kraken", symbol="BTC/USDT",
                                 timeframe="5m", direction="short", level_type="swing_high",
                                 price=Decimal("110"), status="active", observed_at=now,
                                 updated_at=now, measurements={}, **provenance),
        ])
        session.flush()
        session.add(StrategyEpisodeRecord(
            id="ep", liquidity_level_id="origin", exchange="kraken", symbol="BTC/USDT",
            timeframe="5m", direction="long", current_state="retested",
            highest_state_reached="retested", started_at=now, updated_at=now,
            terminal_reason=None, current_gate_snapshot={}, **provenance))
        session.add(ImbalanceRecord(
            id="imb", episode_id="ep", exchange="kraken", symbol="BTC/USDT",
            timeframe="5m", direction="long", imbalance_type="fvg",
            lower_price=Decimal("100"), upper_price=Decimal("102"), status="retested",
            created_at=now, updated_at=now, measurements={}, **provenance))
        session.add(CandidateEvidenceRecord(
            exchange="kraken", symbol="BTC/USDT", observed_at=now,
            quote_volume=Decimal("100000000"), spread_bps=Decimal("5"),
            recommendation="investigate", reasons=[]))
        session.add(CandleRecord(
            exchange="kraken", symbol="BTC/USDT", timeframe="5m", timestamp=now,
            open=Decimal("101"), high=Decimal("103"), low=Decimal("100"),
            close=Decimal("102"), volume=Decimal("100"), source="test", closed=True))
        session.commit()
    settings = Settings(database_url="sqlite:///:memory:", strategy_version="v", git_sha="sha")
    assert ResearchPipeline(Session, settings).update("BTC/USDT", "5m") == 1
    with Session() as session:
        assert session.get(StrategyEpisodeRecord, "ep").current_state == "approved"
        assert session.query(FeatureSnapshotRecord).count() == 1
        assert session.query(GateEvaluationRecord).count() == 6
        assert session.query(RiskEvaluationRecord).one().decision == "approved"
        assert session.query(RecommendationRecord).one().status == "valid"
