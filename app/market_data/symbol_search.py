from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.market_data.candidates import STABLE_BASES
from app.market_data.watchlist import normalize_symbol
from app.telemetry.models import CandidateEvidenceRecord, WatchlistAssetRecord

# Curated major labels for search suggestions (not an exhaustive asset database).
MAJOR_BASE_NAMES: dict[str, str] = {
    "BTC": "Bitcoin",
    "ETH": "Ethereum",
    "SOL": "Solana",
    "XRP": "XRP",
    "ADA": "Cardano",
    "DOGE": "Dogecoin",
    "DOT": "Polkadot",
    "LINK": "Chainlink",
    "AVAX": "Avalanche",
    "LTC": "Litecoin",
    "BCH": "Bitcoin Cash",
    "ATOM": "Cosmos",
    "NEAR": "NEAR",
    "UNI": "Uniswap",
    "AAVE": "Aave",
    "MATIC": "Polygon",
    "POL": "Polygon",
    "ARB": "Arbitrum",
    "OP": "Optimism",
    "SUI": "Sui",
    "APT": "Aptos",
    "TRX": "TRON",
    "TON": "Toncoin",
    "SHIB": "Shiba Inu",
    "PEPE": "Pepe",
    "FIL": "Filecoin",
    "ICP": "Internet Computer",
    "ETC": "Ethereum Classic",
    "XLM": "Stellar",
    "ALGO": "Algorand",
    "HBAR": "Hedera",
    "INJ": "Injective",
    "SEI": "Sei",
    "TIA": "Celestia",
}


@dataclass(frozen=True)
class SymbolSearchHit:
    symbol: str
    base: str
    quote: str
    active: bool
    on_watchlist: bool
    watchlist_status: str | None
    protected: bool
    quote_volume: float | None
    spread_bps: float | None
    recommendation: str | None
    source: str
    display_name: str = ""
    subtitle: str = ""
    last_price: str | None = None
    price_kind: str | None = None


def normalize_query(query: str) -> str:
    value = query.strip().upper().replace("-", "/")
    if not value:
        raise ValueError("search query is required")
    return value


def matches_query(symbol: str, query: str) -> bool:
    symbol = symbol.upper()
    needle = query.strip().upper().replace("-", "/").rstrip("/")
    base, _, _quote = symbol.partition("/")
    if "/" in needle:
        return symbol.startswith(needle) or symbol == needle
    return base.startswith(needle) or symbol.startswith(needle)


def display_name_for(base: str) -> str:
    key = base.strip().upper()
    return MAJOR_BASE_NAMES.get(key, key)


def subtitle_for(quote: str, *, spot: bool = True) -> str:
    kind = "spot" if spot else "market"
    return f"{quote.strip().upper()} {kind}"


def _with_labels(hit: SymbolSearchHit) -> SymbolSearchHit:
    return replace(
        hit,
        display_name=hit.display_name or display_name_for(hit.base),
        subtitle=hit.subtitle or subtitle_for(hit.quote),
    )


def _format_price(value: Any) -> str | None:
    if value is None:
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if number <= 0:
        return None
    return format(number, "f")


def price_from_ticker(ticker: dict[str, Any] | None) -> tuple[str | None, str | None]:
    """Return (price, price_kind) from a CCXT ticker dict."""
    if not ticker:
        return None, None
    bid, ask = ticker.get("bid"), ticker.get("ask")
    try:
        if bid is not None and ask is not None and float(bid) > 0 and float(ask) > 0:
            mid = (Decimal(str(bid)) + Decimal(str(ask))) / Decimal("2")
            return format(mid, "f"), "bbo_midpoint"
    except (InvalidOperation, ValueError, TypeError):
        pass
    last = _format_price(ticker.get("last") or ticker.get("close"))
    if last is not None:
        return last, "ticker_last"
    return None, None


def enrich_hits_with_tickers(
    hits: list[SymbolSearchHit],
    tickers: dict[str, dict[str, Any]] | None,
) -> list[SymbolSearchHit]:
    tickers = tickers or {}
    enriched: list[SymbolSearchHit] = []
    for hit in hits:
        labeled = _with_labels(hit)
        price, kind = price_from_ticker(tickers.get(hit.symbol))
        if price is None:
            enriched.append(labeled)
        else:
            enriched.append(replace(labeled, last_price=price, price_kind=kind))
    return enriched


