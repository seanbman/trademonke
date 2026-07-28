"""Deterministic chart-annotation geometry helpers (closed-candle only)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from .models import Candle

PRESET_LABELS: tuple[str, ...] = ("LQ", "BSL", "SSL", "BOS", "CHoC", "MSS")
ANNOTATION_KINDS: tuple[str, ...] = ("horizontal", "trendline", "ray", "box")


def interpolate_price(t1: int, p1: Decimal, t2: int, p2: Decimal, t: int) -> Decimal:
    """Linear price along a line at unix time t. Extrapolates for rays."""
    if t1 == t2:
        return p1
    ratio = Decimal(t - t1) / Decimal(t2 - t1)
    return p1 + (p2 - p1) * ratio


def annotation_price_at(geometry: dict[str, Any], kind: str, unix_time: int) -> Decimal | None:
    if kind == "horizontal":
        return Decimal(str(geometry["price"]))
    t1 = int(geometry["t1"])
    t2 = int(geometry["t2"])
    p1 = Decimal(str(geometry["p1"]))
    p2 = Decimal(str(geometry["p2"]))
    if kind == "trendline" and not (min(t1, t2) <= unix_time <= max(t1, t2)):
        return None
    if kind == "ray" and unix_time < min(t1, t2):
        return None
    return interpolate_price(t1, p1, t2, p2, unix_time)


def trendline_break(candle: Candle, geometry: dict[str, Any], kind: str = "trendline") -> dict[str, Any] | None:
    """Detect a closed-candle break of a horizontal/trendline/ray annotation."""
    unix_time = int(candle.timestamp.timestamp())
    level = annotation_price_at(geometry, kind, unix_time)
    if level is None:
        return None
    prior_kind = kind if kind != "horizontal" else "horizontal"
    # Use open as prior side proxy on the same bar: break requires close through level.
    opened_above = candle.open >= level
    closed_above = candle.close > level
    closed_below = candle.close < level
    if opened_above and closed_below:
        return {
            "event_type": "trendline_break",
            "side": "bearish_close_through",
            "level": str(level),
            "close": str(candle.close),
            "kind": prior_kind,
        }
    if (not opened_above) and closed_above:
        return {
            "event_type": "trendline_break",
            "side": "bullish_close_through",
            "level": str(level),
            "close": str(candle.close),
            "kind": prior_kind,
        }
    return None


def zone_break(candle: Candle, geometry: dict[str, Any]) -> dict[str, Any] | None:
    """Detect closed-candle exit through a box/zone boundary."""
    lower = min(Decimal(str(geometry["p1"])), Decimal(str(geometry["p2"])))
    upper = max(Decimal(str(geometry["p1"])), Decimal(str(geometry["p2"])))
    inside_open = lower <= candle.open <= upper
    if not inside_open:
        return None
    if candle.close > upper:
        return {
            "event_type": "zone_break",
            "side": "close_above_zone",
            "lower": str(lower),
            "upper": str(upper),
            "close": str(candle.close),
        }
    if candle.close < lower:
        return {
            "event_type": "zone_break",
            "side": "close_below_zone",
            "lower": str(lower),
            "upper": str(upper),
            "close": str(candle.close),
        }
    return None


def evaluate_annotation_break(kind: str, geometry: dict[str, Any], candle: Candle) -> dict[str, Any] | None:
    if kind in {"horizontal", "trendline", "ray"}:
        return trendline_break(candle, geometry, kind=kind)
    if kind == "box":
        return zone_break(candle, geometry)
    return None


def label_to_event_hint(label: str) -> str:
    """Map preset labels to measured event vocabulary (no intent claims)."""
    normalized = label.strip().upper()
    mapping = {
        "LQ": "liquidity_level",
        "BSL": "buy_side_liquidity",
        "SSL": "sell_side_liquidity",
        "BOS": "structure_break",
        "CHOC": "structure_break",
        "MSS": "structure_break",
    }
    return mapping.get(normalized.replace("CHOCH", "CHOC"), "annotation_break")
