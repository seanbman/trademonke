from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.telemetry.models import CandleRecord, SupplementalMetricRecord

from .types import OhlcvRow, SupplementalSnapshot


def latest_candles(session: Session) -> dict[tuple[str, str, str], object]:
    rows = session.execute(
        select(CandleRecord.exchange, CandleRecord.symbol, CandleRecord.timeframe,
               func.max(CandleRecord.timestamp))
        .group_by(CandleRecord.exchange, CandleRecord.symbol, CandleRecord.timeframe)
    )
    return {(exchange, symbol, timeframe): timestamp for exchange, symbol, timeframe, timestamp in rows}


def upsert_candles(session: Session, rows: list[OhlcvRow]) -> int:
    if not rows:
        return 0
    values = [row.__dict__ for row in rows]
    dialect = session.bind.dialect.name
    if dialect == "postgresql":
        statement = pg_insert(CandleRecord).values(values)
        statement = statement.on_conflict_do_update(
            constraint="uq_candle_identity",
            set_={key: getattr(statement.excluded, key) for key in ("open", "high", "low", "close", "volume", "closed")},
        )
        session.execute(statement)
    else:
        for value in values:
            identity = {key: value[key] for key in ("exchange", "symbol", "timeframe", "timestamp")}
            existing = session.scalar(select(CandleRecord).filter_by(**identity))
            if existing:
                for key, item in value.items():
                    setattr(existing, key, item)
            else:
                session.add(CandleRecord(**value))
    session.commit()
    return len(rows)


def replace_supplement(session: Session, row: SupplementalSnapshot) -> None:
    session.execute(delete(SupplementalMetricRecord).where(
        SupplementalMetricRecord.exchange == row.exchange,
        SupplementalMetricRecord.symbol == row.symbol,
        SupplementalMetricRecord.metric_type == row.metric_type,
        SupplementalMetricRecord.timestamp == row.timestamp,
    ))
    session.add(SupplementalMetricRecord(**row.__dict__))
    session.commit()
