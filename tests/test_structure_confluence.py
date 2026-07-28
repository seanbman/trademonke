from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.domain.confluence import evaluate_confluence
from app.domain.ifvg import detect_ifvg_links, fvg_forms_after_displacement, observe_v_recovery
from app.domain.models import Candle, Direction
from app.domain.sessions import dealing_range, in_kill_zone, premium_discount_position
from app.domain.signals import detect_fvgs
from app.domain.structure import (
    StructureLabel,
    classify_structure_break,
    detect_order_blocks,
    infer_prior_trend,
)


def _candles(factory_prices):
    start = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
    out = []
    for i, (open_, high, low, close) in enumerate(factory_prices):
        out.append(Candle(
            start + timedelta(minutes=5 * i),
            *(Decimal(str(x)) for x in (open_, high, low, close)),
        ))
    return out


def test_structure_labels_and_order_blocks():
    prices = [(10, 11, 9, 10)] * 12
    prices += [(10, 12, 10, 11.5), (11.5, 13, 11.4, 12.8)]
    candles = _candles(prices)
    prior = candles[:-1]
    event = classify_structure_break(
        candles[-1], prior[-10:], Direction.LONG, prior_trend=Direction.SHORT)
    assert event is not None
    assert event.label is StructureLabel.CHOCH
    blocks = detect_order_blocks(candles)
    assert isinstance(blocks, list)
    assert infer_prior_trend(candles) in {None, Direction.LONG, Direction.SHORT}


def test_ifvg_v_recovery_and_fvg_timing_fixture():
    # Bullish FVG: recent.low > older.high on detection index i
    prices = [
        (100, 101, 99, 100),   # i-2 older
        (102, 103, 102, 102.5),  # i-1 recent — low 102 > older high 101
        (103, 104, 102.5, 103.5),  # i detection candle
        (103.5, 105, 103, 104),
        (104, 104.5, 100, 100.5),  # start opposite
        (100.5, 101, 98, 99),      # bearish gap candidate vs prior
        (99, 99.5, 97, 98),
    ]
    candles = _candles(prices)
    fvgs = detect_fvgs(candles, "BTC/USDT", "5m")
    assert fvgs
    assert fvg_forms_after_displacement(fvgs[0], displacement_index=0)
    links = detect_ifvg_links(candles, "BTC/USDT", "5m")
    assert isinstance(links, list)
    sweep_prices = [(100, 101, 99, 100)] * 5 + [(100, 100.5, 95, 96), (96, 102, 96, 101)]
    sweep_candles = _candles(sweep_prices)
    obs = observe_v_recovery(sweep_candles, Decimal("100"), Direction.LONG, sweep_index=5)
    assert obs is not None
    assert obs.reclaim_index > obs.sweep_index


def test_sessions_and_confluence_scorecard():
    ts = datetime(2026, 1, 1, 13, 0, tzinfo=timezone.utc)
    kz = in_kill_zone(ts, "crypto")
    assert kz["in_kill_zone"] is True
    # Explicit swing high then swing low pivots with left=right=1
    prices = [
        (100, 101, 99, 100),
        (100, 120, 100, 119),  # pivot high candidate
        (119, 119.5, 118, 118.5),
        (118.5, 119, 117, 117.5),
        (117.5, 118, 80, 81),  # pivot low candidate
        (81, 90, 80, 89),
        (89, 95, 88, 94),
        (94, 96, 93, 95),
    ]
    candles = _candles(prices)
    range_ = dealing_range(candles, left=1, right=1)
    assert range_ is not None
    pos = premium_discount_position(Decimal("85"), range_, Direction.LONG)
    assert pos["favorable_for_direction"] is True
    result = evaluate_confluence(
        direction=Direction.LONG,
        risk_reward=Decimal("2.5"),
        htf_bias_passed=True,
        in_kill_zone=True,
        structure_shift_passed=True,
        displacement_passed=True,
        volatility_expansion_passed=True,
        premium_discount_favorable=True,
        smt_passed=True,
        asset_class_specific_passed=True,
    )
    assert not result.rejected
    assert result.score > 0
    assert result.authority == "research_only"
    assert result.categories["order_flow_microstructure"]["skipped"] is True
    rejected = evaluate_confluence(
        direction=Direction.LONG,
        risk_reward=Decimal("1.2"),
        htf_bias_passed=False,
        htf_ranging=True,
    )
    assert rejected.rejected
    assert "rr_below_2" in rejected.reject_reasons
