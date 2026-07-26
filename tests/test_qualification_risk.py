from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import sessionmaker

from app.domain.models import Direction
from app.domain.risk import RiskLimits, evaluate_risk
from app.qualification.service import MANDATORY_GATES, QualificationService
from app.telemetry.db import Base, build_engine
from app.telemetry.models import (GateEvaluationRecord, LiquidityLevelRecord,
                                  RiskEvaluationRecord, StrategyEpisodeRecord)


def test_risk_governor_rejects_geometry_costs_and_controls():
    limits = RiskLimits()
    approved = evaluate_risk(Direction.LONG, Decimal("100"), Decimal("98"),
                             Decimal("106"), Decimal("10000"), Decimal("10"),
                             Decimal("5"), limits)
    assert approved.approved and approved.notional <= limits.maximum_notional
    rejected = evaluate_risk(Direction.LONG, Decimal("100"), Decimal("101"),
                             Decimal("99"), Decimal("10000"), Decimal("50"),
                             Decimal("30"), limits, controls_clear=False)
    assert {"invalid_stop_side", "invalid_target_side", "spread_limit",
            "slippage_limit", "control_state_blocks_risk"} <= set(rejected.reason_codes)


def test_mandatory_gates_arm_disarm_and_risk_approval_are_persisted():
    engine = build_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    now = datetime.now(timezone.utc)
    provenance = {"strategy_version": "v1", "config_hash": "cfg", "git_sha": "sha"}
    with Session() as session:
        session.add(LiquidityLevelRecord(
            id="lvl", exchange="kraken", symbol="BTC/USDT", timeframe="5m",
            direction="long", level_type="swing_low", price=Decimal("100"),
            status="swept", observed_at=now, updated_at=now, measurements={}, **provenance))
        session.flush()
        session.add(StrategyEpisodeRecord(
            id="ep", liquidity_level_id="lvl", exchange="kraken", symbol="BTC/USDT",
            timeframe="5m", direction="long", current_state="retested",
            highest_state_reached="retested", started_at=now, updated_at=now,
            terminal_reason=None, current_gate_snapshot={}, **provenance))
        session.commit()
    service = QualificationService(Session, "v1", "sha")
    passing = {name: {"passed": True, "data_quality": "ok",
                      "reason_codes": [f"{name}_passed"]} for name in MANDATORY_GATES}
    assert service.evaluate_gates("ep", passing)
    with Session() as session:
        assert session.get(StrategyEpisodeRecord, "ep").current_state == "armed"
        assert session.query(GateEvaluationRecord).count() == 6
    rejection = service.evaluate_risk(
        "ep", entry=Decimal("100"), stop=Decimal("99"), target=Decimal("101"),
        account_balance=Decimal("10000"), spread_bps=Decimal("10"),
        slippage_bps=Decimal("5"), limits=RiskLimits(), controls_clear=True)
    assert rejection.decision == "rejected"
    approval = service.evaluate_risk(
        "ep", entry=Decimal("100"), stop=Decimal("98"), target=Decimal("106"),
        account_balance=Decimal("10000"), spread_bps=Decimal("10"),
        slippage_bps=Decimal("5"), limits=RiskLimits(), controls_clear=True)
    assert approval.decision == "approved"
    with Session() as session:
        assert session.get(StrategyEpisodeRecord, "ep").current_state == "approved"
        assert session.query(RiskEvaluationRecord).count() == 2
