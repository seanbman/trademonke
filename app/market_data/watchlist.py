from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.telemetry.models import (BackfillJobRecord, BackfillRequestRecord,
                                  CandidateEvidenceRecord, CandleRecord,
                                  WatchlistAssetRecord, WatchlistChangeRecord)

VALID_STATUSES = {"active", "probe", "disabled"}
ANCHORS = ("BTC/USDT", "ETH/USDT")


def normalize_symbol(symbol: str) -> str:
    value = symbol.strip().upper()
    if "/" not in value:
        value = f"{value}/USDT"
    base, quote = value.split("/", 1)
    if not base.isalnum() or quote != "USDT":
        raise ValueError("watchlist symbols must be BASE/USDT")
    return value


def ensure_anchors(session: Session, configured: tuple[str, ...] = ANCHORS) -> None:
    now = datetime.now(timezone.utc)
    for raw in configured:
        symbol = normalize_symbol(raw)
        if session.get(WatchlistAssetRecord, symbol) is None:
            session.add(WatchlistAssetRecord(symbol=symbol, status="active", protected=symbol in ANCHORS,
                                             created_at=now, updated_at=now, updated_by="system",
                                             reason="initial configured anchor"))
    session.commit()


def collection_symbols(session: Session) -> tuple[str, ...]:
    return tuple(session.scalars(select(WatchlistAssetRecord.symbol).where(
        WatchlistAssetRecord.status.in_(["active", "probe"])).order_by(WatchlistAssetRecord.symbol)))


def create_change(session: Session, symbol: str, target_status: str, user_id: int,
                  reason: str = "Telegram request") -> WatchlistChangeRecord:
    symbol = normalize_symbol(symbol)
    if target_status not in VALID_STATUSES:
        raise ValueError("invalid target watchlist status")
    asset = session.get(WatchlistAssetRecord, symbol)
    if asset and asset.protected and target_status != "active":
        raise ValueError(f"{symbol} is a protected anchor and cannot be removed")
    now = datetime.now(timezone.utc)
    record = WatchlistChangeRecord(id=f"ch_{secrets.token_hex(4)}", symbol=symbol,
                                   target_status=target_status, state="pending", requested_at=now,
                                   expires_at=now + timedelta(minutes=15), requested_by=str(user_id),
                                   confirmed_at=None, confirmed_by=None, reason=reason)
    session.add(record)
    session.commit()
    return record


def probe_eligibility(session: Session, exchange: str, symbol: str,
                      min_quote_volume: float, max_spread_bps: float,
                      required_days: int = 30, minimum_coverage: float = 0.95) -> tuple[bool, list[str]]:
    evidence = session.scalar(select(CandidateEvidenceRecord).where(
        CandidateEvidenceRecord.exchange == exchange,
        CandidateEvidenceRecord.symbol == symbol).order_by(CandidateEvidenceRecord.observed_at.desc()))
    reasons = []
    if evidence is None:
        reasons.append("no candidate liquidity snapshot")
    else:
        if float(evidence.quote_volume) < min_quote_volume:
            reasons.append("quote volume below threshold")
        if evidence.spread_bps is None or float(evidence.spread_bps) > max_spread_bps:
            reasons.append("spread missing or above threshold")
    cutoff = datetime.now(timezone.utc) - timedelta(days=required_days)
    count = session.scalar(select(func.count()).where(
        CandleRecord.exchange == exchange, CandleRecord.symbol == symbol,
        CandleRecord.timeframe == "1h", CandleRecord.timestamp >= cutoff)) or 0
    expected = required_days * 24
    coverage = count / expected
    if coverage < minimum_coverage:
        reasons.append(f"1h history coverage {coverage:.1%} below {minimum_coverage:.0%}")
    return not reasons, reasons


def confirm_change(session: Session, change_id: str, user_id: int, exchange: str,
                   min_quote_volume: float, max_spread_bps: float,
                   backfill_timeframes: tuple[str, ...] = ("5m", "15m", "30m", "1h", "4h", "1d"),
                   backfill_days: int = 365) -> WatchlistAssetRecord:
    change = session.get(WatchlistChangeRecord, change_id)
    now = datetime.now(timezone.utc)
    if change is None or change.state != "pending":
        raise ValueError("pending change not found")
    expires = change.expires_at if change.expires_at.tzinfo else change.expires_at.replace(tzinfo=timezone.utc)
    if expires < now:
        change.state = "expired"
        session.commit()
        raise ValueError("pending change expired")
    asset = session.get(WatchlistAssetRecord, change.symbol)
    if change.target_status == "active" and (asset is None or asset.status != "active"):
        eligible, reasons = probe_eligibility(session, exchange, change.symbol,
                                              min_quote_volume, max_spread_bps)
        if not eligible:
            raise ValueError("not eligible for active watchlist: " + "; ".join(reasons))
    if asset is None:
        asset = WatchlistAssetRecord(symbol=change.symbol, status=change.target_status, protected=False,
                                     created_at=now, updated_at=now, updated_by=str(user_id), reason=change.reason)
        session.add(asset)
    else:
        asset.status, asset.updated_at = change.target_status, now
        asset.updated_by, asset.reason = str(user_id), change.reason
    change.state, change.confirmed_at, change.confirmed_by = "confirmed", now, str(user_id)
    if change.target_status == "probe":
        enqueue_backfill(session, exchange, change.symbol, backfill_timeframes,
                         backfill_days, str(user_id))
    session.commit()
    return asset


