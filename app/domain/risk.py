from dataclasses import dataclass
from decimal import Decimal

from .models import Direction, Fvg


@dataclass(frozen=True)
class TradePlan:
    entry: Decimal
    stop: Decimal
    target: Decimal
    risk_reward: Decimal


@dataclass(frozen=True)
class RiskLimits:
    account_risk_fraction: Decimal = Decimal("0.005")
    minimum_risk_reward: Decimal = Decimal("2")
    maximum_spread_bps: Decimal = Decimal("30")
    maximum_slippage_bps: Decimal = Decimal("20")
    maximum_notional: Decimal = Decimal("1000")
    minimum_notional: Decimal = Decimal("10")


@dataclass(frozen=True)
class RiskDecision:
    approved: bool
    reason_codes: tuple[str, ...]
    quantity: Decimal
    notional: Decimal
    risk_amount: Decimal


def evaluate_risk(direction: Direction, entry: Decimal, stop: Decimal, target: Decimal,
                  account_balance: Decimal, spread_bps: Decimal, slippage_bps: Decimal,
                  limits: RiskLimits, controls_clear: bool = True) -> RiskDecision:
    reasons = []
    risk_per_unit = entry - stop if direction is Direction.LONG else stop - entry
    reward_per_unit = target - entry if direction is Direction.LONG else entry - target
    if risk_per_unit <= 0:
        reasons.append("invalid_stop_side")
    if reward_per_unit <= 0:
        reasons.append("invalid_target_side")
    rr = reward_per_unit / risk_per_unit if risk_per_unit > 0 else Decimal("0")
    if rr < limits.minimum_risk_reward:
        reasons.append("minimum_risk_reward")
    if spread_bps > limits.maximum_spread_bps:
        reasons.append("spread_limit")
    if slippage_bps > limits.maximum_slippage_bps:
        reasons.append("slippage_limit")
    if not controls_clear:
        reasons.append("control_state_blocks_risk")
    risk_amount = account_balance * limits.account_risk_fraction
    quantity = risk_amount / risk_per_unit if risk_per_unit > 0 else Decimal("0")
    notional = quantity * entry
    if notional > limits.maximum_notional and entry > 0:
        notional = limits.maximum_notional
        quantity = notional / entry
        risk_amount = quantity * max(risk_per_unit, Decimal("0"))
    if notional < limits.minimum_notional:
        reasons.append("minimum_notional")
    return RiskDecision(not reasons, tuple(reasons), quantity, notional, risk_amount)


def plan_trade(direction: Direction, entry: Decimal, fvg: Fvg, target: Decimal, tick: Decimal, sweep_extreme: Decimal | None = None, atr_buffer: Decimal = Decimal("0"), stop_model: str = "fvg_boundary") -> TradePlan:
    if stop_model == "fvg_boundary":
        stop = fvg.lower - tick if direction is Direction.LONG else fvg.upper + tick
    elif stop_model == "sweep_extreme_atr_buffer" and sweep_extreme is not None:
        stop = sweep_extreme - atr_buffer if direction is Direction.LONG else sweep_extreme + atr_buffer
    else:
        raise ValueError("invalid stop model or missing sweep extreme")
    risk = entry - stop if direction is Direction.LONG else stop - entry
    reward = target - entry if direction is Direction.LONG else entry - target
    if risk <= 0 or reward <= 0:
        raise ValueError("stop or target is on the wrong side of entry")
    return TradePlan(entry, stop, target, reward / risk)


def validate_plan(plan: TradePlan, minimum_rr: Decimal) -> tuple[bool, str | None]:
    return (False, "minimum_risk_reward") if plan.risk_reward < minimum_rr else (True, None)
