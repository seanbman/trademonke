from decimal import Decimal

from app.domain.models import Direction, FvgStatus
from app.domain.signals import (advance_fvg, confirmed_pivots, detect_fvgs, htf_bias,
                                liquidity_sweep, retest_confirmation, smt_divergence,
                                structure_break)


def test_bullish_and_bearish_fvg_boundaries(candle_factory):
    bull = [candle_factory(0, 9, 10, 8, 9), candle_factory(1, 12, 13, 11, 12), candle_factory(2, 12, 13, 11, 12)]
    gap = detect_fvgs(bull, "BTC/USDT", "5m")[0]
    assert (gap.direction, gap.lower, gap.upper) == (Direction.LONG, Decimal("10"), Decimal("11"))
    bear = [candle_factory(0, 12, 13, 11, 12), candle_factory(1, 9, 10, 8, 9), candle_factory(2, 9, 10, 8, 9)]
    gap = detect_fvgs(bear, "BTC/USDT", "5m")[0]
    assert (gap.direction, gap.lower, gap.upper) == (Direction.SHORT, Decimal("10"), Decimal("11"))


def test_fvg_retest_partial_fill_invalidation_and_expiry(candle_factory):
    candles = [candle_factory(0, 9, 10, 8, 9), candle_factory(1, 12, 13, 11, 12), candle_factory(2, 12, 13, 11, 12)]
    gap = detect_fvgs(candles, "BTC/USDT", "5m")[0]
    advance_fvg(gap, candle_factory(3, 11.2, 11.5, 10.5, 11.3), 3, 40)
    assert gap.status == FvgStatus.RETESTED
    assert retest_confirmation(candle_factory(4, 10.7, 11.7, 10.4, 11.4), Decimal("11.3"), gap)
    advance_fvg(gap, candle_factory(5, 10.5, 11, 9, 9.5), 5, 40)
    assert gap.status == FvgStatus.INVALIDATED
    second = detect_fvgs(candles, "ETH/USDT", "5m")[0]
    advance_fvg(second, candle_factory(50, 12, 13, 11.5, 12), 50, 40)
    assert second.status == FvgStatus.EXPIRED


def test_sweeps_and_wick_only_structure_break(candle_factory):
    assert liquidity_sweep(candle_factory(1, 10, 11, 8, 10), Decimal("9"), Direction.LONG)
    assert liquidity_sweep(candle_factory(1, 10, 12, 9, 10), Decimal("11"), Direction.SHORT)
    prior = [candle_factory(0, 9, 10, 8, 9), candle_factory(1, 9, 11, 8, 10)]
    assert not structure_break(candle_factory(2, 10, 12, 9, 10.5), prior, Direction.LONG)
    assert structure_break(candle_factory(2, 10, 12, 9, 11.5), prior, Direction.LONG)
    assert structure_break(candle_factory(2, 9, 10, 6, 7), prior, Direction.SHORT)


def test_confirmed_pivots(candle_factory):
    candles = [candle_factory(0, 2, 3, 1, 2), candle_factory(1, 3, 5, 2, 4), candle_factory(2, 2, 4, 0, 1), candle_factory(3, 2, 3, 1, 2)]
    highs, lows = confirmed_pivots(candles)
    assert highs == {1}
    assert lows == {2}


def test_smt_missing_bullish_bearish_and_htf(candle_factory):
    primary = [candle_factory(0, 10, 11, 9, 10), candle_factory(1, 10, 12, 8, 10)]
    comparison = [candle_factory(0, 10, 11, 9, 10), candle_factory(1, 10, 10.5, 9.5, 10)]
    assert smt_divergence(primary, None, Direction.LONG, 1).data_quality == "missing"
    assert smt_divergence(primary, comparison, Direction.LONG, 1).passed
    assert smt_divergence(primary, comparison, Direction.SHORT, 1).passed
    assert htf_bias([(Decimal("2"), Decimal("1"))] * 3, Direction.LONG)
    assert htf_bias([(Decimal("1"), Decimal("2"))] * 3, Direction.SHORT)

