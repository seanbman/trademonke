#!/usr/bin/env python3
"""Import legacy SQLite platform.db market tables into PostgreSQL."""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.settings import get_settings
from app.telemetry.db import SessionLocal
from app.telemetry.models import (AlertSubscriptionRecord, BackfillJobRecord,
                                  BackfillRequestRecord, CandidateEvidenceRecord,
                                  CandleRecord, IndicatorAlertEventRecord,
                                  IndicatorSnapshotRecord, SetupRecord,
                                  SetupTransitionRecord, SupplementalMetricRecord,
                                  WatchlistAssetRecord, WatchlistChangeRecord)


def _parse_dt(value: str | None) -> datetime | None:
    if value is None:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _rows(conn: sqlite3.Connection, table: str) -> list[sqlite3.Row]:
    conn.row_factory = sqlite3.Row
    return list(conn.execute(f'SELECT * FROM "{table}"'))


def import_candles(session, conn: sqlite3.Connection, batch_size: int = 5000) -> int:
    rows = _rows(conn, "market_candles")
    total = 0
    for offset in range(0, len(rows), batch_size):
        chunk = rows[offset:offset + batch_size]
        session.execute(
            pg_insert(CandleRecord).values([
                {
                    "id": row["id"],
                    "exchange": row["exchange"],
                    "symbol": row["symbol"],
                    "timeframe": row["timeframe"],
                    "timestamp": _parse_dt(row["timestamp"]),
                    "open": row["open"],
                    "high": row["high"],
                    "low": row["low"],
                    "close": row["close"],
                    "volume": row["volume"],
                    "source": row["source"],
                    "closed": bool(row["closed"]),
                }
                for row in chunk
            ]).on_conflict_do_nothing(index_elements=[
                "exchange", "symbol", "timeframe", "timestamp",
            ])
        )
        total += len(chunk)
        session.commit()
    return total