def enqueue_backfill(session: Session, exchange: str, symbol: str,
                     timeframes: tuple[str, ...], days: int,
                     requested_by: str) -> BackfillJobRecord:
    symbol = normalize_symbol(symbol)
    if days < 1 or days > 3650:
        raise ValueError("backfill days must be between 1 and 3650")
    existing = session.scalar(select(BackfillJobRecord).where(
        BackfillJobRecord.exchange == exchange, BackfillJobRecord.symbol == symbol,
        BackfillJobRecord.status.in_(["pending", "running"])
    ).order_by(BackfillJobRecord.requested_at.desc()))
    if existing:
        return existing
    now = datetime.now(timezone.utc)
    job = BackfillJobRecord(
        id=f"bf_{secrets.token_hex(4)}", exchange=exchange, symbol=symbol,
        timeframes=list(timeframes), days=days, status="pending", current_timeframe=None,
        completed_timeframes=[], rows_processed=0, requested_at=now, started_at=None,
        updated_at=now, completed_at=None, requested_by=requested_by, error_type=None,
    )
    session.add(job)
    session.flush()
    return job


def create_backfill_request(session: Session, exchange: str, symbol: str,
                            timeframes: tuple[str, ...], days: int,
                            user_id: int) -> BackfillRequestRecord:
    symbol = normalize_symbol(symbol)
    asset = session.get(WatchlistAssetRecord, symbol)
    if asset is None or asset.status not in {"active", "probe"}:
        raise ValueError(f"{symbol} must be active or probe")
    allowed = {"1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "1d"}
    if not timeframes or any(timeframe not in allowed for timeframe in timeframes):
        raise ValueError("unsupported or empty timeframe list")
    if days < 1 or days > 3650:
        raise ValueError("days must be between 1 and 3650")
    now = datetime.now(timezone.utc)
    request = BackfillRequestRecord(
        id=f"br_{secrets.token_hex(4)}", exchange=exchange, symbol=symbol,
        timeframes=list(timeframes), days=days, state="pending", requested_at=now,
        expires_at=now + timedelta(minutes=15), requested_by=str(user_id),
        confirmed_at=None, confirmed_by=None, job_id=None,
    )
    session.add(request)
    session.commit()
    return request


def confirm_backfill_request(session: Session, request_id: str,
                             user_id: int) -> BackfillJobRecord:
    request = session.get(BackfillRequestRecord, request_id)
    now = datetime.now(timezone.utc)
    if request is None or request.state != "pending":
        raise ValueError("pending backfill request not found")
    expires = request.expires_at if request.expires_at.tzinfo else request.expires_at.replace(tzinfo=timezone.utc)
    if expires < now:
        request.state = "expired"
        session.commit()
        raise ValueError("backfill request expired")
    job = enqueue_backfill(session, request.exchange, request.symbol,
                           tuple(request.timeframes), request.days, str(user_id))
    request.state, request.confirmed_at = "confirmed", now
    request.confirmed_by, request.job_id = str(user_id), job.id
    session.commit()
    return job


def timeframe_seconds(timeframe: str) -> int:
    unit, amount = timeframe[-1], int(timeframe[:-1])
    return amount * {"m": 60, "h": 3600, "d": 86400}[unit]


def audit_configured_history(session: Session, exchange: str,
                             symbols: tuple[str, ...], timeframes: tuple[str, ...],
                             days: int, minimum_coverage: float = 0.95) -> list[str]:
    """Queue missing configured history, respecting active jobs and retry cooldown."""
    now = datetime.now(timezone.utc)
    queued: list[str] = []
    for symbol in symbols:
        active_job = session.scalar(select(BackfillJobRecord).where(
            BackfillJobRecord.exchange == exchange, BackfillJobRecord.symbol == symbol,
            BackfillJobRecord.status.in_(["pending", "running"])
        ).order_by(BackfillJobRecord.requested_at.desc()))
        if active_job:
            continue
        latest_job = session.scalar(select(BackfillJobRecord).where(
            BackfillJobRecord.exchange == exchange,
            BackfillJobRecord.symbol == symbol
        ).order_by(BackfillJobRecord.requested_at.desc()))
        if latest_job and latest_job.status == "failed":
            updated = latest_job.updated_at if latest_job.updated_at.tzinfo else latest_job.updated_at.replace(tzinfo=timezone.utc)
            if now - updated < timedelta(hours=1):
                continue
        missing = []
        for timeframe in timeframes:
            seconds = timeframe_seconds(timeframe)
            expected = max(1, int(days * 86400 / seconds))
            count, earliest = session.execute(select(
                func.count(CandleRecord.id), func.min(CandleRecord.timestamp)
            ).where(
                CandleRecord.exchange == exchange, CandleRecord.symbol == symbol,
                CandleRecord.timeframe == timeframe, CandleRecord.closed.is_(True),
                CandleRecord.timestamp >= now - timedelta(days=days),
            )).one()
            earliest_utc = (earliest if earliest and earliest.tzinfo else
                            earliest.replace(tzinfo=timezone.utc) if earliest else None)
            reaches_start = bool(earliest_utc and earliest_utc <= now - timedelta(days=days) + timedelta(seconds=seconds * 2))
            if reaches_start and count / expected >= minimum_coverage:
                continue
            attempted = bool(latest_job and latest_job.status == "completed" and
                             latest_job.days >= days and timeframe in (latest_job.timeframes or []))
            if not attempted:
                missing.append(timeframe)
        if missing:
            job = enqueue_backfill(session, exchange, symbol, tuple(missing), days,
                                   "system:history_audit")
            queued.append(job.id)
    session.commit()
    return queued
