from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Sequence

from .models import Candle
from .signals import confirmed_pivots


class LevelSide(StrEnum):
    HIGH = "high"
    LOW = "low"


class LevelEventType(StrEnum):
    TOUCH = "touch_recorded"
    SWEPT = "level_swept"
    ACCEPTED_BREAKOUT = "accepted_breakout"


@dataclass(frozen=True)
class DetectedLevel:
    side: LevelSide
    price: Decimal
    pivot_index: int
    confirmed_index: int
    cluster_size: int = 1


def detect_confirmed_levels(candles: Sequence[Candle], left: int = 2, right: int = 2,
                            tolerance_bps: Decimal = Decimal("5")) -> list[DetectedLevel]:
    """Detect levels using only pivots with the required closed candles to their right."""
    highs, lows = confirmed_pivots(candles, left, right)
    raw = [(LevelSide.HIGH, candles[index].high, index) for index in sorted(highs)]
    raw += [(LevelSide.LOW, candles[index].low, index) for index in sorted(lows)]
    clusters: list[list[tuple[LevelSide, Decimal, int]]] = []
    for candidate in sorted(raw, key=lambda item: (item[0].value, item[1], item[2])):
        matching = next((cluster for cluster in clusters
                         if cluster[0][0] == candidate[0]
                         and _within_bps(cluster[-1][1], candidate[1], tolerance_bps)), None)
        if matching is None:
            clusters.append([candidate])
        else:
            matching.append(candidate)
    result = []
    for cluster in clusters:
        side = cluster[0][0]
        price = sum((item[1] for item in cluster), Decimal("0")) / len(cluster)
        pivot_index = cluster[-1][2]
        result.append(DetectedLevel(side, price, pivot_index, pivot_index + right, len(cluster)))
    return sorted(result, key=lambda item: (item.confirmed_index, item.side.value, item.price))


def classify_level_candle(side: LevelSide, price: Decimal, candle: Candle,
                          tolerance_bps: Decimal = Decimal("2")) -> LevelEventType | None:
    tolerance = price * tolerance_bps / Decimal("10000")
    if side is LevelSide.HIGH:
        if candle.close > price:
            return LevelEventType.ACCEPTED_BREAKOUT
        if candle.high > price:
            return LevelEventType.SWEPT
        if candle.high >= price - tolerance:
            return LevelEventType.TOUCH
    else:
        if candle.close < price:
            return LevelEventType.ACCEPTED_BREAKOUT
        if candle.low < price:
            return LevelEventType.SWEPT
        if candle.low <= price + tolerance:
            return LevelEventType.TOUCH
    return None


def _within_bps(first: Decimal, second: Decimal, tolerance_bps: Decimal) -> bool:
    reference = max(abs(first), abs(second))
    return reference != 0 and abs(first - second) / reference * Decimal("10000") <= tolerance_bps
