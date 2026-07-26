from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from .models import Candle, Direction


class EpisodeState(StrEnum):
    OBSERVED = "observed"
    SWEPT = "swept"
    RECLAIMED = "reclaimed"
    DISPLACED = "displaced"
    IMBALANCE_CREATED = "imbalance_created"
    RETESTED = "retested"
    ARMED = "armed"
    APPROVED = "approved"
    ACCEPTED_BREAKOUT = "accepted_breakout"
    FAILED_RECOVERY = "failed_recovery"
    INVALIDATED = "invalidated"
    EXPIRED = "expired"


TERMINAL_EPISODE_STATES = {
    EpisodeState.ACCEPTED_BREAKOUT, EpisodeState.FAILED_RECOVERY,
    EpisodeState.INVALIDATED, EpisodeState.EXPIRED,
}


@dataclass(frozen=True)
class EpisodeDecision:
    next_state: EpisodeState
    reason_codes: tuple[str, ...]
    measurements: dict


def classify_recovery(direction: Direction, level: Decimal, candle: Candle) -> EpisodeDecision:
    reclaimed = candle.close > level if direction is Direction.LONG else candle.close < level
    if reclaimed:
        return EpisodeDecision(EpisodeState.RECLAIMED, ("close_reclaimed_level",),
                               {"close": str(candle.close), "level": str(level)})
    return EpisodeDecision(EpisodeState.FAILED_RECOVERY, ("close_failed_reclaim",),
                           {"close": str(candle.close), "level": str(level)})


def classify_displacement(direction: Direction, candle: Candle,
                          minimum_body_bps: Decimal) -> EpisodeDecision | None:
    body = abs(candle.close - candle.open)
    reference = candle.open if candle.open else Decimal("1")
    body_bps = body / reference * Decimal("10000")
    directional = candle.close > candle.open if direction is Direction.LONG else candle.close < candle.open
    if directional and body_bps >= minimum_body_bps:
        return EpisodeDecision(EpisodeState.DISPLACED, ("directional_body_threshold",),
                               {"body_bps": str(body_bps),
                                "minimum_body_bps": str(minimum_body_bps)})
    return None


def zone_retested(direction: Direction, lower: Decimal, upper: Decimal,
                  candle: Candle) -> bool:
    overlaps = candle.low <= upper and candle.high >= lower
    confirms = candle.close >= (lower + upper) / 2 if direction is Direction.LONG else candle.close <= (lower + upper) / 2
    return overlaps and confirms
