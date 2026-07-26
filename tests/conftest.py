from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.domain.models import Candle


@pytest.fixture
def candle_factory():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def make(index, open_, high, low, close, volume="1"):
        return Candle(start + timedelta(minutes=5 * index), *(Decimal(str(x)) for x in (open_, high, low, close, volume)))

    return make

