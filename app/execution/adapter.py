from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from app.settings import get_settings

from app.telemetry.models import (ControlStateRecord, OrderEventRecord, RunManifestRecord,
                                  TradePlanRecord)


class ExecutionGateError(RuntimeError):
    pass


class FreqtradeIntentAdapter:
    """Creates auditable shadow intents; it contains no exchange or CCXT order methods."""

    def __init__(self, session_factory, mode: str, strategy_version: str, git_sha: str):
        if mode not in {"disabled", "shadow", "dry_run"}:
            raise ValueError("invalid execution mode")
        self.session_factory = session_factory
        self.mode = mode
        self.strategy_version = strategy_version
        self.git_sha = git_sha

    def create_intent(self, trade_plan_id: str) -> OrderEventRecord:
        with self.session_factory() as session:
            if self.mode == "disabled":
                raise ExecutionGateError("execution adapter is disabled")
            if self.mode == "dry_run":
                raise ExecutionGateError(
                    "dry-run submission is locked until reviewed shadow reconciliation")
            self._require_controls_clear(session)
            self._require_reviewed_research(session)
            plan = session.get(TradePlanRecord, trade_plan_id)
            if plan is None or plan.status != "research_approved":
                raise ExecutionGateError("trade plan is not research-approved")
            if plan.validity.get("execution_connected") is not False:
                raise ExecutionGateError("trade plan execution boundary is inconsistent")
            event_id = f"shadow:{plan.id}:v{plan.version}"
            existing = session.scalar(select(OrderEventRecord).where(
                OrderEventRecord.event_id == event_id))
            if existing:
                return existing
            now = datetime.now(timezone.utc)
            event = OrderEventRecord(
                event_id=event_id, trade_plan_id=plan.id, order_id=None,
                event_type="shadow_order", occurred_at=now,
                order_snapshot={"entry": plan.entry_geometry, "targets": plan.targets,
                                "stop": plan.initial_stop, "position_size": plan.position_size,
                                "submitted": False, "authority": "freqtrade",
                                "mode": "shadow"},
                reason_codes=["reviewed_research_gate", "shadow_only_no_submission"],
                strategy_version=self.strategy_version, config_hash=get_settings().config_hash, git_sha=self.git_sha)
            session.add(event)
            session.commit()
            return event

    def reconcile_shadow(self, trade_plan_id: str, market_observation: dict) -> OrderEventRecord:
        with self.session_factory() as session:
            intent = session.scalar(select(OrderEventRecord).where(
                OrderEventRecord.trade_plan_id == trade_plan_id,
                OrderEventRecord.event_type == "shadow_order"))
            if intent is None:
                raise ExecutionGateError("shadow intent not found")
            event_id = f"shadow-reconciled:{intent.event_id}"
            existing = session.scalar(select(OrderEventRecord).where(
                OrderEventRecord.event_id == event_id))
            if existing:
                return existing
            event = OrderEventRecord(
                event_id=event_id, trade_plan_id=trade_plan_id, order_id=None,
                event_type="reconciled", occurred_at=datetime.now(timezone.utc),
                order_snapshot={"intent_event_id": intent.event_id,
                                "market_observation": market_observation,
                                "submitted": False}, reason_codes=["shadow_reconciliation"],
                strategy_version=self.strategy_version, config_hash=get_settings().config_hash, git_sha=self.git_sha)
            session.add(event)
            session.commit()
            return event

    @staticmethod
    def _require_controls_clear(session):
        for key in ("paused", "kill_switch"):
            control = session.get(ControlStateRecord, key)
            if control and control.enabled:
                raise ExecutionGateError(f"persisted {key} blocks new intents")

    @staticmethod
    def _require_reviewed_research(session):
        reviewed = session.scalar(select(RunManifestRecord.id).where(
            RunManifestRecord.run_type == "baseline",
            RunManifestRecord.status == "reviewed",
            RunManifestRecord.dataset_manifest["untouched_test_sealed"].as_boolean().is_(True)
        ).limit(1))
        if not reviewed:
            raise ExecutionGateError("reviewed baseline research manifest is required")
