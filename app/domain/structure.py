"""Evidence-based structure labels and order/rejection blocks (closed-candle only)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Sequence

from .models import Candle, Direction
from .signals import confirmed_pivots, structure_break


class StructureLabel(StrEnum):
    BOS = "bos"
    CHOCH = "choch"
    MSS = "mss"
    STRUCTURE_BREAK = "structure_break"


@dataclass(frozen=True)
class StructureEvent:
    label: StructureLabel
    direction: Direction
    level: Decimal
    measurements: dict


@dataclass(frozen=True)
class OrderBlock:
    direction: Direction
    lower: Decimal
    upper: Decimal
    origin_index: int
    kind: str  # order_block | rejection_block
    measurements: dict


def classify_structure_break(
    candle: Candle,
    prior: Sequence[Candle],
    direction: Direction,
    *,
    prior_trend: Direction | None = None,
) -> StructureEvent | None:
    """Refine a raw structure break into BOS / CHoCH / MSS.

    Measurements only — no institutional intent claims.
    - BOS: break in the same direction as prior_trend
    - CHoCH: first break against prior_trend
    - MSS: alias used when prior_trend is unknown but break is confirmed
    """
    if not structure_break(candle, prior, direction):
        return None
    level = max(c.high for c in prior) if direction is Direction.LONG else min(c.low for c in prior)
    if prior_trend is None:
        label = StructureLabel.MSS
    elif prior_trend is direction:
        label = StructureLabel.BOS
    else:
        label = StructureLabel.CHOCH
    return StructureEvent(
        label=label,
        direction=direction,
        level=level,
        measurements={
            "close": str(candle.close),
            "level": str(level),
            "prior_trend": prior_trend.value if prior_trend else None,
            "raw": StructureLabel.STRUCTURE_BREAK.value,
        },
    )


def detect_order_blocks(
    candles: Sequence[Candle],
    *,
    left: int = 2,
    right: int = 2,
    lookback: int = 40,
) -> list[OrderBlock]:
    """Detect order/rejection blocks at the origin of a displacement after a pivot."""
    if len(candles) < left + right + 4:
        return []
    offset = max(0, len(candles) - lookback)
    window = list(candles[offset:])
    highs, lows = confirmed_pivots(window, left, right)
    blocks: list[OrderBlock] = []
    for i in range(left, len(window) - 1):
        candle = window[i]
        nxt = window[i + 1]
        body = abs(candle.close - candle.open)
        next_body = abs(nxt.close - nxt.open)
        if next_body <= body:
            continue
        # Bullish displacement after a low pivot / bearish candle
        if i in lows or candle.close < candle.open:
            if nxt.close > nxt.open and nxt.close > candle.high:
                lower, upper = min(candle.open, candle.close), max(candle.high, candle.open, candle.close)
                kind = "rejection_block" if candle.low < min(candle.open, candle.close) else "order_block"
                blocks.append(OrderBlock(
                    Direction.LONG, lower, upper, offset + i, kind,
                    {"origin_close": str(candle.close), "displacement_close": str(nxt.close)},
                ))
        if i in highs or candle.close > candle.open:
            if nxt.close < nxt.open and nxt.close < candle.low:
                lower, upper = min(candle.low, candle.open, candle.close), max(candle.open, candle.close)
                kind = "rejection_block" if candle.high > max(candle.open, candle.close) else "order_block"
                blocks.append(OrderBlock(
                    Direction.SHORT, lower, upper, offset + i, kind,
                    {"origin_close": str(candle.close), "displacement_close": str(nxt.close)},
                ))
    return blocks


def infer_prior_trend(candles: Sequence[Candle], lookback: int = 10) -> Direction | None:
    if len(candles) < lookback + 1:
        return None
    window = candles[-(lookback + 1):-1]
    higher_highs = window[-1].high > max(c.high for c in window[:-1])
    lower_lows = window[-1].low < min(c.low for c in window[:-1])
    if higher_highs and not lower_lows:
        return Direction.LONG
    if lower_lows and not higher_highs:
        return Direction.SHORT
    return None
