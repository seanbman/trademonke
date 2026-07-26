from __future__ import annotations

import asyncio
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Callable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.telemetry.models import BackfillJobRecord, CandleRecord
from app.telemetry.repository import record_heartbeat

from .exchange import ReadOnlyExchange
from .candidates import rank_candidates, save_candidate_evidence
from .storage import replace_supplement, upsert_candles
from .types import OhlcvRow, SupplementalSnapshot
from .watchlist import audit_configured_history, collection_symbols


def timeframe_ms(exchange: ReadOnlyExchange, timeframe: str) -> int:
    seconds = exchange.client.parse_timeframe(timeframe)
    if seconds <= 0:
        raise ValueError(f"invalid timeframe: {timeframe}")
    return seconds * 1000


def closed_rows(exchange_id: str, symbol: str, timeframe: str, raw: list[list], now_ms: int,
                duration_ms: int) -> list[OhlcvRow]:
    result = []
    for timestamp, open_, high, low, close, volume in raw:
        if timestamp + duration_ms > now_ms:
            continue
        result.append(OhlcvRow(exchange_id, symbol, timeframe,
                               datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc),
                               *(Decimal(str(value)) for value in (open_, high, low, close, volume))))
    return result


class MarketDataCollector:
    def __init__(self, exchange: ReadOnlyExchange, session_factory: Callable[[], Session], batch_limit: int = 300,
                 candidate_quote: str = "USDT", candidate_min_volume: float = 10_000_000,
                 candidate_max_spread_bps: float = 30, indicator_engine=None):
        self.exchange = exchange
        self.session_factory = session_factory
        self.batch_limit = batch_limit
        self.candidate_quote = candidate_quote
        self.candidate_min_volume = candidate_min_volume
        self.candidate_max_spread_bps = candidate_max_spread_bps
        self.indicator_engine = indicator_engine
        self.setup_engine = None
        self.liquidity_service = None
        self.episode_engine = None
        self.research_pipeline = None
        self.history_days = 365
        self.strategy_version = "unknown"
        self.git_sha = "unknown"

    async def backfill(self, symbol: str, timeframe: str, days: int,
                       progress: Callable[[int], None] | None = None) -> int:
        duration = timeframe_ms(self.exchange, timeframe)
        now_ms = self.exchange.client.milliseconds()
        cursor = now_ms - int(timedelta(days=days).total_seconds() * 1000)
        total = 0
        while cursor < now_ms - duration:
            raw = await self.exchange.fetch_ohlcv(symbol, timeframe, cursor, self.batch_limit)
            if not raw:
                break
            rows = closed_rows(self.exchange.exchange_id, symbol, timeframe, raw, now_ms, duration)
            with self.session_factory() as session:
                processed = upsert_candles(session, rows)
                total += processed
            if progress:
                progress(processed)
            next_cursor = int(raw[-1][0]) + duration
            if next_cursor <= cursor:
                raise RuntimeError("exchange OHLCV pagination did not advance")
            cursor = next_cursor
            if len(raw) < self.batch_limit:
                break
        return total

    def recover_interrupted_jobs(self) -> None:
        now = datetime.now(timezone.utc)
        with self.session_factory() as session:
            jobs = list(session.scalars(select(BackfillJobRecord).where(
                BackfillJobRecord.exchange == self.exchange.exchange_id,
                BackfillJobRecord.status == "running")))
            for job in jobs:
                job.status, job.current_timeframe, job.updated_at = "pending", None, now
                job.error_type = "InterruptedRestart"
            session.commit()

    def _next_backfill_job_id(self) -> str | None:
        with self.session_factory() as session:
            job = session.scalar(select(BackfillJobRecord).where(
                BackfillJobRecord.exchange == self.exchange.exchange_id,
                BackfillJobRecord.status == "pending"
            ).order_by(BackfillJobRecord.requested_at).limit(1))
            return job.id if job else None

    def ensure_configured_history(self, symbols: tuple[str, ...],
                                  timeframes: tuple[str, ...], days: int,
                                  minimum_coverage: float = 0.95) -> list[str]:
        """Queue one job per symbol when configured history is absent or incomplete."""
        with self.session_factory() as session:
            return audit_configured_history(session, self.exchange.exchange_id, symbols,
                                            timeframes, days, minimum_coverage)

    async def process_backfill_job(self, job_id: str) -> None:
        now = datetime.now(timezone.utc)
        with self.session_factory() as session:
            job = session.get(BackfillJobRecord, job_id)
            if job is None or job.status != "pending":
                return
            job.status, job.started_at, job.updated_at = "running", job.started_at or now, now
            job.error_type = None
            session.commit()
            symbol, days = job.symbol, job.days
            timeframes, completed = list(job.timeframes), list(job.completed_timeframes or [])
        try:
            for timeframe in timeframes:
                if timeframe in completed:
                    continue
                with self.session_factory() as session:
                    job = session.get(BackfillJobRecord, job_id)
                    job.current_timeframe, job.updated_at = timeframe, datetime.now(timezone.utc)
                    session.commit()

                def record_progress(count: int) -> None:
                    with self.session_factory() as progress_session:
                        progress_job = progress_session.get(BackfillJobRecord, job_id)
                        progress_job.rows_processed += count
                        progress_job.updated_at = datetime.now(timezone.utc)
                        progress_session.commit()

                await self.backfill(symbol, timeframe, days, record_progress)
                completed.append(timeframe)
                with self.session_factory() as session:
                    job = session.get(BackfillJobRecord, job_id)
                    job.completed_timeframes = list(completed)
                    job.updated_at = datetime.now(timezone.utc)
                    session.commit()
            with self.session_factory() as session:
                job = session.get(BackfillJobRecord, job_id)
                finished = datetime.now(timezone.utc)
                job.status, job.current_timeframe = "completed", None
                job.completed_at, job.updated_at = finished, finished
                session.commit()
        except Exception as error:
            with self.session_factory() as session:
                job = session.get(BackfillJobRecord, job_id)
                job.status, job.updated_at = "failed", datetime.now(timezone.utc)
                job.error_type = type(error).__name__
                session.commit()

    async def backfill_worker(self) -> None:
        self.recover_interrupted_jobs()
        while True:
            job_id = self._next_backfill_job_id()
            if job_id:
                await self.process_backfill_job(job_id)
            else:
                await asyncio.sleep(2)

    async def update(self, symbol: str, timeframe: str) -> int:
        duration = timeframe_ms(self.exchange, timeframe)
        with self.session_factory() as session:
            latest = session.scalar(select(func.max(CandleRecord.timestamp)).where(
                CandleRecord.exchange == self.exchange.exchange_id,
                CandleRecord.symbol == symbol, CandleRecord.timeframe == timeframe))
        if latest:
            # SQLite drops timezone metadata. Persisted candle timestamps are UTC by contract,
            # so never let the host's local timezone shift the exchange cursor into the future.
            latest_utc = latest if latest.tzinfo else latest.replace(tzinfo=timezone.utc)
            since = int(latest_utc.timestamp() * 1000)
        else:
            since = self.exchange.client.milliseconds() - duration * 3
        raw = await self.exchange.fetch_ohlcv(symbol, timeframe, since, self.batch_limit)
        rows = closed_rows(self.exchange.exchange_id, symbol, timeframe, raw,
                           self.exchange.client.milliseconds(), duration)
        with self.session_factory() as session:
            return upsert_candles(session, rows)

    async def supplement(self, base: str) -> list[str]:
        contract = f"{base}/USDT:USDT"
        stored: list[str] = []
        for metric, fetch in (("funding_rate", self.exchange.fetch_funding_rate),
                              ("open_interest", self.exchange.fetch_open_interest)):
            try:
                value = await fetch(contract)
            except (ValueError, KeyError):
                value = None
            if value:
                timestamp = value.get("timestamp") or self.exchange.client.milliseconds()
                snapshot = SupplementalSnapshot(
                    self.exchange.exchange_id, contract,
                    datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc), metric,
                    {key: item for key, item in value.items() if key != "info"},
                )
                with self.session_factory() as session:
                    replace_supplement(session, snapshot)
                stored.append(metric)
        return stored

    async def run_forever(self, timeframes: tuple[str, ...], poll_seconds: int = 30):
        next_candidate_refresh = 0.0
        next_history_audit = 0.0
        worker = asyncio.create_task(self.backfill_worker())
        try:
            while True:
                with self.session_factory() as session:
                    record_heartbeat(session, "market-data", self.strategy_version, self.git_sha)
                with self.session_factory() as session:
                    symbols = collection_symbols(session)
                if time.monotonic() >= next_history_audit:
                    self.ensure_configured_history(symbols, timeframes, self.history_days)
                    next_history_audit = time.monotonic() + 3600
                for symbol in symbols:
                    for timeframe in timeframes:
                        await self.update(symbol, timeframe)
                    await self.supplement(symbol.split("/")[0])
                    if self.liquidity_service:
                        self.liquidity_service.update(symbol, self.indicator_engine.base_timeframe)
                    if self.episode_engine:
                        self.episode_engine.update(symbol, self.indicator_engine.base_timeframe)
                    if self.indicator_engine:
                        snapshots = self.indicator_engine.evaluate_symbol(symbol)
                        if self.setup_engine:
                            for snapshot in snapshots:
                                self.setup_engine.process(snapshot)
                    if self.research_pipeline:
                        self.research_pipeline.update(symbol, self.indicator_engine.base_timeframe)
                if time.monotonic() >= next_candidate_refresh:
                    evidence = await rank_candidates(self.exchange, symbols, self.candidate_quote,
                                                     self.candidate_min_volume,
                                                     self.candidate_max_spread_bps, 20)
                    with self.session_factory() as session:
                        save_candidate_evidence(session, self.exchange.exchange_id, evidence)
                    next_candidate_refresh = time.monotonic() + 3600
                await asyncio.sleep(poll_seconds)
        finally:
            worker.cancel()
            await asyncio.gather(worker, return_exceptions=True)
