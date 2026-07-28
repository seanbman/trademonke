from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.orm import sessionmaker

from app.domain.models import Candle
from app.liquidity.invalidations import (
    evaluate_annotation_invalidations,
    evaluate_liquidity_invalidations,
)
from app.telemetry.db import Base, build_engine
from app.telemetry.models import ChartAnnotationRecord, LiquidityLevelRecord


def _session():
    engine = build_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def test_annotation_and_liquidity_invalidation_events():
    session = _session()
    now = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
    session.add(ChartAnnotationRecord(
        exchange="kraken", symbol="BTC/USDT", timeframe="5m", kind="horizontal",
        label="LQ", checklist_item=None, geometry={"price": "100"},
        created_at=now, updated_at=now, created_by="test", active=True,
    ))
    session.add(LiquidityLevelRecord(
        id="lvl-1", exchange="kraken", symbol="BTC/USDT", timeframe="5m",
        direction="short", level_type="high", price=Decimal("100"), status="active",
        observed_at=now, updated_at=now, measurements={}, strategy_version="v",
        config_hash="h", git_sha="s",
    ))
    session.commit()
    candle = Candle(now, Decimal("101"), Decimal("102"), Decimal("99"), Decimal("98"))
    prior = [
        Candle(now - timedelta(minutes=5 * i), Decimal("100"), Decimal("101"),
               Decimal("99"), Decimal("100"))
        for i in range(12, 0, -1)
    ]
    ann = evaluate_annotation_invalidations(
        session, exchange="kraken", symbol="BTC/USDT", timeframe="5m", candle=candle)
    liq = evaluate_liquidity_invalidations(
        session, exchange="kraken", symbol="BTC/USDT", timeframe="5m",
        candle=candle, prior_candles=prior)
    session.commit()
    assert len(ann) == 1
    assert ann[0].event_type == "trendline_break"
    assert any(item.event_type == "liquidity_sweep" for item in liq)
