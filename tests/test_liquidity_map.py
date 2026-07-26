from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.domain.liquidity import (LevelEventType, LevelSide, classify_level_candle,
                                  detect_confirmed_levels)
from app.domain.models import Candle
from app.liquidity.service import LiquidityMapService
from app.telemetry.db import Base, build_engine
from app.telemetry.models import (CandleRecord, LiquidityLevelEventRecord,
                                  LiquidityLevelRecord)


def candle(index, open_, high, low, close):
    return Candle(datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=5 * index),
                  *(Decimal(str(value)) for value in (open_, high, low, close, 100)))


def test_confirmed_levels_require_right_candles_and_classify_observable_crossing():
    candles = [candle(0, 10, 11, 9, 10), candle(1, 10, 12, 8, 11),
               candle(2, 11, 13, 10, 12), candle(3, 11, 12, 9, 10)]
    assert not any(level.side is LevelSide.HIGH and level.pivot_index == 2
                   for level in detect_confirmed_levels(candles[:3], left=1, right=1))
    levels = detect_confirmed_levels(candles, left=1, right=1)
    assert any(level.side is LevelSide.HIGH and level.pivot_index == 2 for level in levels)
    assert classify_level_candle(LevelSide.HIGH, Decimal("13"),
                                 candle(4, 12, 14, 11, 12.5)) is LevelEventType.SWEPT
    assert classify_level_candle(LevelSide.HIGH, Decimal("13"),
                                 candle(4, 12, 14, 11, 13.5)) is LevelEventType.ACCEPTED_BREAKOUT


def test_persistent_level_and_sweep_event_are_idempotent():
    engine = build_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    values = [(10, 11, 9, 10), (10, 12, 8, 11), (11, 13, 7, 12),
              (12, 12.5, 8.5, 11), (11, 12, 9, 10), (10, 11, 6, 9)]
    with Session() as session:
        for index, (open_, high, low, close) in enumerate(values):
            item = candle(index, open_, high, low, close)
            session.add(CandleRecord(
                exchange="kraken", symbol="BTC/USDT", timeframe="5m",
                timestamp=item.timestamp, open=item.open, high=item.high, low=item.low,
                close=item.close, volume=item.volume, source="test", closed=True))
        session.commit()
    service = LiquidityMapService(Session, "kraken", "v1", "sha", left=2, right=2)
    assert service.update("BTC/USDT", "5m") >= 2
    service.update("BTC/USDT", "5m")
    with Session() as session:
        low = session.scalar(select(LiquidityLevelRecord).where(
            LiquidityLevelRecord.direction == "long"))
        assert low is not None and low.status == "swept"
        events = list(session.scalars(select(LiquidityLevelEventRecord).where(
            LiquidityLevelEventRecord.liquidity_level_id == low.id)))
        assert [item.event_type for item in events].count("level_swept") == 1
