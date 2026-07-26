from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.telemetry.models import CandidateEvidenceRecord

from .exchange import ReadOnlyExchange
from .types import CandidateEvidence

STABLE_BASES = {"USDT", "USDC", "USDE", "USDG", "DAI", "FDUSD", "TUSD", "EUR", "USD"}


def ticker_evidence(symbol: str, ticker: dict, min_quote_volume: float,
                    max_spread_bps: float) -> CandidateEvidence:
    volume = float(ticker.get("quoteVolume") or 0)
    bid, ask = ticker.get("bid"), ticker.get("ask")
    spread = None
    if bid and ask and float(bid) > 0:
        spread = (float(ask) - float(bid)) / ((float(ask) + float(bid)) / 2) * 10_000
    reasons = []
    if volume >= min_quote_volume:
        reasons.append(f"24h quote volume {volume:,.0f} meets threshold")
    else:
        reasons.append(f"24h quote volume {volume:,.0f} is below threshold")
    if spread is not None and spread <= max_spread_bps:
        reasons.append(f"spread {spread:.2f} bps meets threshold")
    else:
        reasons.append("spread is missing or too wide")
    qualifies = volume >= min_quote_volume and spread is not None and spread <= max_spread_bps
    return CandidateEvidence(symbol, volume, spread, 0, "investigate" if qualifies else "exclude", tuple(reasons))


async def rank_candidates(exchange: ReadOnlyExchange, current: tuple[str, ...], quote: str,
                          min_quote_volume: float, max_spread_bps: float,
                          limit: int = 10) -> list[CandidateEvidence]:
    tickers = await exchange.fetch_tickers()
    candidates = []
    for symbol, ticker in tickers.items():
        market = exchange.client.markets.get(symbol, {})
        if symbol in current or not market.get("spot") or market.get("quote") != quote:
            continue
        if market.get("base") in STABLE_BASES or not market.get("active", True):
            continue
        evidence = ticker_evidence(symbol, ticker, min_quote_volume, max_spread_bps)
        if evidence.recommendation == "investigate":
            candidates.append(evidence)
    return sorted(candidates, key=lambda item: item.quote_volume, reverse=True)[:limit]


def save_candidate_evidence(session: Session, exchange_id: str,
                            evidence: list[CandidateEvidence]) -> None:
    observed_at = datetime.now(timezone.utc)
    for item in evidence:
        session.add(CandidateEvidenceRecord(
            exchange=exchange_id, symbol=item.symbol, observed_at=observed_at,
            quote_volume=Decimal(str(item.quote_volume)),
            spread_bps=Decimal(str(item.spread_bps)) if item.spread_bps is not None else None,
            recommendation=item.recommendation, reasons=list(item.reasons),
        ))
    session.commit()
