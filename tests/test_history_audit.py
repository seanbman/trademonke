from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.market_data.watchlist import audit_configured_history, ensure_anchors
from app.telemetry.db import Base, build_engine
from app.telemetry.models import BackfillJobRecord


def test_history_audit_queues_missing_configured_timeframes_and_avoids_duplicates():
    engine = build_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as session:
        ensure_anchors(session)
        queued = audit_configured_history(session, "okx", ("BTC/USDT", "ETH/USDT"),
                                          ("4h", "1d"), 365)
        assert len(queued) == 2
        jobs = list(session.scalars(select(BackfillJobRecord).order_by(BackfillJobRecord.symbol)))
        assert all(job.timeframes == ["4h", "1d"] for job in jobs)
        assert all(job.requested_by == "system:history_audit" for job in jobs)
        assert audit_configured_history(session, "okx", ("BTC/USDT", "ETH/USDT"),
                                        ("4h", "1d"), 365) == []


def test_completed_audit_job_accepts_best_available_but_new_timeframe_queues():
    engine = build_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as session:
        ensure_anchors(session, ("BTC/USDT",))
        audit_configured_history(session, "okx", ("BTC/USDT",), ("4h", "1d"), 365)
        job = session.scalar(select(BackfillJobRecord))
        job.status, job.completed_timeframes = "completed", ["4h", "1d"]
        job.completed_at = job.updated_at = datetime.now(timezone.utc)
        session.commit()
        assert audit_configured_history(session, "okx", ("BTC/USDT",),
                                        ("4h", "1d"), 365) == []
        queued = audit_configured_history(session, "okx", ("BTC/USDT",),
                                          ("4h", "1d", "1h"), 365)
        assert len(queued) == 1
        newest = session.get(BackfillJobRecord, queued[0])
        assert newest.timeframes == ["1h"]


def test_failed_history_job_has_retry_cooldown():
    engine = build_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as session:
        ensure_anchors(session, ("BTC/USDT",))
        queued = audit_configured_history(session, "okx", ("BTC/USDT",), ("1d",), 365)
        job = session.get(BackfillJobRecord, queued[0])
        job.status, job.error_type = "failed", "NetworkError"
        job.updated_at = datetime.now(timezone.utc)
        session.commit()
        assert audit_configured_history(session, "okx", ("BTC/USDT",), ("1d",), 365) == []
