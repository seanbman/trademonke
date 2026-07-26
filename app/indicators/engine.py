from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.lifecycle import state_for_score
from app.domain.models import Candle, Direction, FvgStatus
from app.domain.signals import (advance_fvg, confirmed_pivots, detect_fvgs,
                                htf_bias, liquidity_sweep,
                                retest_confirmation, smt_divergence,
                                structure_break)
from app.telemetry.models import (CandleRecord, IndicatorAlertEventRecord,
                                  IndicatorSnapshotRecord)

COMPONENT_NAMES = ("htf_bias", "liquidity_sweep", "fvg_retest",
                   "retest_confirmation", "smt", "structure")


def ema(values: list[Decimal], length: int) -> Decimal | None:
    if len(values) < length:
        return None
    alpha = Decimal("2") / Decimal(length + 1)
    result = values[0]
    for value in values[1:]:
        result = value * alpha + result * (Decimal("1") - alpha)
    return result


class IndicatorEngine:
    def __init__(self, session_factory, exchange: str, strategy_version: str,
                 base_timeframe: str = "5m", htf_timeframes: tuple[str, ...] = ("15m", "30m", "1h", "4h", "1d"),
                 ema_length: int = 50, structure_lookback: int = 10, smt_lookback: int = 10,
                 pivot_lookback: int = 30, fvg_max_age: int = 40,
                 comparison_symbols: tuple[str, str] = ("BTC/USDT", "ETH/USDT")):
        self.session_factory = session_factory
        self.exchange = exchange
        self.strategy_version = strategy_version
        self.base_timeframe = base_timeframe
        self.htf_timeframes = htf_timeframes
        self.ema_length = ema_length
        self.structure_lookback = structure_lookback
        self.smt_lookback = smt_lookback
        self.pivot_lookback = pivot_lookback
        self.fvg_max_age = fvg_max_age
        self.comparison_symbols = comparison_symbols

    def _candles(self, session: Session, symbol: str, timeframe: str, limit: int = 250) -> list[Candle]:
        records = list(session.scalars(select(CandleRecord).where(
            CandleRecord.exchange == self.exchange, CandleRecord.symbol == symbol,
            CandleRecord.timeframe == timeframe, CandleRecord.closed.is_(True)
        ).order_by(CandleRecord.timestamp.desc()).limit(limit)))
        records.reverse()
        return [Candle(r.timestamp if r.timestamp.tzinfo else r.timestamp.replace(tzinfo=timezone.utc),
                       r.open, r.high, r.low, r.close, r.volume) for r in records]

    def evaluate_symbol(self, symbol: str) -> list[IndicatorSnapshotRecord]:
        with self.session_factory() as session:
            base = self._candles(session, symbol, self.base_timeframe)
            if len(base) < 15:
                return []
            htf = {}
            for timeframe in self.htf_timeframes:
                candles = self._candles(session, symbol, timeframe)
                average = ema([c.close for c in candles], self.ema_length)
                htf[timeframe] = (candles[-1].close, average) if candles and average is not None else None
            comparison_symbol = self._comparison_for(symbol)
            comparison = self._candles(session, comparison_symbol, self.base_timeframe, 30) if comparison_symbol else []
            snapshots = [self._evaluate_direction(session, symbol, base, comparison, htf, direction)
                         for direction in (Direction.LONG, Direction.SHORT)]
            session.commit()
            return [snapshot for snapshot in snapshots if snapshot is not None]

    def _comparison_for(self, symbol: str) -> str | None:
        first, second = self.comparison_symbols
        if symbol == first:
            return second
        return first if symbol != first else second

    def _evaluate_direction(self, session: Session, symbol: str, candles: list[Candle],
                            comparison: list[Candle], htf: dict,
                            direction: Direction) -> IndicatorSnapshotRecord | None:
        current = candles[-1]
        existing = session.scalar(select(IndicatorSnapshotRecord.id).where(
            IndicatorSnapshotRecord.exchange == self.exchange,
            IndicatorSnapshotRecord.symbol == symbol,
            IndicatorSnapshotRecord.timeframe == self.base_timeframe,
            IndicatorSnapshotRecord.candle_timestamp == current.timestamp,
            IndicatorSnapshotRecord.direction == direction.value))
        if existing:
            return None
        aligned_values = [value for value in htf.values() if value is not None]
        bias = len(aligned_values) == len(self.htf_timeframes) and htf_bias(aligned_values, direction)
        sweep, sweep_level = self._sweep(candles, direction)
        fvg, inside, confirmation = self._fvg_state(candles, symbol, direction)
        smt = smt_divergence(candles[-self.smt_lookback - 1:],
                             comparison[-self.smt_lookback - 1:] if comparison else None,
                             direction, self.smt_lookback)
        structure = structure_break(current, candles[-self.structure_lookback - 1:-1], direction)
        components = {
            "htf_bias": {"passed": bias, "values": {key: ({"close": str(value[0]), "ema50": str(value[1])} if value else None) for key, value in htf.items()}},
            "liquidity_sweep": {"passed": sweep, "level": str(sweep_level) if sweep_level else None},
            "fvg_retest": {"passed": inside, "zone": ({"lower": str(fvg.lower), "upper": str(fvg.upper), "status": fvg.status.value} if fvg else None)},
            "retest_confirmation": {"passed": confirmation},
            "smt": {"passed": smt.passed, "comparison": self._comparison_for(symbol), "data_quality": smt.data_quality},
            "structure": {"passed": structure, "lookback": self.structure_lookback},
        }
        score = sum(bool(components[name]["passed"]) for name in COMPONENT_NAMES)
        state = state_for_score(score).value
        previous = session.scalar(select(IndicatorSnapshotRecord).where(
            IndicatorSnapshotRecord.exchange == self.exchange,
            IndicatorSnapshotRecord.symbol == symbol,
            IndicatorSnapshotRecord.timeframe == self.base_timeframe,
            IndicatorSnapshotRecord.direction == direction.value
        ).order_by(IndicatorSnapshotRecord.candle_timestamp.desc()).limit(1))
        snapshot = IndicatorSnapshotRecord(
            exchange=self.exchange, symbol=symbol, timeframe=self.base_timeframe,
            candle_timestamp=current.timestamp, evaluated_at=datetime.now(timezone.utc),
            direction=direction.value, score=score, setup_state=state,
            components=components, strategy_version=self.strategy_version,
        )
        session.add(snapshot)
        session.flush()
        if previous:
            self._record_changes(session, previous, snapshot)
        return snapshot

    def _sweep(self, candles: list[Candle], direction: Direction):
        window = candles[-self.pivot_lookback:-1]
        highs, lows = confirmed_pivots(window)
        candidates = lows if direction is Direction.LONG else highs
        if not candidates:
            return False, None
        local = max(candidates)
        pivot = window[local]
        level = pivot.low if direction is Direction.LONG else pivot.high
        return liquidity_sweep(candles[-1], level, direction), level

    def _fvg_state(self, candles: list[Candle], symbol: str, direction: Direction):
        gaps = [gap for gap in detect_fvgs(candles, symbol, self.base_timeframe) if gap.direction is direction]
        for gap in reversed(gaps):
            for index in range(gap.creation_index + 1, len(candles)):
                advance_fvg(gap, candles[index], index, self.fvg_max_age)
            if gap.status not in {FvgStatus.INVALIDATED, FvgStatus.EXPIRED, FvgStatus.CONSUMED}:
                inside = gap.status is FvgStatus.RETESTED
                confirmed = inside and retest_confirmation(candles[-1], candles[-2].close, gap)
                return gap, inside, confirmed
        return None, False, False

    def _record_changes(self, session: Session, previous: IndicatorSnapshotRecord,
                        current: IndicatorSnapshotRecord) -> None:
        for name in COMPONENT_NAMES:
            old = bool(previous.components.get(name, {}).get("passed"))
            new = bool(current.components.get(name, {}).get("passed"))
            if old != new:
                self._event(session, current, "component_change", name, str(old), str(new),
                            f"{current.symbol} {current.direction}: {name} {'ON' if new else 'OFF'}; score {current.score}/6")
        if previous.score != current.score:
            self._event(session, current, "score_change", "score", str(previous.score), str(current.score),
                        f"{current.symbol} {current.direction}: score {previous.score}/6 → {current.score}/6")
        if previous.setup_state != current.setup_state:
            self._event(session, current, "state_change", "setup_state", previous.setup_state, current.setup_state,
                        f"{current.symbol} {current.direction}: state {previous.setup_state} → {current.setup_state}; score {current.score}/6")

    def _event(self, session: Session, snapshot: IndicatorSnapshotRecord, event_type: str,
               component: str, old_value: str, new_value: str, message: str) -> None:
        event_id = (f"indicator:{snapshot.exchange}:{snapshot.symbol}:{snapshot.timeframe}:"
                    f"{snapshot.candle_timestamp.isoformat()}:{snapshot.direction}:{event_type}:{component}")
        session.add(IndicatorAlertEventRecord(
            event_id=event_id, exchange=snapshot.exchange, symbol=snapshot.symbol,
            timeframe=snapshot.timeframe, candle_timestamp=snapshot.candle_timestamp,
            direction=snapshot.direction, event_type=event_type, component=component,
            old_value=old_value, new_value=new_value, score=snapshot.score,
            message=message, created_at=datetime.now(timezone.utc), delivered_at=None,
        ))
