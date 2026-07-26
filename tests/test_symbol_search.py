from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy.orm import sessionmaker

from app.market_data.symbol_search import (
    display_name_for,
    enrich_hits_with_closes,
    enrich_hits_with_tickers,
    matches_query,
    price_from_ticker,
    search_known_symbols,
    search_spot_markets,
    SymbolSearchHit,
)
from app.market_data.watchlist import ensure_anchors
from app.telemetry.db import Base, build_engine
from app.telemetry.models import CandidateEvidenceRecord


@pytest.fixture
def session():
    engine = build_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as value:
        yield value


def test_matches_query_prefix_and_pair():
    assert matches_query("SOL/USDT", "SOL")
    assert matches_query("SOL/USDT", "sol")
    assert matches_query("SOL/USDT", "SOL/USDT")
    assert not matches_query("SOL/USDT", "BTC")


def test_display_name_for_majors_and_fallback():
    assert display_name_for("BTC") == "Bitcoin"
    assert display_name_for("sol") == "Solana"
    assert display_name_for("XYZ") == "XYZ"


def test_price_from_ticker_prefers_bbo_midpoint():
    price, kind = price_from_ticker({"bid": "100", "ask": "102", "last": "99"})
    assert kind == "bbo_midpoint"
    assert price == "101"
    last, last_kind = price_from_ticker({"last": "55.5"})
    assert last_kind == "ticker_last"
    assert last == "55.5"


def test_enrich_hits_with_tickers_and_closes():
    hit = SymbolSearchHit(
        symbol="SOL/USDT", base="SOL", quote="USDT", active=True,
        on_watchlist=False, watchlist_status=None, protected=False,
        quote_volume=1.0, spread_bps=2.0, recommendation="investigate",
        source="exchange_markets",
    )
    priced = enrich_hits_with_tickers([hit], {"SOL/USDT": {"bid": "10", "ask": "12"}})
    assert priced[0].display_name == "Solana"
    assert priced[0].subtitle == "USDT spot"
    assert priced[0].last_price == "11"
    assert priced[0].price_kind == "bbo_midpoint"

    closed = enrich_hits_with_closes(
        [SymbolSearchHit(
            symbol="ADA/USDT", base="ADA", quote="USDT", active=True,
            on_watchlist=False, watchlist_status=None, protected=False,
            quote_volume=None, spread_bps=None, recommendation=None,
            source="watchlist",
        )],
        {"ADA/USDT": Decimal("1.25")},
    )
    assert closed[0].display_name == "Cardano"
    assert closed[0].last_price == "1.25"
    assert closed[0].price_kind == "closed_candle"


def test_search_spot_markets_filters_quote_and_stables():
    markets = {
        "SOL/USDT": {"spot": True, "quote": "USDT", "base": "SOL", "active": True},
        "USDC/USDT": {"spot": True, "quote": "USDT", "base": "USDC", "active": True},
        "SOL/USD": {"spot": True, "quote": "USD", "base": "SOL", "active": True},
        "LINK/USDT": {"spot": True, "quote": "USDT", "base": "LINK", "active": True},
    }
    hits = search_spot_markets(markets, "S", quote="USDT", limit=10)
    symbols = [item.symbol for item in hits]
    assert "SOL/USDT" in symbols
    assert "USDC/USDT" not in symbols
    assert "SOL/USD" not in symbols
    sol = next(item for item in hits if item.symbol == "SOL/USDT")
    assert sol.display_name == "Solana"
    assert sol.subtitle == "USDT spot"


def test_search_known_symbols_includes_evidence_and_exact(session):
    ensure_anchors(session)
    now = datetime.now(timezone.utc)
    session.add(CandidateEvidenceRecord(
        exchange="kraken", symbol="SOL/USDT", observed_at=now,
        quote_volume=Decimal("25000000"), spread_bps=Decimal("3"),
        recommendation="investigate", reasons=["ok"]))
    session.commit()
    hits = search_known_symbols(session, "kraken", "SOL", quote="USDT")
    assert any(item.symbol == "SOL/USDT" and item.recommendation == "investigate" for item in hits)
    exact = search_known_symbols(session, "kraken", "ADA", quote="USDT")
    assert any(item.symbol == "ADA/USDT" for item in exact)
