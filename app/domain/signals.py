from __future__ import annotations

import hashlib
from decimal import Decimal
from typing import Sequence

from .models import Candle, ComponentResult, Direction, Fvg, FvgStatus


def confirmed_pivots(candles: Sequence[Candle], left: int = 1, right: int = 1) -> tuple[set[int], set[int]]:
    """Return confirmed high/low pivot indices; right-side candles delay confirmation."""
    highs: set[int] = set()
    lows: set[int] = set()
    for i in range(left, len(candles) - right):
        before = candles[i - left : i]
        after = candles[i + 1 : i + right + 1]
        if all(candles[i].high > c.high for c in (*before, *after)):
            highs.add(i)
        if all(candles[i].low < c.low for c in (*before, *after)):
            lows.add(i)
    return highs, lows


def liquidity_sweep(candle: Candle, level: Decimal, direction: Direction, require_close_inside: bool = True) -> bool:
    if direction is Direction.LONG:
        crossed = candle.low < level
        reclaimed = candle.close > level
    else:
        crossed = candle.high > level
        reclaimed = candle.close < level
    return crossed and (reclaimed if require_close_inside else True)


def detect_fvgs(candles: Sequence[Candle], pair: str, timeframe: str) -> list[Fvg]:
    """Pine-compatible indexing: on i, compare candle i-1 with i-2."""
    result: list[Fvg] = []
    for i in range(2, len(candles)):
        recent, older = candles[i - 1], candles[i - 2]
        if recent.low > older.high:
            direction, lower, upper = Direction.LONG, older.high, recent.low
        elif recent.high < older.low:
            direction, lower, upper = Direction.SHORT, recent.high, older.low
        else:
            continue
        raw_id = f"{pair}|{timeframe}|{direction}|{recent.timestamp.isoformat()}|{lower}|{upper}"
        result.append(Fvg(hashlib.sha256(raw_id.encode()).hexdigest()[:24], pair, timeframe, direction, i - 1, recent.timestamp, lower, upper))
    return result


def advance_fvg(fvg: Fvg, candle: Candle, index: int, max_age: int) -> Fvg:
    if fvg.status in {FvgStatus.EXPIRED, FvgStatus.INVALIDATED, FvgStatus.CONSUMED}:
        return fvg
    if index - fvg.creation_index > max_age:
        fvg.status, fvg.invalidation_timestamp, fvg.invalidation_reason = FvgStatus.EXPIRED, candle.timestamp, "max_age"
        return fvg
    invalid = candle.close < fvg.lower if fvg.direction is Direction.LONG else candle.close > fvg.upper
    if invalid:
        fvg.status, fvg.invalidation_timestamp, fvg.invalidation_reason = FvgStatus.INVALIDATED, candle.timestamp, "close_beyond_far_boundary"
        return fvg
    touched = candle.low <= fvg.upper and candle.high >= fvg.lower
    if touched and index > fvg.creation_index:
        fvg.first_touch_timestamp = fvg.first_touch_timestamp or candle.timestamp
        fvg.status = FvgStatus.RETESTED
    return fvg


def retest_confirmation(candle: Candle, previous_close: Decimal, fvg: Fvg) -> bool:
    if fvg.status is not FvgStatus.RETESTED:
        return False
    if fvg.direction is Direction.LONG:
        return candle.close > candle.open and candle.close > fvg.midpoint and candle.close > previous_close
    return candle.close < candle.open and candle.close < fvg.midpoint and candle.close < previous_close


def structure_break(candle: Candle, prior: Sequence[Candle], direction: Direction) -> bool:
    if not prior:
        return False
    level = max(c.high for c in prior) if direction is Direction.LONG else min(c.low for c in prior)
    return candle.close > level if direction is Direction.LONG else candle.close < level


def smt_divergence(primary: Sequence[Candle], comparison: Sequence[Candle] | None, direction: Direction, lookback: int) -> ComponentResult:
    if not comparison or len(primary) < lookback + 1 or len(comparison) < lookback + 1:
        return ComponentResult("smt", False, {"reason": "missing_or_insufficient_comparison"}, data_quality="missing")
    p_now, c_now = primary[-1], comparison[-1]
    if direction is Direction.LONG:
        passed = p_now.low < min(x.low for x in primary[-lookback - 1 : -1]) and c_now.low >= min(x.low for x in comparison[-lookback - 1 : -1])
    else:
        passed = p_now.high > max(x.high for x in primary[-lookback - 1 : -1]) and c_now.high <= max(x.high for x in comparison[-lookback - 1 : -1])
    return ComponentResult("smt", passed, {"lookback": lookback})


def htf_bias(closes_and_emas: Sequence[tuple[Decimal, Decimal]], direction: Direction) -> bool:
    if not closes_and_emas:
        return False
    return all(close > ema for close, ema in closes_and_emas) if direction is Direction.LONG else all(close < ema for close, ema in closes_and_emas)
