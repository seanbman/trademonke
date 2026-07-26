from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.indicators.engine import IndicatorEngine, ema
from app.telemetry.db import Base, build_engine
from app.telemetry.models import (CandleRecord, IndicatorAlertEventRecord,
                                  IndicatorSnapshotRecord)


def add_candle(session, symbol, timeframe, timestamp, open_, high, low, close):
    session.add(CandleRecord(exchange="okx", symbol=symbol, timeframe=timeframe,
                             timestamp=timestamp, open=Decimal(str(open_)), high=Decimal(str(high)),
                             low=Decimal(str(low)), close=Decimal(str(close)), volume=Decimal("100"),
                             source="test", closed=True))


def test_ema_requires_length_and_indicator_transitions_are_persisted():
    assert ema([Decimal("1")] * 49, 50) is None
    engine_db = build_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine_db)
    Session = sessionmaker(bind=engine_db, expire_on_commit=False)
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    with Session() as session:
        for timeframe, minutes in (("15m", 15), ("30m", 30), ("1h", 60)):
            for index in range(60):
                value = 100 + index
                add_candle(session, "BTC/USDT", timeframe,
                           now - timedelta(minutes=minutes * (60 - index)),
                           value - 1, value + 1, value - 2, value)
        for symbol in ("BTC/USDT", "ETH/USDT"):
            for index in range(30):
                add_candle(session, symbol, "5m", now - timedelta(minutes=5 * (30 - index)),
                           10, 11, 9, 10)
        session.commit()

    indicator = IndicatorEngine(Session, "okx", "test-v1")
    assert len(indicator.evaluate_symbol("BTC/USDT")) == 2
    assert indicator.evaluate_symbol("BTC/USDT") == []  # same closed candle is idempotent
    with Session() as session:
        add_candle(session, "BTC/USDT", "5m", now, 10, 21, 9.5, 20)
        add_candle(session, "ETH/USDT", "5m", now, 10, 11, 9, 10)
        session.commit()
    assert len(indicator.evaluate_symbol("BTC/USDT")) == 2
    with Session() as session:
        snapshots = list(session.scalars(select(IndicatorSnapshotRecord)))
        events = list(session.scalars(select(IndicatorAlertEventRecord)))
        assert len(snapshots) == 4
        assert any(event.component == "structure" and event.new_value == "True" for event in events)
        assert len({event.event_id for event in events}) == len(events)
