"""Confluence filtration scorecard (research-only; not position-size authority)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from .models import Direction


GATEKEEPER_NAMES = ("minimum_risk_reward", "htf_directional_bias", "session_kill_zone")

# Weights sum to 100. Microstructure is omitted (not faked) until data exists.
CATEGORY_WEIGHTS: dict[str, int] = {
    "multi_timeframe_alignment": 20,
    "market_structure_shift_displacement": 20,
    "volatility_expansion": 15,
    "premium_discount": 15,
    "macro_intermarket": 10,
    "asset_class_specific": 10,
    "order_flow_microstructure": 0,  # skipped — no CVD/footprint feed
}


@dataclass(frozen=True)
class ConfluenceResult:
    rejected: bool
    reject_reasons: tuple[str, ...]
    score: int
    max_score: int
    tier: str | None
    categories: dict[str, Any]
    gatekeepers: dict[str, Any]
    authority: str = "research_only"


def _tier(score: int, rr: Decimal, in_primary_kill_zone: bool) -> str | None:
    if score >= 85 and rr >= Decimal("3") and in_primary_kill_zone:
        return "A+++"
    if score >= 70 and rr >= Decimal("2.5"):
        return "A++"
    if score >= 55 and rr >= Decimal("2"):
        return "A+"
    return None


def evaluate_confluence(
    *,
    direction: Direction,
    risk_reward: Decimal | None,
    htf_bias_passed: bool | None,
    htf_ranging: bool = False,
    in_kill_zone: bool = False,
    structure_shift_passed: bool = False,
    displacement_passed: bool = False,
    volatility_expansion_passed: bool = False,
    premium_discount_favorable: bool = False,
    smt_passed: bool = False,
    asset_class_specific_passed: bool = False,
    kill_zone_penalty: bool = False,
) -> ConfluenceResult:
    """Stage 1 gatekeepers then Stage 2 weighted score using available OHLC evidence only."""
    gates = {
        "minimum_risk_reward": {
            "passed": risk_reward is not None and risk_reward >= Decimal("2"),
            "value": str(risk_reward) if risk_reward is not None else None,
        },
        "htf_directional_bias": {
            "passed": bool(htf_bias_passed) and not htf_ranging,
            "ranging": htf_ranging,
        },
        "session_kill_zone": {
            "passed": in_kill_zone or kill_zone_penalty,
            "in_kill_zone": in_kill_zone,
            "soft_penalty": kill_zone_penalty and not in_kill_zone,
        },
    }
    reject_reasons: list[str] = []
    if not gates["minimum_risk_reward"]["passed"]:
        reject_reasons.append("rr_below_2")
    if not gates["htf_directional_bias"]["passed"]:
        reject_reasons.append("htf_bias_missing_or_ranging")
    # Kill zone: hard reject only when explicitly configured as hard; default soft via score
    rejected = any(r in reject_reasons for r in ("rr_below_2", "htf_bias_missing_or_ranging"))

    categories: dict[str, Any] = {}
    score = 0
    max_score = sum(CATEGORY_WEIGHTS.values())

    def award(name: str, passed: bool, detail: dict | None = None) -> None:
        nonlocal score
        weight = CATEGORY_WEIGHTS[name]
        earned = weight if passed else 0
        score += earned
        categories[name] = {"weight": weight, "earned": earned, "passed": passed, **(detail or {})}

    award("multi_timeframe_alignment", bool(htf_bias_passed) and structure_shift_passed,
          {"direction": direction.value})
    award("market_structure_shift_displacement", structure_shift_passed and displacement_passed)
    award("volatility_expansion", volatility_expansion_passed,
          {"note": "closed-candle proxy only"})
    award("premium_discount", premium_discount_favorable)
    award("macro_intermarket", smt_passed, {"note": "SMT used as intermarket proxy"})
    award("asset_class_specific", asset_class_specific_passed)
    categories["order_flow_microstructure"] = {
        "weight": 0, "earned": 0, "passed": False, "skipped": True,
        "note": "no CVD/footprint feed — not scored",
    }
    if kill_zone_penalty and not in_kill_zone:
        score = max(0, score - 10)
        categories["session_penalty"] = {"earned": -10, "reason": "outside_kill_zone"}

    tier = None if rejected else _tier(
        score, risk_reward or Decimal("0"), in_kill_zone)

    return ConfluenceResult(
        rejected=rejected,
        reject_reasons=tuple(reject_reasons),
        score=score,
        max_score=max_score,
        tier=tier,
        categories=categories,
        gatekeepers=gates,
    )
