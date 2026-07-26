from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.domain.episodes import (EpisodeState, classify_displacement, classify_recovery,
                                 zone_retested)
from app.domain.models import Candle, Direction
from app.episodes.service import EpisodeEngine
from app.telemetry.db import Base, build_engine
from app.telemetry.models import (CandleRecord, EpisodeEventRecord, ImbalanceRecord,
                                  LiquidityLevelEventRecord, LiquidityLevelRecord,
                                  StrategyEpisodeRecord)


def candle(index, open_, high, low, close):
    return Candle(datetime(2026, 2, 1, tzinfo=timezone.utc) + timedelta(minutes=5 * index),
                  *(Decimal(str(value)) for value in (open_, high, low, close, 100)))


def test_episode_rules_are_directional_and_decimal():
    recovered = classify_recovery(Direction.LONG, Decimal("100"), candle(1, 99, 103, 98, 102))
    assert recovered.next_state is EpisodeState.RECLAIMED
    displaced = classify_displacement(Direction.LONG, candle(2, 102, 111, 101, 110), Decimal("20"))
    assert displaced and displaced.next_state is EpisodeState.DISPLACED
    assert zone_retested(Direction.LONG, Decimal("103"), Decimal("105"),
                         candle(3, 106, 108, 104, 107))


def test_sweep_advances_through_linked_imbalance_and_retest_idempotently():
    engine = build_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    candles = [candle(0, 99, 102, 98, 101), candle(1, 101, 103, 99, 102),
               candle(2, 102, 111, 105, 110), candle(3, 110, 112, 108, 111),
               candle(4, 106, 108, 104, 107)]
    provenance = {"strategy_version": "v1", "config_hash": "cfg", "git_sha": "sha"}
    with Session() as session:
        level = LiquidityLevelRecord(
            id="lvl_1", exchange="kraken", symbol="BTC/USDT", timeframe="5m",
            direction="long", level_type="swing_low", price=Decimal("100"), status="swept",
            observed_at=candles[0].timestamp - timedelta(minutes=5), updated_at=candles[0].timestamp,
            measurements={"side": "low"}, **provenance)
        session.add(level)
        session.flush()
        session.add(LiquidityLevelEventRecord(
            event_id="level:lvl_1:sweep", liquidity_level_id="lvl_1",
            event_type="level_swept", occurred_at=candles[0].timestamp,
            candle_timestamp=candles[0].timestamp, reason_codes=["level_swept"],
            measurements={}, **provenance))
        for item in candles:
            session.add(CandleRecord(
                exchange="kraken", symbol="BTC/USDT", timeframe="5m",
                timestamp=item.timestamp, open=item.open, high=item.high, low=item.low,
                close=item.close, volume=item.volume, source="test", closed=True))
        session.commit()
    service = EpisodeEngine(Session, "kraken", "v1", "sha", Decimal("20"))
    assert service.update("BTC/USDT", "5m") == 5
    assert service.update("BTC/USDT", "5m") == 0
    with Session() as session:
        episode = session.scalar(select(StrategyEpisodeRecord))
        assert episode.current_state == "retested"
        assert episode.highest_state_reached == "retested"
        assert session.query(ImbalanceRecord).count() == 1
        states = [event.current_state for event in session.scalars(select(EpisodeEventRecord).order_by(
            EpisodeEventRecord.occurred_at))]
        assert states == ["swept", "reclaimed", "displaced", "imbalance_created", "retested"]
