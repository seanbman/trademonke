from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class OhlcvRow:
    exchange: str
    symbol: str
    timeframe: str
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    source: str = "ccxt_public"
    closed: bool = True


@dataclass(frozen=True)
class SupplementalSnapshot:
    exchange: str
    symbol: str
    timestamp: datetime
    metric_type: str
    values: dict[str, Any]
    source: str = "ccxt_public"


@dataclass(frozen=True)
class CandidateEvidence:
    symbol: str
    quote_volume: float
    spread_bps: float | None
    history_points: int
    recommendation: str
    reasons: tuple[str, ...]

