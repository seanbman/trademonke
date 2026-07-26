from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.models import Setup

from .models import EventRecord, ServiceHeartbeatRecord, SetupRecord


def save_setup(session: Session, setup: Setup) -> SetupRecord:
    record = session.get(SetupRecord, setup.id)
    values = {
        "pair": setup.pair, "timeframe": setup.timeframe, "direction": setup.direction.value,
        "state": setup.state.value, "components": {x.name: {"passed": x.passed, "raw": x.raw, "weight": str(x.weight), "data_quality": x.data_quality} for x in setup.components},
        "detected_at": setup.detected_at, "strategy_version": setup.strategy_version,
        "config_hash": setup.config_hash, "git_sha": setup.git_sha,
    }
    if record is None:
        record = SetupRecord(id=setup.id, highest_state_reached=setup.state.value, **values)
        session.add(record)
    else:
        for key, value in values.items():
            setattr(record, key, value)
    session.commit()
    return record


def append_event_idempotently(session: Session, event: EventRecord) -> bool:
    session.add(event)
    try:
        session.commit()
        return True
    except IntegrityError:
        session.rollback()
        return False


def canonical_event(*, event_id: str, event_type: str, occurred_at: datetime,
                    service: str, environment: str, strategy_version: str,
                    config_hash: str, git_sha: str, correlation_id: str,
                    payload: dict | None = None, causation_id: str | None = None,
                    candle_timestamp: datetime | None = None,
                    market_context: dict | None = None, decision_context: dict | None = None,
                    measurements: dict | None = None, severity: str = "info",
                    retry_count: int = 0, latency_ms: int | None = None,
                    external_request_id: str | None = None,
                    image_version: str = "unknown",
                    dependency_manifest_id: str = "unknown") -> EventRecord:
    if occurred_at.tzinfo is None or occurred_at.utcoffset() is None:
        raise ValueError("canonical event occurred_at must be UTC-aware")
    occurred_at = occurred_at.astimezone(timezone.utc)
    if candle_timestamp is not None:
        if candle_timestamp.tzinfo is None or candle_timestamp.utcoffset() is None:
            raise ValueError("canonical event candle_timestamp must be UTC-aware")
        candle_timestamp = candle_timestamp.astimezone(timezone.utc)
    if retry_count < 0 or latency_ms is not None and latency_ms < 0:
        raise ValueError("canonical event operational measurements cannot be negative")
    return EventRecord(
        event_id=event_id, event_type=event_type, schema_version="1.0",
        correlation_id=correlation_id, causation_id=causation_id,
        occurred_at=occurred_at, recorded_at=datetime.now(timezone.utc),
        candle_timestamp=candle_timestamp, service=service, environment=environment,
        payload=payload or {}, market_context=market_context or {},
        decision_context=decision_context or {}, measurements=measurements or {},
        severity=severity, retry_count=retry_count, latency_ms=latency_ms,
        external_request_id=external_request_id, strategy_version=strategy_version,
        config_hash=config_hash, git_sha=git_sha, image_version=image_version,
        dependency_manifest_id=dependency_manifest_id)


def list_setups(session: Session) -> list[SetupRecord]:
    return list(session.scalars(select(SetupRecord).order_by(SetupRecord.detected_at.desc())))


def record_heartbeat(session: Session, service: str, strategy_version: str, git_sha: str,
                     status: str = "healthy", details: dict | None = None) -> None:
    now = datetime.now(timezone.utc)
    heartbeat = session.get(ServiceHeartbeatRecord, service)
    if heartbeat is None:
        heartbeat = ServiceHeartbeatRecord(service=service, observed_at=now, status=status,
                                           details=details or {}, strategy_version=strategy_version,
                                           git_sha=git_sha)
        session.add(heartbeat)
    else:
        heartbeat.observed_at = now
        heartbeat.status = status
        heartbeat.details = details or {}
        heartbeat.strategy_version = strategy_version
        heartbeat.git_sha = git_sha
    session.commit()
