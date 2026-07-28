"""Watchlist invalidation event persistence from drawings and liquidity measurements."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.annotations import evaluate_annotation_break, label_to_event_hint
from app.domain.liquidity import LevelEventType, LevelSide, classify_level_candle
from app.domain.models import Candle, Direction
from app.domain.structure import classify_structure_break, infer_prior_trend
from app.telemetry.models import (
    ChartAnnotationRecord,
    LiquidityLevelRecord,
    WatchlistInvalidationEventRecord,
)


def _event_id(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:40]


def evaluate_annotation_invalidations(
    session: Session,
    *,
    exchange: str,
    symbol: str,
    timeframe: str,
    candle: Candle,
) -> list[WatchlistInvalidationEventRecord]:
    annotations = list(session.scalars(select(ChartAnnotationRecord).where(
        ChartAnnotationRecord.exchange == exchange,
        ChartAnnotationRecord.symbol == symbol,
        ChartAnnotationRecord.timeframe == timeframe,
        ChartAnnotationRecord.active.is_(True),
    )))
    created: list[WatchlistInvalidationEventRecord] = []
    now = datetime.now(timezone.utc)
    for annotation in annotations:
        result = evaluate_annotation_break(annotation.kind, annotation.geometry, candle)
        if result is None:
            continue
        event_type = result["event_type"]
        hint = label_to_event_hint(annotation.label)
        event_id = _event_id(
            "annotation", annotation.id, event_type, candle.timestamp.isoformat(),
        )
        if session.scalar(select(WatchlistInvalidationEventRecord).where(
                WatchlistInvalidationEventRecord.event_id == event_id)):
            continue
        message = (
            f"Measured {event_type.replace('_', ' ')} on {symbol} {timeframe} "
            f"for annotation label {annotation.label} ({hint})."
        )
        row = WatchlistInvalidationEventRecord(
            event_id=event_id,
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
            event_type=event_type,
            source="annotation",
            annotation_id=annotation.id,
            liquidity_level_id=None,
            candle_timestamp=candle.timestamp,
            message=message,
            measurements={**result, "label": annotation.label, "hint": hint},
            created_at=now,
        )
        session.add(row)
        created.append(row)
    return created


def evaluate_liquidity_invalidations(
    session: Session,
    *,
    exchange: str,
    symbol: str,
    timeframe: str,
    candle: Candle,
    prior_candles: list[Candle],
    touch_tolerance_bps: Decimal = Decimal("2"),
    structure_lookback: int = 10,
) -> list[WatchlistInvalidationEventRecord]:
    levels = list(session.scalars(select(LiquidityLevelRecord).where(
        LiquidityLevelRecord.exchange == exchange,
        LiquidityLevelRecord.symbol == symbol,
        LiquidityLevelRecord.timeframe == timeframe,
        LiquidityLevelRecord.status == "active",
    )))
    created: list[WatchlistInvalidationEventRecord] = []
    now = datetime.now(timezone.utc)
    for level in levels:
        side = LevelSide.HIGH if level.direction == "short" else LevelSide.LOW
        # Prefer explicit level_type when present
        if level.level_type in {"high", "eqh"}:
            side = LevelSide.HIGH
        elif level.level_type in {"low", "eql"}:
            side = LevelSide.LOW
        classified = classify_level_candle(side, level.price, candle, touch_tolerance_bps)
        if classified is None:
            continue
        if classified is LevelEventType.SWEPT:
            event_type = "liquidity_sweep"
            bsl_ssl = "buy_side_liquidity" if side is LevelSide.HIGH else "sell_side_liquidity"
        elif classified is LevelEventType.ACCEPTED_BREAKOUT:
            event_type = "accepted_breakout"
            bsl_ssl = "buy_side_liquidity" if side is LevelSide.HIGH else "sell_side_liquidity"
        else:
            continue
        event_id = _event_id(
            "liquidity", level.id, event_type, candle.timestamp.isoformat(),
        )
        if session.scalar(select(WatchlistInvalidationEventRecord).where(
                WatchlistInvalidationEventRecord.event_id == event_id)):
            continue
        message = (
            f"Measured {event_type.replace('_', ' ')} on {symbol} {timeframe} "
            f"at {level.price} ({bsl_ssl})."
        )
        row = WatchlistInvalidationEventRecord(
            event_id=event_id,
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
            event_type=event_type,
            source="liquidity_map",
            annotation_id=None,
            liquidity_level_id=level.id,
            candle_timestamp=candle.timestamp,
            message=message,
            measurements={
                "price": str(level.price),
                "level_type": level.level_type,
                "direction": level.direction,
                "liquidity_label": bsl_ssl,
                "classification": classified.value,
            },
            created_at=now,
        )
        session.add(row)
        created.append(row)

    # Structure break against recent lookback (named CHoCH/MSS/BOS when trend known)
    if len(prior_candles) >= structure_lookback:
        window = prior_candles[-structure_lookback:]
        prior_trend = infer_prior_trend(prior_candles + [candle], lookback=structure_lookback)
        for direction in (Direction.LONG, Direction.SHORT):
            event = classify_structure_break(
                candle, window, direction, prior_trend=prior_trend)
            if event is None:
                continue
            event_type = event.label.value
            event_id = _event_id(
                "structure", symbol, timeframe, direction.value, event_type,
                candle.timestamp.isoformat(),
            )
            if session.scalar(select(WatchlistInvalidationEventRecord).where(
                    WatchlistInvalidationEventRecord.event_id == event_id)):
                continue
            message = (
                f"Measured {event_type} ({direction.value}) on {symbol} {timeframe} "
                f"(close beyond lookback extreme)."
            )
            row = WatchlistInvalidationEventRecord(
                event_id=event_id,
                exchange=exchange,
                symbol=symbol,
                timeframe=timeframe,
                event_type=event_type,
                source="structure",
                annotation_id=None,
                liquidity_level_id=None,
                candle_timestamp=candle.timestamp,
                message=message,
                measurements={
                    **event.measurements,
                    "direction": direction.value,
                    "lookback": structure_lookback,
                },
                created_at=now,
            )
            session.add(row)
            created.append(row)
    return created
