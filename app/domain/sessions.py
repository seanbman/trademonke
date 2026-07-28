"""Session/kill-zone windows and premium/discount dealing-range measurements."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timezone
from decimal import Decimal
from typing import Sequence
from zoneinfo import ZoneInfo

from .models import Candle, Direction
from .signals import confirmed_pivots


UTC = ZoneInfo("UTC")


@dataclass(frozen=True)
class KillZone:
    name: str
    start: time
    end: time
    tz: str = "UTC"


# Deterministic UTC windows (asset-class overlays can remap via config later)
DEFAULT_KILL_ZONES: dict[str, tuple[KillZone, ...]] = {
    "crypto": (
        KillZone("asia", time(0, 0), time(8, 0)),
        KillZone("london", time(7, 0), time(11, 0)),
        KillZone("new_york", time(12, 0), time(16, 0)),
    ),
    "forex": (
        KillZone("london", time(7, 0), time(11, 0)),
        KillZone("new_york", time(12, 0), time(16, 0)),
        KillZone("london_ny_overlap", time(12, 0), time(16, 0)),
    ),
    "default": (
        KillZone("london", time(7, 0), time(11, 0)),
        KillZone("new_york", time(12, 0), time(16, 0)),
    ),
}


def _aware(ts: datetime) -> datetime:
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


def in_kill_zone(ts: datetime, asset_class: str = "crypto", zone_name: str | None = None) -> dict:
    zones = DEFAULT_KILL_ZONES.get(asset_class, DEFAULT_KILL_ZONES["default"])
    moment = _aware(ts).astimezone(UTC).time()
    matched = []
    for zone in zones:
        if zone.start <= zone.end:
            inside = zone.start <= moment < zone.end
        else:  # wraps midnight
            inside = moment >= zone.start or moment < zone.end
        if inside and (zone_name is None or zone.name == zone_name):
            matched.append(zone.name)
    return {
        "in_kill_zone": bool(matched),
        "zones": matched,
        "asset_class": asset_class,
        "timestamp": _aware(ts).isoformat(),
    }


@dataclass(frozen=True)
class DealingRange:
    high: Decimal
    low: Decimal
    equilibrium: Decimal
    premium_lower: Decimal
    discount_upper: Decimal


def dealing_range(candles: Sequence[Candle], left: int = 2, right: int = 2) -> DealingRange | None:
    if len(candles) < left + right + 3:
        return None
    highs, lows = confirmed_pivots(candles, left, right)
    if highs and lows:
        high = max(candles[i].high for i in highs)
        low = min(candles[i].low for i in lows)
    else:
        # Fallback research measurement: closed-window extremes when pivots are sparse
        window = candles[-(left + right + 10):] if len(candles) > left + right + 10 else candles
        high = max(c.high for c in window)
        low = min(c.low for c in window)
    if high <= low:
        return None
    mid = (high + low) / Decimal("2")
    return DealingRange(
        high=high,
        low=low,
        equilibrium=mid,
        premium_lower=mid,
        discount_upper=mid,
    )


def premium_discount_position(price: Decimal, range_: DealingRange, direction: Direction) -> dict:
    """Longs prefer discount (price <= eq); shorts prefer premium (price >= eq)."""
    in_discount = price <= range_.equilibrium
    in_premium = price >= range_.equilibrium
    favorable = in_discount if direction is Direction.LONG else in_premium
    return {
        "price": str(price),
        "equilibrium": str(range_.equilibrium),
        "range_high": str(range_.high),
        "range_low": str(range_.low),
        "in_discount": in_discount,
        "in_premium": in_premium,
        "favorable_for_direction": favorable,
        "direction": direction.value,
    }
