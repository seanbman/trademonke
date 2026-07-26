from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any


class Direction(StrEnum):
    LONG = "long"
    SHORT = "short"


class FvgStatus(StrEnum):
    DETECTED = "detected"
    WAITING_FOR_RETEST = "waiting_for_retest"
    RETESTED = "retested"
    CONFIRMED = "confirmed"
    EXPIRED = "expired"
    INVALIDATED = "invalidated"
    CONSUMED = "consumed"


class SetupState(StrEnum):
    DETECTED = "detected"
    DEVELOPING = "developing"
    WATCH = "watch"
    STRONG_WATCH = "strong_watch"
    ELIGIBLE = "eligible"
    AWAITING_APPROVAL = "awaiting_approval"
    ENTERED = "entered"
    PARTIALLY_FILLED = "partially_filled"
    OPEN = "open"
    INVALIDATED = "invalidated"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    CLOSED = "closed"


@dataclass(frozen=True)
class Candle:
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal = Decimal("0")


@dataclass
class Fvg:
    id: str
    pair: str
    timeframe: str
    direction: Direction
    creation_index: int
    creation_timestamp: datetime
    lower: Decimal
    upper: Decimal
    status: FvgStatus = FvgStatus.WAITING_FOR_RETEST
    first_touch_timestamp: datetime | None = None
    invalidation_timestamp: datetime | None = None
    invalidation_reason: str | None = None

    @property
    def midpoint(self) -> Decimal:
        return (self.lower + self.upper) / Decimal("2")


@dataclass(frozen=True)
class ComponentResult:
    name: str
    passed: bool
    raw: dict[str, Any] = field(default_factory=dict)
    weight: Decimal = Decimal("1")
    data_quality: str = "ok"


@dataclass(frozen=True)
class Transition:
    from_state: SetupState
    to_state: SetupState
    timestamp: datetime
    reason: str


@dataclass
class Setup:
    id: str
    pair: str
    timeframe: str
    direction: Direction
    state: SetupState
    components: tuple[ComponentResult, ...]
    detected_at: datetime
    strategy_version: str
    config_hash: str
    git_sha: str
    transitions: list[Transition] = field(default_factory=list)

    @property
    def score(self) -> int:
        return sum(component.passed for component in self.components)

