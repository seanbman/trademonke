from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.indicators.engine import COMPONENT_NAMES
from app.telemetry.models import AlertSubscriptionRecord, IndicatorAlertEventRecord


def get_subscription(session: Session, chat_id: int, user_id: int,
                     symbol: str) -> AlertSubscriptionRecord | None:
    return session.scalar(select(AlertSubscriptionRecord).where(
        AlertSubscriptionRecord.chat_id == str(chat_id),
        AlertSubscriptionRecord.user_id == str(user_id),
        AlertSubscriptionRecord.symbol == symbol))


def set_enabled(session: Session, chat_id: int, user_id: int,
                symbol: str, enabled: bool) -> AlertSubscriptionRecord:
    now = datetime.now(timezone.utc)
    record = get_subscription(session, chat_id, user_id, symbol)
    if record is None:
        record = AlertSubscriptionRecord(chat_id=str(chat_id), user_id=str(user_id), symbol=symbol,
                                         enabled=enabled, components=["*"], minimum_score=4,
                                         created_at=now, updated_at=now)
        session.add(record)
    else:
        record.enabled, record.updated_at = enabled, now
    session.commit()
    return record


def toggle_component(session: Session, chat_id: int, user_id: int,
                     symbol: str, component: str) -> AlertSubscriptionRecord:
    if component not in COMPONENT_NAMES:
        raise ValueError("component must be one of: " + ", ".join(COMPONENT_NAMES))
    record = set_enabled(session, chat_id, user_id, symbol, True)
    components = [] if record.components == ["*"] else list(record.components)
    if component in components:
        components.remove(component)
    else:
        components.append(component)
    record.components, record.updated_at = components, datetime.now(timezone.utc)
    session.commit()
    return record


def set_minimum_score(session: Session, chat_id: int, user_id: int,
                      symbol: str, score: int) -> AlertSubscriptionRecord:
    if score < 0 or score > 6:
        raise ValueError("score must be between 0 and 6")
    record = set_enabled(session, chat_id, user_id, symbol, True)
    record.minimum_score, record.updated_at = score, datetime.now(timezone.utc)
    session.commit()
    return record


def set_setup_only(session: Session, chat_id: int, user_id: int,
                   symbol: str) -> AlertSubscriptionRecord:
    record = set_enabled(session, chat_id, user_id, symbol, True)
    record.components = []
    record.minimum_score = 4
    record.updated_at = datetime.now(timezone.utc)
    session.commit()
    return record


def event_matches(event: IndicatorAlertEventRecord, subscription: AlertSubscriptionRecord) -> bool:
    if not subscription.enabled or subscription.symbol != event.symbol:
        return False
    if event.event_type in {"score_change", "state_change", "setup_transition"}:
        return event.score >= subscription.minimum_score
    return "*" in subscription.components or event.component in subscription.components


def setup_event_matches_default(event: IndicatorAlertEventRecord,
                                subscriptions: list[AlertSubscriptionRecord],
                                tracked: bool, default_minimum_score: int = 4) -> bool:
    """Setup transitions are watchlist opt-out; newest explicit preference wins."""
    if event.event_type != "setup_transition" or not tracked:
        return False
    relevant = [item for item in subscriptions if item.symbol == event.symbol]
    if not relevant:
        return event.score >= default_minimum_score
    latest = max(relevant, key=lambda item: (
        item.updated_at if item.updated_at.tzinfo else item.updated_at.replace(tzinfo=timezone.utc)
    ).timestamp())
    return latest.enabled and event.score >= latest.minimum_score
