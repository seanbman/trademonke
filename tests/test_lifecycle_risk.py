from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.domain.lifecycle import state_for_score, transition
from app.domain.models import (ComponentResult, Direction, Fvg, Setup, SetupState)
from app.domain.risk import plan_trade, validate_plan


def setup_with_score(score):
    now = datetime.now(timezone.utc)
    return Setup("stable-id", "BTC/USDT", "5m", Direction.LONG, SetupState.DETECTED,
                 tuple(ComponentResult(str(i), i < score) for i in range(6)), now, "v1", "cfg", "sha")


def test_scoring_dedup_identity_and_state_transitions():
    setup = setup_with_score(5)
    assert setup.score == 5 and state_for_score(setup.score) == SetupState.STRONG_WATCH
    transition(setup, SetupState.DEVELOPING, setup.detected_at, "first component")
    transition(setup, SetupState.STRONG_WATCH, setup.detected_at, "score 5")
    assert len(setup.transitions) == 2
    with pytest.raises(ValueError):
        transition(setup, SetupState.OPEN, setup.detected_at, "skip")


def test_stop_target_and_risk_reward_rejection():
    now = datetime.now(timezone.utc)
    fvg = Fvg("f", "BTC/USDT", "5m", Direction.LONG, 1, now, Decimal("99"), Decimal("100"))
    plan = plan_trade(Direction.LONG, Decimal("101"), fvg, Decimal("107"), Decimal("0.1"))
    assert plan.stop == Decimal("98.9")
    assert validate_plan(plan, Decimal("2"))[0]
    rejected = plan_trade(Direction.LONG, Decimal("101"), fvg, Decimal("103"), Decimal("0.1"))
    assert validate_plan(rejected, Decimal("2")) == (False, "minimum_risk_reward")

