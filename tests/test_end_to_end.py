from decimal import Decimal

import pytest

from app.domain.lifecycle import state_for_score
from app.domain.models import ComponentResult, Direction, SetupState
from app.domain.signals import (advance_fvg, detect_fvgs, liquidity_sweep,
                                retest_confirmation, structure_break)


@pytest.mark.parametrize(
    ("direction", "formation", "sweep", "prior_structure", "break_candle", "retest", "previous_close"),
    [
        (Direction.LONG, [(9, 10, 8, 9), (12, 13, 11, 12), (12, 13, 11, 12)],
         (9, 10, 7, 9), [(9, 10, 8, 9), (10, 11, 9, 10)], (10, 12, 9, 11.5),
         (10.4, 11.4, 10.2, 11.2), Decimal("10.5")),
        (Direction.SHORT, [(12, 13, 11, 12), (9, 10, 8, 9), (9, 10, 8, 9)],
         (11, 14, 10, 11), [(11, 13, 10, 12), (10, 12, 9, 11)], (10, 11, 7, 8.5),
         (10.6, 10.8, 9.2, 9.5), Decimal("10.5")),
    ],
)
def test_synthetic_sequence_reaches_eligible(direction, formation, sweep, prior_structure,
                                               break_candle, retest, previous_close,
                                               candle_factory):
    candles = [candle_factory(i, *values) for i, values in enumerate(formation)]
    fvg = next(gap for gap in detect_fvgs(candles, "BTC/USDT", "5m") if gap.direction is direction)
    level = Decimal("8") if direction is Direction.LONG else Decimal("13")
    assert liquidity_sweep(candle_factory(3, *sweep), level, direction)
    prior = [candle_factory(4 + i, *values) for i, values in enumerate(prior_structure)]
    assert structure_break(candle_factory(6, *break_candle), prior, direction)
    reaction = candle_factory(7, *retest)
    advance_fvg(fvg, reaction, 7, 40)
    assert retest_confirmation(reaction, previous_close, fvg)
    components = tuple(ComponentResult(name, True) for name in
                       ("htf_bias", "sweep", "fvg_retest", "retest_confirmation", "smt", "structure"))
    assert sum(item.passed for item in components) == 6
    assert state_for_score(6) is SetupState.ELIGIBLE

