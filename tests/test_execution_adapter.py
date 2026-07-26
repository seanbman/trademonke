from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import sessionmaker

from app.execution.adapter import ExecutionGateError, FreqtradeIntentAdapter
from app.telemetry.db import Base, build_engine
from app.telemetry.models import (ControlStateRecord, OrderEventRecord, RunManifestRecord,
                                  TradePlanRecord)


def make_session():
    engine = build_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def add_plan_and_manifest(Session):
    now = datetime.now(timezone.utc)
    with Session() as session:
        session.add(RunManifestRecord(
            id="run", run_type="baseline", started_at=now, completed_at=now,
            status="reviewed", configuration={},
            dataset_manifest={"untouched_test_sealed": True},
            dependency_manifest_id="lock", artifact_refs=[], strategy_version="v1",
            config_hash="cfg", git_sha="sha"))
        session.add(TradePlanRecord(
            id="plan", recommendation_id="rec",
            risk_evaluation_id="00000000-0000-0000-0000-000000000001", version=1,
            status="research_approved", entry_geometry={"lower": "100", "upper": "101"},
            targets=[{"price": "105"}], initial_stop={"price": "98"},
            trailing_policy={}, position_size={"quantity": "1"},
            validity={"execution_connected": False}, created_at=now,
            strategy_version="v1", config_hash="cfg", git_sha="sha"))
        session.commit()


def test_adapter_is_disabled_and_dry_run_is_locked():
    Session = make_session()
    with pytest.raises(ExecutionGateError, match="disabled"):
        FreqtradeIntentAdapter(Session, "disabled", "v1", "sha").create_intent("plan")
    with pytest.raises(ExecutionGateError, match="locked"):
        FreqtradeIntentAdapter(Session, "dry_run", "v1", "sha").create_intent("plan")


def test_shadow_intent_requires_reviewed_research_controls_and_is_idempotent():
    Session = make_session()
    adapter = FreqtradeIntentAdapter(Session, "shadow", "v1", "sha")
    with pytest.raises(ExecutionGateError, match="reviewed baseline"):
        adapter.create_intent("plan")
    add_plan_and_manifest(Session)
    first = adapter.create_intent("plan")
    second = adapter.create_intent("plan")
    assert first.id == second.id and first.order_snapshot["submitted"] is False
    reconciled = adapter.reconcile_shadow("plan", {"would_fill": True, "slippage_bps": "4"})
    assert reconciled.event_type == "reconciled"
    with Session() as session:
        assert session.query(OrderEventRecord).count() == 2
        session.add(ControlStateRecord(key="paused", enabled=True, updated_at=datetime.now(timezone.utc),
                                       updated_by="test", reason="test"))
        session.commit()
    with pytest.raises(ExecutionGateError, match="paused"):
        adapter.create_intent("another")
