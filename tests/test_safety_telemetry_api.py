from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import sessionmaker

from app.api.main import health, require_gui_access
from app.settings import Settings
from app.telegram.security import KillSwitch, authorize, require_authorized
from app.telemetry.db import Base, build_engine
from app.telemetry.models import ControlStateRecord, EventRecord, ServiceHeartbeatRecord
from app.telemetry.repository import append_event_idempotently, canonical_event, record_heartbeat


def test_live_configuration_fails_closed():
    with pytest.raises(ValueError):
        Settings(dry_run=False)


def test_indicator_timeframes_must_be_collected_and_are_configurable():
    with pytest.raises(ValueError, match="must include indicator timeframes"):
        Settings(market_data_timeframes="5m,15m", indicator_htf_timeframes="15m,1h")
    settings = Settings(market_data_timeframes="15m,30m,1h,4h",
                        indicator_base_timeframe="15m",
                        indicator_htf_timeframes="30m,1h,4h",
                        indicator_ema_length=20)
    assert settings.indicator_htfs == ("30m", "1h", "4h")
    assert settings.indicator_ema_length == 20


def test_telegram_authorization_and_kill_switch():
    assert authorize(42, {42}) and not authorize(7, {42})
    with pytest.raises(PermissionError):
        require_authorized(7, {42})
    switch = KillSwitch()
    assert switch.permits_new_entry()
    switch.engage()
    assert not switch.permits_new_entry()


def test_idempotent_events():
    engine = build_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    now = datetime.now(timezone.utc)
    with Session() as session:
        def event(): return EventRecord(event_id="same", event_type="setup", occurred_at=now, payload={}, strategy_version="v", config_hash="c", git_sha="g")
        assert append_event_idempotently(session, event())
        assert not append_event_idempotently(session, event())


def test_health_api():
    engine = build_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    now = datetime.now(timezone.utc)
    with Session() as session:
        session.add(ControlStateRecord(key="paused", enabled=True, updated_at=now,
                                       updated_by="test", reason="test"))
        session.commit()
        response = health(Settings(), session)
        assert response.status == "degraded"
        assert response.database == "healthy"
        assert response.feed_status == "empty"
        assert response.paused is True
        assert response.services["platform-api"] == "healthy"


def test_heartbeat_upsert_preserves_one_current_row():
    engine = build_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as session:
        record_heartbeat(session, "market-data", "v1", "sha", details={"cycle": 1})
        record_heartbeat(session, "market-data", "v1", "sha", details={"cycle": 2})
        assert session.query(ServiceHeartbeatRecord).count() == 1
        assert session.get(ServiceHeartbeatRecord, "market-data").details == {"cycle": 2}


def test_canonical_event_requires_aware_time_and_populates_envelope():
    now = datetime.now(timezone.utc)
    event = canonical_event(
        event_id="evt-1", event_type="gate_evaluated", occurred_at=now,
        service="qualification", environment="test", strategy_version="v1",
        config_hash="cfg", git_sha="sha", correlation_id="episode:1",
        market_context={"exchange": "kraken", "symbol": "BTC/USDT"},
        decision_context={"decision": "rejected", "reason_codes": ["stale_data"]},
        measurements={"spread": {"value": "12", "unit": "bps", "version": "v1"}})
    assert event.schema_version == "1.0"
    assert event.occurred_at.utcoffset().total_seconds() == 0
    assert event.decision_context["reason_codes"] == ["stale_data"]
    with pytest.raises(ValueError, match="UTC-aware"):
        canonical_event(event_id="bad", event_type="bad", occurred_at=datetime.now(),
                        service="test", environment="test", strategy_version="v1",
                        config_hash="cfg", git_sha="sha", correlation_id="bad")


def test_gui_access_fails_closed_and_uses_dedicated_token():
    with pytest.raises(Exception):
        require_gui_access(None, Settings(gui_access_token=""))
    with pytest.raises(Exception):
        require_gui_access("wrong", Settings(gui_access_token="correct"))
    assert require_gui_access("correct", Settings(gui_access_token="correct")) is None