def enrich_hits_with_closes(
    hits: list[SymbolSearchHit],
    closes: dict[str, str | Decimal | float | None],
) -> list[SymbolSearchHit]:
    enriched: list[SymbolSearchHit] = []
    for hit in hits:
        labeled = _with_labels(hit)
        if labeled.last_price is not None:
            enriched.append(labeled)
            continue
        price = _format_price(closes.get(hit.symbol))
        if price is None:
            enriched.append(labeled)
        else:
            enriched.append(replace(labeled, last_price=price, price_kind="closed_candle"))
    return enriched


def search_spot_markets(markets: dict, query: str, quote: str = "USDT",
                        watchlist: dict[str, WatchlistAssetRecord] | None = None,
                        evidence: dict[str, CandidateEvidenceRecord] | None = None,
                        limit: int = 25) -> list[SymbolSearchHit]:
    query = normalize_query(query)
    watchlist = watchlist or {}
    evidence = evidence or {}
    hits: list[SymbolSearchHit] = []
    for symbol, market in markets.items():
        if market.get("quote") != quote or not market.get("spot"):
            continue
        base = str(market.get("base") or symbol.split("/", 1)[0])
        if base in STABLE_BASES:
            continue
        if not matches_query(symbol, query):
            continue
        asset = watchlist.get(symbol)
        row = evidence.get(symbol)
        hits.append(_with_labels(SymbolSearchHit(
            symbol=symbol, base=base, quote=quote,
            active=bool(market.get("active", True)),
            on_watchlist=asset is not None,
            watchlist_status=asset.status if asset else None,
            protected=bool(asset.protected) if asset else False,
            quote_volume=float(row.quote_volume) if row is not None else None,
            spread_bps=float(row.spread_bps) if row is not None and row.spread_bps is not None else None,
            recommendation=row.recommendation if row is not None else None,
            source="exchange_markets",
        )))
    hits.sort(key=lambda item: (
        0 if item.on_watchlist else 1,
        0 if item.recommendation == "investigate" else 1,
        -(item.quote_volume or 0),
        item.symbol,
    ))
    return hits[: max(1, min(limit, 50))]


def latest_candidate_evidence(session: Session, exchange: str) -> dict[str, CandidateEvidenceRecord]:
    rows = list(session.scalars(select(CandidateEvidenceRecord).where(
        CandidateEvidenceRecord.exchange == exchange).order_by(
            CandidateEvidenceRecord.observed_at.desc())))
    latest: dict[str, CandidateEvidenceRecord] = {}
    for row in rows:
        latest.setdefault(row.symbol, row)
    return latest


def watchlist_index(session: Session) -> dict[str, WatchlistAssetRecord]:
    return {item.symbol: item for item in session.scalars(select(WatchlistAssetRecord))}


def search_known_symbols(session: Session, exchange: str, query: str,
                         quote: str = "USDT", limit: int = 25) -> list[SymbolSearchHit]:
    """DB-only fallback when exchange markets are unavailable."""
    query = normalize_query(query)
    assets = watchlist_index(session)
    evidence = latest_candidate_evidence(session, exchange)
    symbols = set(assets) | set(evidence)
    try:
        exact = normalize_symbol(query if "/" in query else f"{query}/{quote}")
        symbols.add(exact)
    except ValueError:
        pass
    hits: list[SymbolSearchHit] = []
    for symbol in symbols:
        if not matches_query(symbol, query):
            continue
        base, _, sym_quote = symbol.partition("/")
        if sym_quote != quote or base in STABLE_BASES:
            continue
        asset = assets.get(symbol)
        row = evidence.get(symbol)
        hits.append(_with_labels(SymbolSearchHit(
            symbol=symbol, base=base, quote=quote, active=True,
            on_watchlist=asset is not None,
            watchlist_status=asset.status if asset else None,
            protected=bool(asset.protected) if asset else False,
            quote_volume=float(row.quote_volume) if row is not None else None,
            spread_bps=float(row.spread_bps) if row is not None and row.spread_bps is not None else None,
            recommendation=row.recommendation if row is not None else None,
            source="local_evidence" if row is not None else "watchlist",
        )))
    hits.sort(key=lambda item: (0 if item.on_watchlist else 1, -(item.quote_volume or 0), item.symbol))
    return hits[: max(1, min(limit, 50))]
