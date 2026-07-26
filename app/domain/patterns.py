"""Closed-candle soft-label pattern detectors (tiny kit).

Patterns are optional location tags — never trade authority, entries, or intents.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence

from .models import Candle
from .signals import confirmed_pivots

TINY_KIT: tuple[str, ...] = (
    "rising_wedge",
    "falling_wedge",
    "ascending_triangle",
    "descending_triangle",
    "flag",
    "pennant",
    "double_top",
    "double_bottom",
)


@dataclass(frozen=True)
class PatternPoint:
    index: int
    price: Decimal
    kind: str  # high | low
    timestamp: object


@dataclass(frozen=True)
class DetectedPattern:
    id: str
    pattern_type: str
    status: str  # forming | confirmed_shape | broken | expired
    confidence: str  # low | medium | high
    direction_hint: str | None
    points: tuple[PatternPoint, ...]
    upper_line: tuple[PatternPoint, PatternPoint] | None
    lower_line: tuple[PatternPoint, PatternPoint] | None
    measurements: dict

    def to_chart_dict(self) -> dict:
        def point(item: PatternPoint) -> dict:
            return {
                "index": item.index,
                "price": str(item.price),
                "kind": item.kind,
                "timestamp": item.timestamp,
            }

        return {
            "id": self.id,
            "pattern_type": self.pattern_type,
            "status": self.status,
            "confidence": self.confidence,
            "direction_hint": self.direction_hint,
            "points": [point(item) for item in self.points],
            "upper_line": [point(item) for item in self.upper_line] if self.upper_line else None,
            "lower_line": [point(item) for item in self.lower_line] if self.lower_line else None,
            "measurements": {
                key: (str(value) if isinstance(value, Decimal) else value)
                for key, value in self.measurements.items()
            },
            "soft_label": True,
            "authority": "none",
        }


def detect_patterns(
    candles: Sequence[Candle],
    *,
    left: int = 2,
    right: int = 2,
    equal_tolerance_bps: Decimal = Decimal("25"),
    flat_slope_bps_per_bar: Decimal = Decimal("5"),
    lookback: int = 80,
) -> list[DetectedPattern]:
    """Detect soft-label patterns from confirmed pivots on closed candles only."""
    if len(candles) < left + right + 6:
        return []
    offset = max(0, len(candles) - lookback)
    window = list(candles[offset:])
    highs, lows = confirmed_pivots(window, left, right)
    high_pts = [_mk(window, i, offset, "high") for i in sorted(highs)]
    low_pts = [_mk(window, i, offset, "low") for i in sorted(lows)]
    found: list[DetectedPattern] = []
    found.extend(_doubles(high_pts, low_pts, "double_top", equal_tolerance_bps))
    found.extend(_doubles(low_pts, high_pts, "double_bottom", equal_tolerance_bps))
    found.extend(_wedge_triangle(high_pts, low_pts, flat_slope_bps_per_bar, window, offset))
    found.extend(_flag_pennant(window, offset, high_pts, low_pts))
    return _dedupe(found)


def _mk(window: Sequence[Candle], local: int, offset: int, kind: str) -> PatternPoint:
    candle = window[local]
    price = candle.high if kind == "high" else candle.low
    return PatternPoint(local + offset, price, kind, candle.timestamp)


def _slope(a: PatternPoint, b: PatternPoint) -> Decimal | None:
    span = b.index - a.index
    if span <= 0:
        return None
    return (b.price - a.price) / Decimal(span)


def _within_bps(first: Decimal, second: Decimal, tolerance_bps: Decimal) -> bool:
    reference = max(abs(first), abs(second))
    return reference != 0 and abs(first - second) / reference * Decimal("10000") <= tolerance_bps


def _pattern_id(pattern_type: str, points: Sequence[PatternPoint]) -> str:
    raw = "|".join([pattern_type, *(f"{p.index}:{p.price}:{p.kind}" for p in points)])
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def _doubles(
    extremes: Sequence[PatternPoint],
    opposite: Sequence[PatternPoint],
    pattern_type: str,
    tolerance_bps: Decimal,
) -> list[DetectedPattern]:
    if len(extremes) < 2:
        return []
    first, second = extremes[-2], extremes[-1]
    if not _within_bps(first.price, second.price, tolerance_bps):
        return []
    middle = [p for p in opposite if first.index < p.index < second.index]
    if not middle:
        return []
    confidence = "high" if _within_bps(first.price, second.price, tolerance_bps / 2) else "medium"
    hint = "short" if pattern_type == "double_top" else "long"
    return [DetectedPattern(
        id=_pattern_id(pattern_type, (first, middle[-1], second)),
        pattern_type=pattern_type,
        status="confirmed_shape",
        confidence=confidence,
        direction_hint=hint,
        points=(first, middle[-1], second),
        upper_line=(first, second) if pattern_type == "double_top" else None,
        lower_line=(first, second) if pattern_type == "double_bottom" else None,
        measurements={
            "extreme_a": first.price,
            "extreme_b": second.price,
            "neck": middle[-1].price,
            "note": "soft_label_only",
        },
    )]


def _wedge_triangle(
    highs: Sequence[PatternPoint],
    lows: Sequence[PatternPoint],
    flat_bps: Decimal,
    window: Sequence[Candle],
    offset: int,
) -> list[DetectedPattern]:
    if len(highs) < 2 or len(lows) < 2:
        return []
    uh, ul = highs[-2], highs[-1]
    lh, ll = lows[-2], lows[-1]
    # Prefer interleaved structure: start roughly together.
    start = min(uh.index, lh.index)
    end = max(ul.index, ll.index)
    if end - start < 4:
        return []
    high_slope = _slope(uh, ul)
    low_slope = _slope(lh, ll)
    if high_slope is None or low_slope is None:
        return []
    mid_price = (uh.price + lh.price) / Decimal("2")
    if mid_price <= 0:
        return []
    high_bps = high_slope / mid_price * Decimal("10000")
    low_bps = low_slope / mid_price * Decimal("10000")
    width_start = uh.price - lh.price
    width_end = ul.price - ll.price
    if width_start <= 0 or width_end <= 0:
        return []
    narrowing = width_end < width_start * Decimal("0.92")
    high_flat = abs(high_bps) <= flat_bps
    low_flat = abs(low_bps) <= flat_bps

    pattern_type: str | None = None
    hint: str | None = None
    if high_flat and low_bps > flat_bps and narrowing:
        pattern_type, hint = "ascending_triangle", "long"
    elif low_flat and high_bps < -flat_bps and narrowing:
        pattern_type, hint = "descending_triangle", "short"
    elif high_bps > flat_bps and low_bps > flat_bps and low_bps > high_bps and narrowing:
        pattern_type, hint = "rising_wedge", None
    elif high_bps < -flat_bps and low_bps < -flat_bps and high_bps < low_bps and narrowing:
        pattern_type, hint = "falling_wedge", None
    if pattern_type is None:
        return []

    status = "confirmed_shape"
    last = window[-1]
    # Break = decisive close beyond the nearer boundary after the pattern end.
    if pattern_type in {"rising_wedge", "ascending_triangle"} and last.close > ul.price:
        status = "broken"
    if pattern_type in {"falling_wedge", "descending_triangle"} and last.close < ll.price:
        status = "broken"

    points = tuple(sorted((uh, ul, lh, ll), key=lambda p: p.index))
    return [DetectedPattern(
        id=_pattern_id(pattern_type, points),
        pattern_type=pattern_type,
        status=status,
        confidence="medium" if narrowing else "low",
        direction_hint=hint,
        points=points,
        upper_line=(uh, ul),
        lower_line=(lh, ll),
        measurements={
            "high_slope_bps_per_bar": high_bps,
            "low_slope_bps_per_bar": low_bps,
            "width_start": width_start,
            "width_end": width_end,
            "note": "soft_label_only",
            "window_offset": offset,
        },
    )]


def _flag_pennant(
    window: Sequence[Candle],
    offset: int,
    highs: Sequence[PatternPoint],
    lows: Sequence[PatternPoint],
) -> list[DetectedPattern]:
    if len(window) < 20 or len(highs) < 2 or len(lows) < 2:
        return []
    # Pole: strongest absolute move in a short closed window ending before consolidation.
    pole_len = 6
    cons_len = 10
    if len(window) < pole_len + cons_len:
        return []
    cons = window[-cons_len:]
    pole = window[-(pole_len + cons_len):-cons_len]
    pole_move = pole[-1].close - pole[0].open
    pole_range = max(c.high for c in pole) - min(c.low for c in pole)
    cons_range = max(c.high for c in cons) - min(c.low for c in cons)
    if pole_range <= 0 or abs(pole_move) < pole_range * Decimal("0.55"):
        return []
    if cons_range >= abs(pole_move) * Decimal("0.55"):
        return []
    uh, ul = highs[-2], highs[-1]
    lh, ll = lows[-2], lows[-1]
    if uh.index < offset + len(window) - cons_len or lh.index < offset + len(window) - cons_len:
        # Prefer pivots inside consolidation when available; otherwise use ends of cons.
        pass
    high_slope = _slope(uh, ul)
    low_slope = _slope(lh, ll)
    if high_slope is None or low_slope is None:
        return []
    converging = (ul.price - ll.price) < (uh.price - lh.price) * Decimal("0.9")
    pattern_type = "pennant" if converging else "flag"
    direction = "long" if pole_move > 0 else "short"
    # Soft continuation hint only when consolidation counters the pole mildly.
    if direction == "long" and high_slope > 0 and low_slope > 0:
        return []
    if direction == "short" and high_slope < 0 and low_slope < 0:
        return []
    pole_start = len(window) - pole_len - cons_len
    points = (
        _mk(window, pole_start, offset, "low" if direction == "long" else "high"),
        _mk(window, pole_start + pole_len - 1, offset, "high" if direction == "long" else "low"),
        uh, ul, lh, ll,
    )
    return [DetectedPattern(
        id=_pattern_id(pattern_type, (uh, ul, lh, ll)),
        pattern_type=pattern_type,
        status="confirmed_shape",
        confidence="medium" if converging else "low",
        direction_hint=direction,
        points=points,
        upper_line=(uh, ul),
        lower_line=(lh, ll),
        measurements={
            "pole_move": pole_move,
            "pole_range": pole_range,
            "consolidation_range": cons_range,
            "note": "soft_label_only",
        },
    )]


def _dedupe(patterns: Sequence[DetectedPattern]) -> list[DetectedPattern]:
    rank = {"high": 3, "medium": 2, "low": 1}
    best: dict[str, DetectedPattern] = {}
    for item in patterns:
        prior = best.get(item.pattern_type)
        if prior is None or rank[item.confidence] > rank[prior.confidence]:
            best[item.pattern_type] = item
        elif prior is not None and rank[item.confidence] == rank[prior.confidence]:
            if item.points[-1].index >= prior.points[-1].index:
                best[item.pattern_type] = item
    # Prefer at most one compression family + doubles.
    selected = list(best.values())
    compression = [p for p in selected if p.pattern_type in {
        "rising_wedge", "falling_wedge", "ascending_triangle", "descending_triangle", "flag", "pennant",
    }]
    if len(compression) > 1:
        keep = max(compression, key=lambda p: (rank[p.confidence], p.points[-1].index))
        selected = [p for p in selected if p not in compression or p is keep]
    return sorted(selected, key=lambda p: (p.points[-1].index, p.pattern_type))
