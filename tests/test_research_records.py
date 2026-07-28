from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.orm import sessionmaker

from app.api.main import episode_events, episodes, gui_bootstrap, gui_chart, liquidity_levels
from app.settings import Settings
from app.telemetry.db import Base, build_engine
from app.telemetry.models import (EpisodeEventRecord, IndicatorSnapshotRecord,
                                  LiquidityLevelRecord, StrategyEpisodeRecord)


def test_liquidity_episode_and_append_only_event_read_models():
    engine = build_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    now = datetime.now(timezone.utc)
    provenance = {"strategy_version": "v1", "config_hash": "cfg", "git_sha": "sha"}
    with Session() as session:
        level = LiquidityLevelRecord(
            id="lvl_1", exchange="kraken", symbol="BTC/USDT", timeframe="5m",
            direction="long", level_type="swing_low", price=Decimal("60000.25"),
            status="active", observed_at=now, updated_at=now,
            measurements={"touches": 2}, **provenance)
        episode = StrategyEpisodeRecord(
            id="ep_1", liquidity_level_id="lvl_1", exchange="kraken",
            symbol="BTC/USDT", timeframe="5m", direction="long",
            current_state="swept", highest_state_reached="swept",
            started_at=now, updated_at=now, terminal_reason=None,
            current_gate_snapshot={}, **provenance)
        snapshot = IndicatorSnapshotRecord(
            exchange="kraken", symbol="BTC/USDT", timeframe="5m",
            candle_timestamp=now, evaluated_at=now, direction="long", score=4,
            setup_state="watch", components={
                "htf_bias": {"passed": True},
                "liquidity_sweep": {"passed": True, "level": "60000.25"},
            }, strategy_version="v1")
        older_snapshot = IndicatorSnapshotRecord(
            exchange="kraken", symbol="BTC/USDT", timeframe="5m",
            candle_timestamp=now - timedelta(minutes=5),
            evaluated_at=now - timedelta(minutes=5), direction="long", score=1,
            setup_state="developing", components={"htf_bias": {"passed": False}},
            strategy_version="v1")
        session.add_all([level, episode, older_snapshot, snapshot])
        session.flush()
        session.add(EpisodeEventRecord(
            event_id="ep_1:swept:1", episode_id="ep_1", event_type="state_changed",
            prior_state="observed", current_state="swept", occurred_at=now,
            candle_timestamp=now, reason_codes=["level_crossed"],
            measurements={"distance": {"value": "4.5", "unit": "bps"}}, **provenance))
        session.commit()
        assert [item.id for item in liquidity_levels(session)] == ["lvl_1"]
        assert [item.id for item in episodes(session)] == ["ep_1"]
        assert episode_events("ep_1", session, Settings())[0].reason_codes == ["level_crossed"]
        bootstrap = gui_bootstrap(session, Settings())
        assert bootstrap.contract_version == "gui.v1"
        assert bootstrap.episodes[0].id == "ep_1"
        chart = gui_chart("BTC/USDT", "5m", 500, session, Settings())
        assert chart.contract_version == "chart.v1"
        assert chart.liquidity_levels[0].id == "lvl_1"
        assert chart.indicator_snapshots[0].direction == "long"
        assert chart.indicator_snapshots[0].score == 4
        assert chart.indicator_snapshots[0].components["htf_bias"]["passed"] is True
