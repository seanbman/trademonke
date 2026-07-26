from __future__ import annotations

import hashlib
from datetime import timezone
from decimal import Decimal

from sqlalchemy import select

from app.domain.liquidity import (LevelEventType, LevelSide, classify_level_candle,
                                  detect_confirmed_levels)
from app.domain.models import Candle
from app.settings import get_settings
from app.telemetry.models import (CandleRecord, LiquidityLevelEventRecord,
                                  LiquidityLevelRecord)


class LiquidityMapService:
    def __init__(self, session_factory, exchange: str, strategy_version: str, git_sha: str,
                 left: int = 2, right: int = 2, tolerance_bps: Decimal = Decimal("5"),
                 touch_tolerance_bps: Decimal = Decimal("2"), expiry_candles: int = 500):
        self.session_factory = session_factory
        self.exchange = exchange
        self.strategy_version = strategy_version
        self.git_sha = git_sha
        self.left = left
        self.right = right
        self.tolerance_bps = tolerance_bps
        self.touch_tolerance_bps = touch_tolerance_bps
        self.expiry_candles = expiry_candles

    def update(self, symbol: str, timeframe: str) -> int:
        with self.session_factory() as session:
            rows = list(session.scalars(select(CandleRecord).where(
                CandleRecord.exchange == self.exchange, CandleRecord.symbol == symbol,
                CandleRecord.timeframe == timeframe, CandleRecord.closed.is_(True)
            ).order_by(CandleRecord.timestamp.desc()).limit(self.expiry_candles + 20)))
            rows.reverse()
            if len(rows) < self.left + self.right + 1:
                return 0
            candles = [Candle(self._aware(row.timestamp), row.open, row.high, row.low,
                              row.close, row.volume) for row in rows]
            changes = self._persist_new_levels(session, symbol, timeframe, candles)
            changes += self._expire_levels(session, symbol, timeframe, candles)
            changes += self._advance_levels(session, symbol, timeframe, candles[-1])
            session.commit()
            return changes

    def _persist_new_levels(self, session, symbol: str, timeframe: str,
                            candles: list[Candle]) -> int:
        changes = 0
        for level in detect_confirmed_levels(candles, self.left, self.right, self.tolerance_bps):
            pivot = candles[level.pivot_index]
            level_id = self._level_id(symbol, timeframe, level.side, pivot.timestamp, level.price)
            if session.get(LiquidityLevelRecord, level_id):
                continue
            observed = candles[level.confirmed_index].timestamp
            record = LiquidityLevelRecord(
                id=level_id, exchange=self.exchange, symbol=symbol, timeframe=timeframe,
                direction="short" if level.side is LevelSide.HIGH else "long",
                level_type="equal_high" if level.side is LevelSide.HIGH and level.cluster_size > 1
                else "equal_low" if level.cluster_size > 1 else f"swing_{level.side.value}",
                price=level.price, status="active", observed_at=observed, updated_at=observed,
                measurements={"side": level.side.value, "cluster_size": level.cluster_size,
                              "pivot_timestamp": pivot.timestamp.isoformat(), "touch_count": 0,
                              "tolerance_bps": str(self.tolerance_bps)},
                strategy_version=self.strategy_version, config_hash=get_settings().config_hash, git_sha=self.git_sha)
            session.add(record)
            # Persist the FK parent before an event or a later lookup can trigger autoflush.
            session.flush()
            self._event(session, record, "level_created", observed,
                        ["confirmed_pivot"], {"cluster_size": level.cluster_size})
            changes += 1
        return changes

    def _advance_levels(self, session, symbol: str, timeframe: str, candle: Candle) -> int:
        changes = 0
        levels = list(session.scalars(select(LiquidityLevelRecord).where(
            LiquidityLevelRecord.exchange == self.exchange,
            LiquidityLevelRecord.symbol == symbol, LiquidityLevelRecord.timeframe == timeframe,
            LiquidityLevelRecord.status == "active")))
        for level in levels:
            if candle.timestamp <= self._aware(level.observed_at):
                continue
            side = LevelSide(level.measurements["side"])
            event_type = classify_level_candle(side, level.price, candle,
                                               self.touch_tolerance_bps)
            if event_type is None:
                continue
            event_id = f"level:{level.id}:{candle.timestamp.isoformat()}:{event_type.value}"
            if session.scalar(select(LiquidityLevelEventRecord.id).where(
                    LiquidityLevelEventRecord.event_id == event_id)):
                continue
            measurements = dict(level.measurements)
            if event_type is LevelEventType.TOUCH:
                measurements["touch_count"] = int(measurements.get("touch_count", 0)) + 1
            else:
                level.status = "swept" if event_type is LevelEventType.SWEPT else "accepted_breakout"
            level.measurements = measurements
            level.updated_at = candle.timestamp
            self._event(session, level, event_type.value, candle.timestamp,
                        [event_type.value], {"close": str(candle.close)})
            changes += 1
        return changes

    def _expire_levels(self, session, symbol: str, timeframe: str,
                       candles: list[Candle]) -> int:
        if len(candles) <= self.expiry_candles:
            return 0
        cutoff = candles[-self.expiry_candles].timestamp
        current = candles[-1].timestamp
        levels = list(session.scalars(select(LiquidityLevelRecord).where(
            LiquidityLevelRecord.exchange == self.exchange,
            LiquidityLevelRecord.symbol == symbol, LiquidityLevelRecord.timeframe == timeframe,
            LiquidityLevelRecord.status == "active",
            LiquidityLevelRecord.observed_at < cutoff)))
        for level in levels:
            level.status = "expired"
            level.updated_at = current
            self._event(session, level, "level_expired", current,
                        ["maximum_age_exceeded"], {"expiry_candles": self.expiry_candles})
        return len(levels)

    def _event(self, session, level, event_type, timestamp, reasons, measurements):
        session.add(LiquidityLevelEventRecord(
            event_id=f"level:{level.id}:{timestamp.isoformat()}:{event_type}",
            liquidity_level_id=level.id, event_type=event_type, occurred_at=timestamp,
            candle_timestamp=timestamp, reason_codes=reasons, measurements=measurements,
            strategy_version=self.strategy_version, config_hash=get_settings().config_hash, git_sha=self.git_sha))

    def _level_id(self, symbol, timeframe, side, timestamp, price):
        raw = f"{self.exchange}|{symbol}|{timeframe}|{side.value}|{timestamp.isoformat()}|{price}"
        return "lvl_" + hashlib.sha256(raw.encode()).hexdigest()[:20]

    @staticmethod
    def _aware(timestamp):
        return timestamp if timestamp.tzinfo else timestamp.replace(tzinfo=timezone.utc)
