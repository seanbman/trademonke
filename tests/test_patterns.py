from decimal import Decimal

from app.domain.patterns import detect_patterns


def _zigzag(candle_factory, highs: list[float], lows: list[float]):
    candles = []
    index = 0
    for high, low in zip(highs, lows, strict=True):
        candles.append(candle_factory(index, low + 0.5, low + 1, low, low + 0.6))
        index += 1
        candles.append(candle_factory(index, low + 1, (low + high) / 2 + 1, low + 0.8, (low + high) / 2))
        index += 1
        candles.append(candle_factory(index, high - 1, high, high - 1.5, high - 0.8))
        index += 1
        candles.append(candle_factory(index, high - 1.2, high - 0.5, (low + high) / 2, (low + high) / 2))
        index += 1
    return candles


def test_detect_rising_wedge_soft_label(candle_factory):
    candles = _zigzag(candle_factory, [20, 21, 21.5], [10, 14, 17])
    patterns = detect_patterns(candles, left=1, right=1)
    types = {item.pattern_type for item in patterns}
    assert "rising_wedge" in types
    wedge = next(item for item in patterns if item.pattern_type == "rising_wedge")
    payload = wedge.to_chart_dict()
    assert payload["soft_label"] is True
    assert payload["authority"] == "none"
    assert wedge.status in {"confirmed_shape", "broken"}


def test_detect_ascending_triangle(candle_factory):
    candles = _zigzag(candle_factory, [22, 22, 22], [12, 15, 18])
    patterns = detect_patterns(candles, left=1, right=1)
    assert any(item.pattern_type == "ascending_triangle" for item in patterns)


def test_detect_double_top(candle_factory):
    series = [
        (10, 11, 9, 10),
        (10, 12, 9.5, 11),
        (11, 20, 11, 18),
        (17, 18, 14, 15),
        (14, 15, 10, 11),
        (11, 14, 11, 13),
        (13, 20, 13, 18),
        (17, 18, 14, 15),
        (14, 15, 12, 13),
    ]
    candles = [candle_factory(i, *ohlc) for i, ohlc in enumerate(series)]
    patterns = detect_patterns(candles, left=1, right=1, equal_tolerance_bps=Decimal("30"))
    top = next(item for item in patterns if item.pattern_type == "double_top")
    assert top.status == "confirmed_shape"
    assert top.direction_hint == "short"


def test_detect_falling_wedge(candle_factory):
    candles = _zigzag(candle_factory, [30, 26, 23], [20, 18, 17])
    patterns = detect_patterns(candles, left=1, right=1)
    assert any(item.pattern_type == "falling_wedge" for item in patterns)


def test_patterns_need_enough_history(candle_factory):
    short = [candle_factory(i, 10, 11, 9, 10) for i in range(4)]
    assert detect_patterns(short) == []
