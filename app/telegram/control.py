from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.telemetry.models import ControlStateRecord
from app.telemetry.repository import append_event_idempotently, canonical_event
from app.settings import get_settings


def get_control(session: Session, key: str) -> bool:
    record = session.get(ControlStateRecord, key)
    return bool(record and record.enabled)


def set_control(session: Session, key: str, enabled: bool, user_id: int, reason: str,
                strategy_version: str, git_sha: str) -> None:
    now = datetime.now(timezone.utc)
    record = session.get(ControlStateRecord, key)
    if record is None:
        record = ControlStateRecord(key=key, enabled=enabled, updated_at=now,
                                    updated_by=str(user_id), reason=reason)
        session.add(record)
    else:
        record.enabled, record.updated_at = enabled, now
        record.updated_by, record.reason = str(user_id), reason
    session.commit()
    event = canonical_event(
        event_id=f"telegram:{key}:{enabled}:{user_id}:{int(now.timestamp())}",
        event_type="control_state_changed", occurred_at=now, service="telegram-bot",
        environment="runtime", correlation_id=f"control:{key}:{int(now.timestamp())}",
        payload={"control": key, "enabled": enabled, "user_id": user_id, "reason": reason},
        decision_context={"decision": "enabled" if enabled else "disabled",
                          "reason_codes": [reason], "operator_id": str(user_id)},
        strategy_version=strategy_version, config_hash=get_settings().config_hash, git_sha=git_sha,
    )
    append_event_idempotently(session, event)
