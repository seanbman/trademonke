from datetime import datetime, timezone
from uuid import uuid4

from decimal import Decimal

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class SetupRecord(Base):
    __tablename__ = "setups"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    pair: Mapped[str] = mapped_column(String(40), index=True)
    timeframe: Mapped[str] = mapped_column(String(10))
    direction: Mapped[str] = mapped_column(String(8))
    state: Mapped[str] = mapped_column("current_state", String(32), index=True)
    highest_state_reached: Mapped[str] = mapped_column(String(32))
    components: Mapped[dict] = mapped_column(JSON)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    strategy_version: Mapped[str] = mapped_column(String(80))
    config_hash: Mapped[str] = mapped_column(String(64))
    git_sha: Mapped[str] = mapped_column(String(64))


class SetupTransitionRecord(Base):
    __tablename__ = "setup_transitions"
    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    setup_id: Mapped[str] = mapped_column(ForeignKey("setups.id"), index=True)
    from_state: Mapped[str] = mapped_column(String(32))
    to_state: Mapped[str] = mapped_column(String(32))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str] = mapped_column(Text)


class EventRecord(Base):
    __tablename__ = "events"
    __table_args__ = (UniqueConstraint("event_id"),)
    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    event_id: Mapped[str] = mapped_column(String(128))
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    sequence: Mapped[int | None] = mapped_column(nullable=True, unique=True)
    schema_version: Mapped[str] = mapped_column(String(16), default="1.0")
    correlation_id: Mapped[str] = mapped_column(String(128), index=True, default="standalone")
    causation_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    candle_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    service: Mapped[str] = mapped_column(String(64), default="platform")
    environment: Mapped[str] = mapped_column(String(32), default="development")
    payload: Mapped[dict] = mapped_column(JSON)
    market_context: Mapped[dict] = mapped_column(JSON, default=dict)
    decision_context: Mapped[dict] = mapped_column(JSON, default=dict)
    measurements: Mapped[dict] = mapped_column(JSON, default=dict)
    severity: Mapped[str] = mapped_column(String(16), default="info")
    retry_count: Mapped[int] = mapped_column(default=0)
    latency_ms: Mapped[int | None] = mapped_column(nullable=True)
    external_request_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    strategy_version: Mapped[str] = mapped_column(String(80))
    config_hash: Mapped[str] = mapped_column(String(64))
    git_sha: Mapped[str] = mapped_column(String(64))
    image_version: Mapped[str] = mapped_column(String(128), default="unknown")
    dependency_manifest_id: Mapped[str] = mapped_column(String(128), default="unknown")


