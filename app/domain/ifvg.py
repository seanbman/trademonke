"""IFVG and V-recovery research observations (not execution authority)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence

from .models import Candle, Direction, Fvg
from .signals import detect_fvgs


@dataclass(frozen=True)
class InverseFvgLink:
    original_fvg_id: str
    inverse_fvg_id: str
    direction: Direction
    measurements: dict


@dataclass(frozen=True)
class VRecoveryObservation:
    direction: Direction
    sweep_index: int
    reclaim_index: int
    measurements: dict


def detect_ifvg_links(
    candles: Sequence[Candle],
    pair: str,
    timeframe: str,
    *,
    max_age: int = 40,
) -> list[InverseFvgLink]:
    """Link an original FVG to a later opposite-direction FVG that overlaps it.

    Research-only: does not arm trades or alter mandatory gates.
    """
    fvgs = detect_fvgs(candles, pair, timeframe)
    links: list[InverseFvgLink] = []
    for i, original in enumerate(fvgs):
        for later in fvgs[i + 1:]:
            if later.creation_index - original.creation_index > max_age:
                break
            if later.direction is original.direction:
                continue
            overlaps = later.lower <= original.upper and later.upper >= original.lower
            if not overlaps:
                continue
            links.append(InverseFvgLink(
                original_fvg_id=original.id,
                inverse_fvg_id=later.id,
                direction=later.direction,
                measurements={
                    "original_zone": {"lower": str(original.lower), "upper": str(original.upper)},
                    "inverse_zone": {"lower": str(later.lower), "upper": str(later.upper)},
                    "original_creation_index": original.creation_index,
                    "inverse_creation_index": later.creation_index,
                    "authority": "research_only",
                },
            ))
    return links


def observe_v_recovery(
    candles: Sequence[Candle],
    level: Decimal,
    direction: Direction,
    *,
    sweep_index: int,
) -> VRecoveryObservation | None:
    """Observe a V-shaped reclaim after a sweep index (closed candles after displacement)."""
    if sweep_index < 0 or sweep_index >= len(candles) - 1:
        return None
    for j in range(sweep_index + 1, len(candles)):
        candle = candles[j]
        reclaimed = candle.close > level if direction is Direction.LONG else candle.close < level
        if not reclaimed:
            continue
        # Simple V shape: intervening extreme beyond level then reclaim
        window = candles[sweep_index:j + 1]
        if direction is Direction.LONG:
            extreme = min(c.low for c in window)
            shaped = extreme < level
        else:
            extreme = max(c.high for c in window)
            shaped = extreme > level
        if not shaped:
            return None
        return VRecoveryObservation(
            direction=direction,
            sweep_index=sweep_index,
            reclaim_index=j,
            measurements={
                "level": str(level),
                "extreme": str(extreme),
                "reclaim_close": str(candle.close),
                "authority": "research_only",
            },
        )
    return None


def fvg_forms_after_displacement(fvg: Fvg, displacement_index: int) -> bool:
    """Golden audit helper: imbalance creation must be at/after displacement."""
    return fvg.creation_index >= displacement_index


def research_stream_id(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:24]
