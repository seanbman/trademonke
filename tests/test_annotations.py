from datetime import datetime, timezone
from decimal import Decimal

from app.domain.annotations import (
    evaluate_annotation_break,
    interpolate_price,
    label_to_event_hint,
)
from app.domain.models import Candle


def test_interpolate_and_horizontal_break():
    candle = Candle(
        datetime(2026, 1, 1, 12, tzinfo=timezone.utc),
        Decimal("100"), Decimal("101"), Decimal("90"), Decimal("91"),
    )
    assert evaluate_annotation_break(
        "horizontal", {"price": "95"}, candle,
    )["side"] == "bearish_close_through"
    assert interpolate_price(0, Decimal("10"), 10, Decimal("20"), 5) == Decimal("15")


def test_zone_break_and_label_hints():
    candle = Candle(
        datetime(2026, 1, 1, 12, tzinfo=timezone.utc),
        Decimal("100"), Decimal("110"), Decimal("99"), Decimal("111"),
    )
    result = evaluate_annotation_break(
        "box", {"p1": "95", "p2": "105", "t1": 1, "t2": 2}, candle,
    )
    assert result["event_type"] == "zone_break"
    assert label_to_event_hint("BSL") == "buy_side_liquidity"
    assert label_to_event_hint("CHoC") == "structure_break"