class LiquidityLevelRecord(Base):
    __tablename__ = "liquidity_levels"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    exchange: Mapped[str] = mapped_column(String(32), index=True)
    symbol: Mapped[str] = mapped_column(String(40), index=True)
    timeframe: Mapped[str] = mapped_column(String(10))
    direction: Mapped[str] = mapped_column(String(8))
    level_type: Mapped[str] = mapped_column(String(32))
    price: Mapped[Decimal] = mapped_column(Numeric(38, 18))
    status: Mapped[str] = mapped_column(String(32), index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    measurements: Mapped[dict] = mapped_column(JSON)
    strategy_version: Mapped[str] = mapped_column(String(80))
    config_hash: Mapped[str] = mapped_column(String(64))
    git_sha: Mapped[str] = mapped_column(String(64))


class LiquidityLevelEventRecord(Base):
    __tablename__ = "liquidity_level_events"
    __table_args__ = (UniqueConstraint("event_id", name="uq_liquidity_level_event"),)
    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    event_id: Mapped[str] = mapped_column(String(160), nullable=False)
    liquidity_level_id: Mapped[str] = mapped_column(ForeignKey("liquidity_levels.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    candle_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reason_codes: Mapped[list] = mapped_column(JSON)
    measurements: Mapped[dict] = mapped_column(JSON)
    strategy_version: Mapped[str] = mapped_column(String(80))
    config_hash: Mapped[str] = mapped_column(String(64))
    git_sha: Mapped[str] = mapped_column(String(64))


class StrategyEpisodeRecord(Base):
    __tablename__ = "strategy_episodes"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    liquidity_level_id: Mapped[str] = mapped_column(ForeignKey("liquidity_levels.id"), index=True)
    exchange: Mapped[str] = mapped_column(String(32), index=True)
    symbol: Mapped[str] = mapped_column(String(40), index=True)
    timeframe: Mapped[str] = mapped_column(String(10))
    direction: Mapped[str] = mapped_column(String(8))
    current_state: Mapped[str] = mapped_column(String(32), index=True)
    highest_state_reached: Mapped[str] = mapped_column(String(32))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    terminal_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_gate_snapshot: Mapped[dict] = mapped_column(JSON)
    strategy_version: Mapped[str] = mapped_column(String(80))
    config_hash: Mapped[str] = mapped_column(String(64))
    git_sha: Mapped[str] = mapped_column(String(64))


class EpisodeEventRecord(Base):
    __tablename__ = "episode_events"
    __table_args__ = (UniqueConstraint("event_id", name="uq_episode_event"),)
    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    event_id: Mapped[str] = mapped_column(String(160), nullable=False)
    episode_id: Mapped[str] = mapped_column(ForeignKey("strategy_episodes.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    prior_state: Mapped[str | None] = mapped_column(String(32), nullable=True)
    current_state: Mapped[str] = mapped_column(String(32))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    candle_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reason_codes: Mapped[list] = mapped_column(JSON)
    measurements: Mapped[dict] = mapped_column(JSON)
    strategy_version: Mapped[str] = mapped_column(String(80))
    config_hash: Mapped[str] = mapped_column(String(64))
    git_sha: Mapped[str] = mapped_column(String(64))


class ImbalanceRecord(Base):
    __tablename__ = "imbalances"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    episode_id: Mapped[str | None] = mapped_column(ForeignKey("strategy_episodes.id"), nullable=True, index=True)
    exchange: Mapped[str] = mapped_column(String(32), index=True)
    symbol: Mapped[str] = mapped_column(String(40), index=True)
    timeframe: Mapped[str] = mapped_column(String(10))
    direction: Mapped[str] = mapped_column(String(8))
    imbalance_type: Mapped[str] = mapped_column(String(16))
    lower_price: Mapped[Decimal] = mapped_column(Numeric(38, 18))
    upper_price: Mapped[Decimal] = mapped_column(Numeric(38, 18))
    status: Mapped[str] = mapped_column(String(32), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    measurements: Mapped[dict] = mapped_column(JSON)
    strategy_version: Mapped[str] = mapped_column(String(80))
    config_hash: Mapped[str] = mapped_column(String(64))
    git_sha: Mapped[str] = mapped_column(String(64))


class RecommendationRecord(Base):
    __tablename__ = "recommendations"
    __table_args__ = (UniqueConstraint("episode_id", "recommendation_type", "version",
                                      name="uq_recommendation_version"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    episode_id: Mapped[str] = mapped_column(ForeignKey("strategy_episodes.id"), index=True)
    setup_id: Mapped[str | None] = mapped_column(ForeignKey("setups.id"), nullable=True)
    recommendation_type: Mapped[str] = mapped_column(String(32))
    version: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(32), index=True)
    geometry: Mapped[dict] = mapped_column(JSON)
    source_rules: Mapped[list] = mapped_column(JSON)
    source_object_ids: Mapped[list] = mapped_column(JSON)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    supersedes_id: Mapped[str | None] = mapped_column(ForeignKey("recommendations.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    strategy_version: Mapped[str] = mapped_column(String(80))
    config_hash: Mapped[str] = mapped_column(String(64))
    git_sha: Mapped[str] = mapped_column(String(64))


class GateEvaluationRecord(Base):
    __tablename__ = "gate_evaluations"
    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    episode_id: Mapped[str | None] = mapped_column(ForeignKey("strategy_episodes.id"), nullable=True, index=True)
    setup_id: Mapped[str | None] = mapped_column(ForeignKey("setups.id"), nullable=True)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    gate_name: Mapped[str] = mapped_column(String(64))
    mandatory: Mapped[bool] = mapped_column(Boolean)
    passed: Mapped[bool] = mapped_column(Boolean)
    reason_codes: Mapped[list] = mapped_column(JSON)
    inputs: Mapped[dict] = mapped_column(JSON)
    thresholds: Mapped[dict] = mapped_column(JSON)
    data_quality: Mapped[dict] = mapped_column(JSON)
    strategy_version: Mapped[str] = mapped_column(String(80))
    config_hash: Mapped[str] = mapped_column(String(64))
    git_sha: Mapped[str] = mapped_column(String(64))


class RiskEvaluationRecord(Base):
    __tablename__ = "risk_evaluations"
    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    episode_id: Mapped[str | None] = mapped_column(ForeignKey("strategy_episodes.id"), nullable=True, index=True)
    setup_id: Mapped[str | None] = mapped_column(ForeignKey("setups.id"), nullable=True)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    decision: Mapped[str] = mapped_column(String(32))
    reason_codes: Mapped[list] = mapped_column(JSON)
    inputs: Mapped[dict] = mapped_column(JSON)
    limits_snapshot: Mapped[dict] = mapped_column(JSON)
    size_calculation: Mapped[dict] = mapped_column(JSON)
    strategy_version: Mapped[str] = mapped_column(String(80))
    config_hash: Mapped[str] = mapped_column(String(64))
    git_sha: Mapped[str] = mapped_column(String(64))


class RecommendationEventRecord(Base):
    __tablename__ = "recommendation_events"
    __table_args__ = (UniqueConstraint("event_id", name="uq_recommendation_event"),)
    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    event_id: Mapped[str] = mapped_column(String(160), nullable=False)
    recommendation_id: Mapped[str] = mapped_column(ForeignKey("recommendations.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(64))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    prior_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    current_status: Mapped[str] = mapped_column(String(32))
    reason_codes: Mapped[list] = mapped_column(JSON)
    geometry_snapshot: Mapped[dict] = mapped_column(JSON)
    actor_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    strategy_version: Mapped[str] = mapped_column(String(80))
    config_hash: Mapped[str] = mapped_column(String(64))
    git_sha: Mapped[str] = mapped_column(String(64))


class TradePlanRecord(Base):
    __tablename__ = "trade_plans"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    recommendation_id: Mapped[str] = mapped_column(ForeignKey("recommendations.id"), index=True)
    risk_evaluation_id: Mapped[str] = mapped_column(ForeignKey("risk_evaluations.id"))
    version: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(32), index=True)
    entry_geometry: Mapped[dict] = mapped_column(JSON)
    targets: Mapped[list] = mapped_column(JSON)
    initial_stop: Mapped[dict] = mapped_column(JSON)
    trailing_policy: Mapped[dict] = mapped_column(JSON)
    position_size: Mapped[dict] = mapped_column(JSON)
    validity: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    strategy_version: Mapped[str] = mapped_column(String(80))
    config_hash: Mapped[str] = mapped_column(String(64))
    git_sha: Mapped[str] = mapped_column(String(64))


class AlertAcknowledgementRecord(Base):
    __tablename__ = "alert_acknowledgements"
    __table_args__ = (UniqueConstraint("alert_event_id", "user_id", name="uq_alert_ack_user"),)
    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    alert_event_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    acknowledged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    snoozed_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    escalation_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    navigation_target: Mapped[dict] = mapped_column(JSON)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class GuiActionEventRecord(Base):
    __tablename__ = "gui_action_events"
    __table_args__ = (UniqueConstraint("event_id", name="uq_gui_action_event"),)
    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    event_id: Mapped[str] = mapped_column(String(160), nullable=False)
    user_id: Mapped[str] = mapped_column(String(128))
    session_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    action_type: Mapped[str] = mapped_column(String(64))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    entity_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    proposal: Mapped[dict] = mapped_column(JSON)
    decision: Mapped[dict] = mapped_column(JSON)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    correlation_id: Mapped[str] = mapped_column(String(128))
    strategy_version: Mapped[str] = mapped_column(String(80))
    config_hash: Mapped[str] = mapped_column(String(64))
    git_sha: Mapped[str] = mapped_column(String(64))


class FeatureSnapshotRecord(Base):
    __tablename__ = "feature_snapshots"
    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    episode_id: Mapped[str | None] = mapped_column(ForeignKey("strategy_episodes.id"), nullable=True, index=True)
    setup_id: Mapped[str | None] = mapped_column(ForeignKey("setups.id"), nullable=True)
    candle_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    features: Mapped[dict] = mapped_column(JSON)
    thresholds: Mapped[dict] = mapped_column(JSON)
    data_quality: Mapped[dict] = mapped_column(JSON)
    calculation_versions: Mapped[dict] = mapped_column(JSON)
    strategy_version: Mapped[str] = mapped_column(String(80))
    config_hash: Mapped[str] = mapped_column(String(64))
    git_sha: Mapped[str] = mapped_column(String(64))


class OutcomeLabelRecord(Base):
    __tablename__ = "outcome_labels"
    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    episode_id: Mapped[str] = mapped_column(ForeignKey("strategy_episodes.id"), index=True)
    trade_plan_id: Mapped[str | None] = mapped_column(ForeignKey("trade_plans.id"), nullable=True)
    labelled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    label: Mapped[str] = mapped_column(String(64))
    target_stop_ordering: Mapped[str | None] = mapped_column(String(64), nullable=True)
    mae: Mapped[Decimal | None] = mapped_column(Numeric(38, 18), nullable=True)
    mfe: Mapped[Decimal | None] = mapped_column(Numeric(38, 18), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(nullable=True)
    path_metrics: Mapped[dict] = mapped_column(JSON)
    strategy_version: Mapped[str] = mapped_column(String(80))
    config_hash: Mapped[str] = mapped_column(String(64))
    git_sha: Mapped[str] = mapped_column(String(64))


class RunManifestRecord(Base):
    __tablename__ = "run_manifests"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_type: Mapped[str] = mapped_column(String(32))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32))
    configuration: Mapped[dict] = mapped_column(JSON)
    dataset_manifest: Mapped[dict] = mapped_column(JSON)
    dependency_manifest_id: Mapped[str] = mapped_column(String(128))
    artifact_refs: Mapped[list] = mapped_column(JSON)
    strategy_version: Mapped[str] = mapped_column(String(80))
    config_hash: Mapped[str] = mapped_column(String(64))
    git_sha: Mapped[str] = mapped_column(String(64))


class OrderEventRecord(Base):
    __tablename__ = "order_events"
    __table_args__ = (UniqueConstraint("event_id", name="uq_order_event"),)
    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    event_id: Mapped[str] = mapped_column(String(160), nullable=False)
    trade_plan_id: Mapped[str] = mapped_column(ForeignKey("trade_plans.id"), index=True)
    order_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    order_snapshot: Mapped[dict] = mapped_column(JSON)
    reason_codes: Mapped[list] = mapped_column(JSON)
    strategy_version: Mapped[str] = mapped_column(String(80))
    config_hash: Mapped[str] = mapped_column(String(64))
    git_sha: Mapped[str] = mapped_column(String(64))


class CandleRecord(Base):
    __tablename__ = "market_candles"
    __table_args__ = (UniqueConstraint("exchange", "symbol", "timeframe", "timestamp", name="uq_candle_identity"),)
    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    exchange: Mapped[str] = mapped_column(String(32), index=True)
    symbol: Mapped[str] = mapped_column(String(40), index=True)
    timeframe: Mapped[str] = mapped_column(String(10))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    open: Mapped[Decimal] = mapped_column(Numeric(38, 18))
    high: Mapped[Decimal] = mapped_column(Numeric(38, 18))
    low: Mapped[Decimal] = mapped_column(Numeric(38, 18))
    close: Mapped[Decimal] = mapped_column(Numeric(38, 18))
    volume: Mapped[Decimal] = mapped_column(Numeric(38, 18))
    source: Mapped[str] = mapped_column(String(32))
    closed: Mapped[bool] = mapped_column(Boolean, default=True)


class SupplementalMetricRecord(Base):
    __tablename__ = "supplemental_metrics"
    __table_args__ = (UniqueConstraint("exchange", "symbol", "metric_type", "timestamp", name="uq_supplement_identity"),)
    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    exchange: Mapped[str] = mapped_column(String(32), index=True)
    symbol: Mapped[str] = mapped_column(String(40), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    metric_type: Mapped[str] = mapped_column(String(32))
    values: Mapped[dict] = mapped_column(JSON)
    source: Mapped[str] = mapped_column(String(32))


class ControlStateRecord(Base):
    __tablename__ = "control_state"
    key: Mapped[str] = mapped_column(String(32), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_by: Mapped[str] = mapped_column(String(64), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)


class ServiceHeartbeatRecord(Base):
    __tablename__ = "service_heartbeats"
    service: Mapped[str] = mapped_column(String(64), primary_key=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    details: Mapped[dict] = mapped_column(JSON, nullable=False)
    strategy_version: Mapped[str] = mapped_column(String(80), nullable=False)
    git_sha: Mapped[str] = mapped_column(String(64), nullable=False)


class WatchlistAssetRecord(Base):
    __tablename__ = "watchlist_assets"
    symbol: Mapped[str] = mapped_column(String(40), primary_key=True)
    status: Mapped[str] = mapped_column(String(16), index=True)
    protected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_by: Mapped[str] = mapped_column(String(64), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)


class CandidateEvidenceRecord(Base):
    __tablename__ = "candidate_evidence"
    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    exchange: Mapped[str] = mapped_column(String(32), index=True)
    symbol: Mapped[str] = mapped_column(String(40), index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    quote_volume: Mapped[Decimal] = mapped_column(Numeric(38, 8))
    spread_bps: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    recommendation: Mapped[str] = mapped_column(String(32))
    reasons: Mapped[list] = mapped_column(JSON)


class WatchlistChangeRecord(Base):
    __tablename__ = "watchlist_changes"
    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(40), index=True)
    target_status: Mapped[str] = mapped_column(String(16))
    state: Mapped[str] = mapped_column(String(16), index=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    requested_by: Mapped[str] = mapped_column(String(64), nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)


class BackfillJobRecord(Base):
    __tablename__ = "backfill_jobs"
    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    exchange: Mapped[str] = mapped_column(String(32), index=True)
    symbol: Mapped[str] = mapped_column(String(40), index=True)
    timeframes: Mapped[list] = mapped_column(JSON)
    days: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(16), index=True)
    current_timeframe: Mapped[str | None] = mapped_column(String(10), nullable=True)
    completed_timeframes: Mapped[list] = mapped_column(JSON)
    rows_processed: Mapped[int] = mapped_column(nullable=False, default=0)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    requested_by: Mapped[str] = mapped_column(String(64), nullable=False)
    error_type: Mapped[str | None] = mapped_column(String(128), nullable=True)


class BackfillRequestRecord(Base):
    __tablename__ = "backfill_requests"
    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    exchange: Mapped[str] = mapped_column(String(32), index=True)
    symbol: Mapped[str] = mapped_column(String(40), index=True)
    timeframes: Mapped[list] = mapped_column(JSON)
    days: Mapped[int] = mapped_column(nullable=False)
    state: Mapped[str] = mapped_column(String(16), index=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    requested_by: Mapped[str] = mapped_column(String(64), nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    job_id: Mapped[str | None] = mapped_column(String(20), nullable=True)


class IndicatorSnapshotRecord(Base):
    __tablename__ = "indicator_snapshots"
    __table_args__ = (UniqueConstraint("exchange", "symbol", "timeframe", "candle_timestamp", "direction",
                                       name="uq_indicator_snapshot"),)
    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    exchange: Mapped[str] = mapped_column(String(32), index=True)
    symbol: Mapped[str] = mapped_column(String(40), index=True)
    timeframe: Mapped[str] = mapped_column(String(10))
    candle_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    direction: Mapped[str] = mapped_column(String(8))
    score: Mapped[int] = mapped_column(nullable=False)
    setup_state: Mapped[str] = mapped_column(String(32), nullable=False)
    components: Mapped[dict] = mapped_column(JSON)
    strategy_version: Mapped[str] = mapped_column(String(80), nullable=False)


class IndicatorAlertEventRecord(Base):
    __tablename__ = "indicator_alert_events"
    __table_args__ = (UniqueConstraint("event_id", name="uq_indicator_alert_event"),)
    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    event_id: Mapped[str] = mapped_column(String(160), nullable=False)
    exchange: Mapped[str] = mapped_column(String(32), index=True)
    symbol: Mapped[str] = mapped_column(String(40), index=True)
    timeframe: Mapped[str] = mapped_column(String(10))
    candle_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    direction: Mapped[str] = mapped_column(String(8))
    event_type: Mapped[str] = mapped_column(String(64))
    component: Mapped[str | None] = mapped_column(String(64), nullable=True)
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    score: Mapped[int] = mapped_column(nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AlertSubscriptionRecord(Base):
    __tablename__ = "alert_subscriptions"
    __table_args__ = (UniqueConstraint("chat_id", "user_id", "symbol", name="uq_alert_subscription"),)
    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    chat_id: Mapped[str] = mapped_column(String(64), index=True)
    user_id: Mapped[str] = mapped_column(String(64))
    symbol: Mapped[str] = mapped_column(String(40), index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    components: Mapped[list] = mapped_column(JSON)
    minimum_score: Mapped[int] = mapped_column(nullable=False, default=4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
