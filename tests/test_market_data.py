from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import sessionmaker

from app.market_data.candidates import ticker_evidence
from app.market_data.collector import MarketDataCollector, closed_rows
from app.telemetry.db import Base, build_engine
from app.telemetry.models import CandleRecord


def test_closed_rows_excludes_forming_candle():
    now = 1_800_000
    raw = [
        [1_680_000, 1, 2, 0.5, 1.5, 10],
        [1_770_000, 1.5, 2, 1, 1.8, 11],
    ]
    rows = closed_rows("okx", "BTC/USDT", "1m", raw, now, 60_000)
    assert len(rows) == 1
    assert rows[0].timestamp == datetime.fromtimestamp(1680, tz=timezone.utc)


def test_candidate_requires_primary_liquidity_and_spread_evidence():
    included = ticker_evidence("SOL/USDT", {"quoteVolume": 20_000_000, "bid": 100, "ask": 100.1},
                               10_000_000, 30)
    excluded = ticker_evidence("TINY/USDT", {"quoteVolume": 1000, "bid": 1, "ask": 2},
                               10_000_000, 30)
    assert included.recommendation == "investigate"
    assert excluded.recommendation == "exclude"


class CursorExchange:
    exchange_id = "okx"

    class Client:
        @staticmethod
        def parse_timeframe(_):
            return 300

        @staticmethod
        def milliseconds():
            return 1_800_000

    client = Client()

    def __init__(self):
        self.since = None

    async def fetch_ohlcv(self, symbol, timeframe, since, limit):
        self.since = since
        return []


@pytest.mark.anyio
async def test_update_treats_naive_sqlite_timestamp_as_utc():
    engine = build_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    timestamp = datetime(2026, 7, 11, 6, 15)  # SQLite returns UTC contract values as naive.
    with Session() as session:
        session.add(CandleRecord(exchange="okx", symbol="BTC/USDT", timeframe="5m",
                                 timestamp=timestamp, open=1, high=2, low=1, close=2, volume=1,
                                 source="test", closed=True))
        session.commit()
    exchange = CursorExchange()
    await MarketDataCollector(exchange, Session).update("BTC/USDT", "5m")
    assert exchange.since == int(timestamp.replace(tzinfo=timezone.utc).timestamp() * 1000)