def import_simple_table(session, model, conn: sqlite3.Connection, table: str,
                        transform) -> int:
    rows = _rows(conn, table)
    if not rows:
        return 0
    for row in rows:
        session.merge(model(**transform(row)))
    session.commit()
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Import platform.db into PostgreSQL")
    parser.add_argument("--sqlite-path", default="platform.db")
    parser.add_argument("--skip-candles", action="store_true")
    args = parser.parse_args()
    sqlite_path = Path(args.sqlite_path)
    if not sqlite_path.is_file():
        raise SystemExit(f"missing sqlite database: {sqlite_path}")

    settings = get_settings()
    if settings.database_url.startswith("sqlite"):
        raise SystemExit("PLATFORM_DATABASE_URL must target PostgreSQL for import")

    conn = sqlite3.connect(sqlite_path)
    counts: dict[str, int] = {}
    with SessionLocal() as session:
        if not args.skip_candles:
            counts["market_candles"] = import_candles(session, conn)
        counts["watchlist_assets"] = import_simple_table(
            session, WatchlistAssetRecord, conn, "watchlist_assets",
            lambda row: {
                "symbol": row["symbol"], "status": row["status"],
                "protected": bool(row["protected"]),
                "created_at": _parse_dt(row["created_at"]),
                "updated_at": _parse_dt(row["updated_at"]),
                "updated_by": row["updated_by"], "reason": row["reason"],
            })
        counts["setups"] = import_simple_table(
            session, SetupRecord, conn, "setups",
            lambda row: {
                "id": row["id"], "pair": row["pair"], "timeframe": row["timeframe"],
                "direction": row["direction"], "state": row["state"],
                "highest_state_reached": row["state"],
                "components": json.loads(row["components"]) if isinstance(row["components"], str) else row["components"],
                "detected_at": _parse_dt(row["detected_at"]),
                "strategy_version": row["strategy_version"],
                "config_hash": row["config_hash"], "git_sha": row["git_sha"],
            })
        counts["setup_transitions"] = import_simple_table(
            session, SetupTransitionRecord, conn, "setup_transitions",
            lambda row: {
                "id": row["id"], "setup_id": row["setup_id"],
                "from_state": row["from_state"], "to_state": row["to_state"],
                "occurred_at": _parse_dt(row["occurred_at"]), "reason": row["reason"],
            })
        counts["indicator_snapshots"] = import_simple_table(
            session, IndicatorSnapshotRecord, conn, "indicator_snapshots",
            lambda row: {
                "id": row["id"], "exchange": row["exchange"], "symbol": row["symbol"],
                "timeframe": row["timeframe"],
                "candle_timestamp": _parse_dt(row["candle_timestamp"]),
                "evaluated_at": _parse_dt(row["evaluated_at"]),
                "direction": row["direction"], "score": row["score"],
                "setup_state": row["setup_state"],
                "components": json.loads(row["components"]) if isinstance(row["components"], str) else row["components"],
                "strategy_version": row["strategy_version"],
            })
        counts["supplemental_metrics"] = import_simple_table(
            session, SupplementalMetricRecord, conn, "supplemental_metrics",
            lambda row: {
                "id": row["id"], "exchange": row["exchange"], "symbol": row["symbol"],
                "timestamp": _parse_dt(row["timestamp"]), "metric_type": row["metric_type"],
                "values": json.loads(row["values"]) if isinstance(row["values"], str) else row["values"],
                "source": row["source"],
            })
        counts["candidate_evidence"] = import_simple_table(
            session, CandidateEvidenceRecord, conn, "candidate_evidence",
            lambda row: {
                "id": row["id"], "exchange": row["exchange"], "symbol": row["symbol"],
                "observed_at": _parse_dt(row["observed_at"]),
                "quote_volume": row["quote_volume"], "spread_bps": row["spread_bps"],
                "recommendation": row["recommendation"],
                "reasons": json.loads(row["reasons"]) if isinstance(row["reasons"], str) else row["reasons"],
            })
        counts["watchlist_changes"] = import_simple_table(
            session, WatchlistChangeRecord, conn, "watchlist_changes",
            lambda row: {
                "id": row["id"], "symbol": row["symbol"],
                "target_status": row["target_status"], "state": row["state"],
                "requested_at": _parse_dt(row["requested_at"]),
                "expires_at": _parse_dt(row["expires_at"]),
                "requested_by": row["requested_by"],
                "confirmed_at": _parse_dt(row["confirmed_at"]),
                "confirmed_by": row["confirmed_by"], "reason": row["reason"],
            })
        counts["backfill_jobs"] = import_simple_table(
            session, BackfillJobRecord, conn, "backfill_jobs",
            lambda row: {
                "id": row["id"], "exchange": row["exchange"], "symbol": row["symbol"],
                "timeframes": json.loads(row["timeframes"]) if isinstance(row["timeframes"], str) else row["timeframes"],
                "days": row["days"], "status": row["status"],
                "current_timeframe": row["current_timeframe"],
                "completed_timeframes": json.loads(row["completed_timeframes"]) if isinstance(row["completed_timeframes"], str) else row["completed_timeframes"],
                "rows_processed": row["rows_processed"],
                "requested_at": _parse_dt(row["requested_at"]),
                "started_at": _parse_dt(row["started_at"]),
                "updated_at": _parse_dt(row["updated_at"]),
                "completed_at": _parse_dt(row["completed_at"]),
                "requested_by": row["requested_by"], "error_type": row["error_type"],
            })
        counts["backfill_requests"] = import_simple_table(
            session, BackfillRequestRecord, conn, "backfill_requests",
            lambda row: {
                "id": row["id"], "exchange": row["exchange"], "symbol": row["symbol"],
                "timeframes": json.loads(row["timeframes"]) if isinstance(row["timeframes"], str) else row["timeframes"],
                "days": row["days"], "state": row["state"],
                "requested_at": _parse_dt(row["requested_at"]),
                "expires_at": _parse_dt(row["expires_at"]),
                "requested_by": row["requested_by"],
                "confirmed_at": _parse_dt(row["confirmed_at"]),
                "confirmed_by": row["confirmed_by"], "job_id": row["job_id"],
            })
        counts["indicator_alert_events"] = import_simple_table(
            session, IndicatorAlertEventRecord, conn, "indicator_alert_events",
            lambda row: {
                "id": row["id"], "event_id": row["event_id"], "exchange": row["exchange"],
                "symbol": row["symbol"], "timeframe": row["timeframe"],
                "candle_timestamp": _parse_dt(row["candle_timestamp"]),
                "direction": row["direction"], "event_type": row["event_type"],
                "component": row["component"], "old_value": row["old_value"],
                "new_value": row["new_value"], "score": row["score"],
                "message": row["message"], "created_at": _parse_dt(row["created_at"]),
                "delivered_at": _parse_dt(row["delivered_at"]),
            })
        counts["alert_subscriptions"] = import_simple_table(
            session, AlertSubscriptionRecord, conn, "alert_subscriptions",
            lambda row: {
                "id": row["id"], "chat_id": row["chat_id"], "user_id": row["user_id"],
                "symbol": row["symbol"], "enabled": bool(row["enabled"]),
                "components": json.loads(row["components"]) if isinstance(row["components"], str) else row["components"],
                "minimum_score": row["minimum_score"],
                "created_at": _parse_dt(row["created_at"]),
                "updated_at": _parse_dt(row["updated_at"]),
            })
        session.execute(text("SELECT 1"))
    conn.close()
    print(json.dumps(counts, indent=2))


if __name__ == "__main__":
    main()
