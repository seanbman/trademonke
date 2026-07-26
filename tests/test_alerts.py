from datetime import datetime, timezone

from sqlalchemy.orm import sessionmaker

from app.telegram.alerts import (event_matches, set_enabled, set_minimum_score,
                                 setup_event_matches_default, toggle_component)
from app.telemetry.db import Base, build_engine
from app.telemetry.models import IndicatorAlertEventRecord


def event(event_type="component_change", component="fvg_retest", score=3):
    now = datetime.now(timezone.utc)
    return IndicatorAlertEventRecord(event_id=f"x-{event_type}-{component}-{score}", exchange="okx",
                                     symbol="BTC/USDT", timeframe="5m", candle_timestamp=now,
                                     direction="long", event_type=event_type, component=component,
                                     old_value="False", new_value="True", score=score,
                                     message="changed", created_at=now, delivered_at=None)


def test_alert_subscription_component_and_score_filters():
    engine = build_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as session:
        subscription = set_enabled(session, -123, 42, "BTC/USDT", True)
        assert event_matches(event(), subscription)
        subscription = toggle_component(session, -123, 42, "BTC/USDT", "fvg_retest")
        assert subscription.components == ["fvg_retest"]
        assert event_matches(event(), subscription)
        assert not event_matches(event(component="smt"), subscription)
        subscription = set_minimum_score(session, -123, 42, "BTC/USDT", 5)
        assert not event_matches(event("score_change", "score", 4), subscription)
        assert event_matches(event("score_change", "score", 5), subscription)


def test_setup_alerts_default_on_for_tracked_symbol_and_explicitly_disable():
    engine = build_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    setup_event = event("setup_transition", "setup_state", 4)
    with Session() as session:
        assert setup_event_matches_default(setup_event, [], tracked=True)
        assert not setup_event_matches_default(setup_event, [], tracked=False)
        disabled = set_enabled(session, -123, 42, "BTC/USDT", False)
        assert not setup_event_matches_default(setup_event, [disabled], tracked=True)
        enabled = set_enabled(session, -123, 42, "BTC/USDT", True)
        enabled.minimum_score = 6
        session.commit()
        assert not setup_event_matches_default(setup_event, [enabled], tracked=True)
        assert setup_event_matches_default(event("setup_transition", "setup_state", 6),
                                           [enabled], tracked=True)
