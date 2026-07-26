from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy.orm import sessionmaker

from app.market_data.watchlist import (collection_symbols, confirm_change,
                                       confirm_backfill_request, create_backfill_request,
                                       create_change, enqueue_backfill, ensure_anchors)
from app.telemetry.db import Base, build_engine
from app.telemetry.models import (BackfillJobRecord, CandidateEvidenceRecord,
                                  CandleRecord, WatchlistAssetRecord)


@pytest.fixture
def session():
    engine = build_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as value:
        yield value


def test_probe_confirm_and_protected_anchor(session):
    ensure_anchors(session)
    assert collection_symbols(session) == ("BTC/USDT", "ETH/USDT")
    with pytest.raises(ValueError, match="protected"):
        create_change(session, "BTC/USDT", "disabled", 42)
    change = create_change(session, "SOL", "probe", 42)
    asset = confirm_change(session, change.id, 42, "okx", 10_000_000, 30)
    assert asset.symbol == "SOL/USDT" and asset.status == "probe"
    assert "SOL/USDT" in collection_symbols(session)
    job = session.query(BackfillJobRecord).filter_by(symbol="SOL/USDT").one()
    assert job.status == "pending" and job.days == 365
    assert enqueue_backfill(session, "okx", "SOL/USDT", ("1h",), 30, "test").id == job.id


def test_active_promotion_requires_liquidity_and_history(session):
    ensure_anchors(session)
    probe = create_change(session, "SOL/USDT", "probe", 42)
    confirm_change(session, probe.id, 42, "okx", 10_000_000, 30)
    promotion = create_change(session, "SOL/USDT", "active", 42)
    with pytest.raises(ValueError, match="not eligible"):
        confirm_change(session, promotion.id, 42, "okx", 10_000_000, 30)

    now = datetime.now(timezone.utc)
    session.add(CandidateEvidenceRecord(exchange="okx", symbol="SOL/USDT", observed_at=now,
                                        quote_volume=Decimal("20000000"), spread_bps=Decimal("2"),
                                        recommendation="investigate", reasons=[]))
    for index in range(30 * 24):
        timestamp = now - timedelta(hours=index)
        session.add(CandleRecord(exchange="okx", symbol="SOL/USDT", timeframe="1h",
                                 timestamp=timestamp, open=1, high=2, low=1, close=2, volume=100,
                                 source="test", closed=True))
    session.commit()
    asset = confirm_change(session, promotion.id, 42, "okx", 10_000_000, 30)
    assert asset.status == "active"


def test_confirmed_manual_backfill_request_does_not_change_watchlist_state(session):
    ensure_anchors(session)
    request = create_backfill_request(session, "okx", "BTC/USDT", ("1h",), 30, 42)
    job = confirm_backfill_request(session, request.id, 42)
    assert job.symbol == "BTC/USDT" and job.days == 30 and job.timeframes == ["1h"]
    assert session.get(type(request), request.id).state == "confirmed"
    assert session.get(WatchlistAssetRecord, "BTC/USDT").status == "active"
