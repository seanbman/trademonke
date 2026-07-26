from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.orm import sessionmaker

from app.market_data.collector import MarketDataCollector
from app.market_data.watchlist import enqueue_backfill
from app.telemetry.db import Base, build_engine
from app.telemetry.models import BackfillJobRecord


class FakeExchange:
    exchange_id = "okx"


@pytest.mark.anyio
async def test_worker_completes_job_and_records_page_progress():
    engine = build_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as session:
        job = enqueue_backfill(session, "okx", "SOL/USDT", ("5m", "1h"), 30, "test")
        session.commit()
        job_id = job.id
    collector = MarketDataCollector(FakeExchange(), Session)

    async def fake_backfill(symbol, timeframe, days, progress=None):
        assert symbol == "SOL/USDT" and days == 30
        progress(100)
        progress(25)
        return 125

    collector.backfill = AsyncMock(side_effect=fake_backfill)
    await collector.process_backfill_job(job_id)
    with Session() as session:
        job = session.get(BackfillJobRecord, job_id)
        assert job.status == "completed"
        assert job.completed_timeframes == ["5m", "1h"]
        assert job.rows_processed == 250
        assert job.completed_at is not None


def test_interrupted_jobs_are_requeued():
    engine = build_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as session:
        job = enqueue_backfill(session, "okx", "SOL/USDT", ("1h",), 30, "test")
        job.status, job.started_at = "running", datetime.now(timezone.utc)
        session.commit()
        job_id = job.id
    collector = MarketDataCollector(FakeExchange(), Session)
    collector.recover_interrupted_jobs()
    with Session() as session:
        job = session.get(BackfillJobRecord, job_id)
        assert job.status == "pending"
        assert job.error_type == "InterruptedRestart"
