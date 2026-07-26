from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.setups.engine import SetupLifecycleEngine
from app.telemetry.db import Base, build_engine
from app.telemetry.models import (ControlStateRecord, IndicatorAlertEventRecord,
                                  IndicatorSnapshotRecord, SetupRecord,
                                  SetupTransitionRecord)

NAMES = ("htf_bias", "liquidity_sweep", "fvg_retest",
         "retest_confirmation", "smt", "structure")


def snapshot(timestamp, score, direction="long", contextual=None):
    passed = set(NAMES[:score])
    if contextual:
        passed.add(contextual)
    components = {name: {"passed": name in passed} for name in NAMES}
    actual_score = sum(value["passed"] for value in components.values())
    return IndicatorSnapshotRecord(exchange="okx", symbol="BTC/USDT", timeframe="5m",
                                   candle_timestamp=timestamp, evaluated_at=timestamp,
                                   direction=direction, score=actual_score,
                                   setup_state="developing", components=components,
                                   strategy_version="v1")


def test_near_miss_lifecycle_dedup_and_pause_gate():
    db = build_engine("sqlite:///:memory:")
    Base.metadata.create_all(db)
    Session = sessionmaker(bind=db, expire_on_commit=False)
    engine = SetupLifecycleEngine(Session, "okx", "v1", "sha", detection_min_score=2, expiry_candles=40)
    now = datetime.now(timezone.utc)
    near_miss = snapshot(now, 0, contextual="structure")
    setup = engine.process(near_miss)
    assert setup.state == "detected" and setup.components["score"] == 1
    assert engine.process(near_miss).id == setup.id

    watch = engine.process(snapshot(now + timedelta(minutes=5), 4))
    assert watch.id == setup.id and watch.state == "watch"
    with Session() as session:
        session.add(ControlStateRecord(key="paused", enabled=True, updated_at=now,
                                       updated_by="test", reason="test"))
        session.commit()
    blocked = engine.process(snapshot(now + timedelta(minutes=10), 6))
    assert blocked.state == "watch"
    assert blocked.components["score"] == 4
    with Session() as session:
        session.get(ControlStateRecord, "paused").enabled = False
        session.commit()
    eligible = engine.process(snapshot(now + timedelta(minutes=15), 6))
    assert eligible.state == "eligible"
    with Session() as session:
        session.add(ControlStateRecord(key="kill_switch", enabled=True, updated_at=now,
                                       updated_by="test", reason="test"))
        session.commit()
    disarmed = engine.process(snapshot(now + timedelta(minutes=20), 6))
    assert disarmed.state == "strong_watch"
    assert disarmed.highest_state_reached == "eligible"
    with Session() as session:
        transitions = list(session.scalars(select(SetupTransitionRecord).where(
            SetupTransitionRecord.setup_id == setup.id)))
        alerts = list(session.scalars(select(IndicatorAlertEventRecord).where(
            IndicatorAlertEventRecord.event_type == "setup_transition")))
        assert [item.to_state for item in transitions] == ["detected", "watch", "eligible", "strong_watch"]
        assert len(alerts) == 4
        assert alerts[-1].new_value == "strong_watch" and alerts[-1].score == 6


def test_current_state_downgrades_while_highest_state_is_retained():
    db = build_engine("sqlite:///:memory:")
    Base.metadata.create_all(db)
    Session = sessionmaker(bind=db, expire_on_commit=False)
    engine = SetupLifecycleEngine(Session, "okx", "v1", "sha")
    now = datetime.now(timezone.utc)
    setup = engine.process(snapshot(now, 6))
    downgraded = engine.process(snapshot(now + timedelta(minutes=5), 4))
    assert downgraded.id == setup.id
    assert downgraded.state == "watch"
    assert downgraded.highest_state_reached == "eligible"

    weak_evidence = engine.process(snapshot(now + timedelta(minutes=10), 1))
    assert weak_evidence.state == "developing"
    assert weak_evidence.highest_state_reached == "eligible"


def test_actionable_setup_invalidates_without_same_candle_replacement():
    db = build_engine("sqlite:///:memory:")
    Base.metadata.create_all(db)
    Session = sessionmaker(bind=db, expire_on_commit=False)
    engine = SetupLifecycleEngine(Session, "okx", "v1", "sha")
    now = datetime.now(timezone.utc)
    setup = engine.process(snapshot(now, 4))
    terminal = engine.process(snapshot(now + timedelta(minutes=5), 0))
    assert terminal.id == setup.id and terminal.state == "invalidated"
    with Session() as session:
        assert session.query(SetupRecord).count() == 1


def test_context_near_miss_does_not_promote_when_trigger_turns_off():
    db = build_engine("sqlite:///:memory:")
    Base.metadata.create_all(db)
    Session = sessionmaker(bind=db, expire_on_commit=False)
    engine = SetupLifecycleEngine(Session, "okx", "v1", "sha")
    now = datetime.now(timezone.utc)
    setup = engine.process(snapshot(now, 0, contextual="liquidity_sweep"))
    assert setup.state == "detected"
    unchanged = engine.process(snapshot(now + timedelta(minutes=5), 0))
    assert unchanged.state == "detected"
    with Session() as session:
        transitions = list(session.scalars(select(SetupTransitionRecord).where(
            SetupTransitionRecord.setup_id == setup.id)))
        assert [item.to_state for item in transitions] == ["detected"]


def test_developing_setup_expires_after_configured_age():
    db = build_engine("sqlite:///:memory:")
    Base.metadata.create_all(db)
    Session = sessionmaker(bind=db, expire_on_commit=False)
    engine = SetupLifecycleEngine(Session, "okx", "v1", "sha", expiry_candles=2)
    now = datetime.now(timezone.utc)
    first = engine.process(snapshot(now, 2))
    replacement = engine.process(snapshot(now + timedelta(minutes=15), 2))
    assert replacement.id != first.id
    with Session() as session:
        assert session.get(SetupRecord, first.id).state == "expired"
