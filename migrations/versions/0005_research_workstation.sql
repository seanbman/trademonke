ALTER TABLE events ADD COLUMN sequence BIGSERIAL UNIQUE;

CREATE TABLE liquidity_level_events (
  id UUID PRIMARY KEY, event_id VARCHAR(160) NOT NULL UNIQUE, liquidity_level_id VARCHAR(64) NOT NULL REFERENCES liquidity_levels(id),
  event_type VARCHAR(64) NOT NULL, occurred_at TIMESTAMPTZ NOT NULL, candle_timestamp TIMESTAMPTZ NOT NULL,
  reason_codes JSONB NOT NULL, measurements JSONB NOT NULL, strategy_version VARCHAR(80) NOT NULL,
  config_hash VARCHAR(64) NOT NULL, git_sha VARCHAR(64) NOT NULL
);
CREATE INDEX ix_liquidity_level_events_level ON liquidity_level_events(liquidity_level_id, occurred_at);

CREATE TABLE feature_snapshots (
  id UUID PRIMARY KEY, episode_id VARCHAR(64) REFERENCES strategy_episodes(id), setup_id VARCHAR(64) REFERENCES setups(id),
  candle_timestamp TIMESTAMPTZ NOT NULL, features JSONB NOT NULL, thresholds JSONB NOT NULL,
  data_quality JSONB NOT NULL, calculation_versions JSONB NOT NULL, strategy_version VARCHAR(80) NOT NULL,
  config_hash VARCHAR(64) NOT NULL, git_sha VARCHAR(64) NOT NULL
);
CREATE INDEX ix_feature_snapshots_episode ON feature_snapshots(episode_id, candle_timestamp);

CREATE TABLE gate_evaluations (
  id UUID PRIMARY KEY, episode_id VARCHAR(64) REFERENCES strategy_episodes(id), setup_id VARCHAR(64) REFERENCES setups(id),
  evaluated_at TIMESTAMPTZ NOT NULL, gate_name VARCHAR(64) NOT NULL, mandatory BOOLEAN NOT NULL,
  passed BOOLEAN NOT NULL, reason_codes JSONB NOT NULL, inputs JSONB NOT NULL, thresholds JSONB NOT NULL,
  data_quality JSONB NOT NULL, strategy_version VARCHAR(80) NOT NULL, config_hash VARCHAR(64) NOT NULL, git_sha VARCHAR(64) NOT NULL
);
CREATE INDEX ix_gate_evaluations_episode ON gate_evaluations(episode_id, evaluated_at);

CREATE TABLE risk_evaluations (
  id UUID PRIMARY KEY, episode_id VARCHAR(64) REFERENCES strategy_episodes(id), setup_id VARCHAR(64) REFERENCES setups(id),
  evaluated_at TIMESTAMPTZ NOT NULL, decision VARCHAR(32) NOT NULL, reason_codes JSONB NOT NULL,
  inputs JSONB NOT NULL, limits_snapshot JSONB NOT NULL, size_calculation JSONB NOT NULL,
  strategy_version VARCHAR(80) NOT NULL, config_hash VARCHAR(64) NOT NULL, git_sha VARCHAR(64) NOT NULL
);
CREATE INDEX ix_risk_evaluations_episode ON risk_evaluations(episode_id, evaluated_at);

CREATE TABLE recommendations (
  id VARCHAR(64) PRIMARY KEY, episode_id VARCHAR(64) NOT NULL REFERENCES strategy_episodes(id), setup_id VARCHAR(64) REFERENCES setups(id),
  recommendation_type VARCHAR(32) NOT NULL, version INTEGER NOT NULL, status VARCHAR(32) NOT NULL,
  geometry JSONB NOT NULL, source_rules JSONB NOT NULL, source_object_ids JSONB NOT NULL,
  valid_from TIMESTAMPTZ NOT NULL, valid_until TIMESTAMPTZ, supersedes_id VARCHAR(64) REFERENCES recommendations(id),
  created_at TIMESTAMPTZ NOT NULL, strategy_version VARCHAR(80) NOT NULL, config_hash VARCHAR(64) NOT NULL, git_sha VARCHAR(64) NOT NULL,
  CONSTRAINT uq_recommendation_version UNIQUE(episode_id, recommendation_type, version)
);
CREATE INDEX ix_recommendations_episode_status ON recommendations(episode_id, status);

CREATE TABLE recommendation_events (
  id UUID PRIMARY KEY, event_id VARCHAR(160) NOT NULL UNIQUE, recommendation_id VARCHAR(64) NOT NULL REFERENCES recommendations(id),
  event_type VARCHAR(64) NOT NULL, occurred_at TIMESTAMPTZ NOT NULL, prior_status VARCHAR(32), current_status VARCHAR(32) NOT NULL,
  reason_codes JSONB NOT NULL, geometry_snapshot JSONB NOT NULL, actor_id VARCHAR(128),
  strategy_version VARCHAR(80) NOT NULL, config_hash VARCHAR(64) NOT NULL, git_sha VARCHAR(64) NOT NULL
);

CREATE TABLE trade_plans (
  id VARCHAR(64) PRIMARY KEY, recommendation_id VARCHAR(64) NOT NULL REFERENCES recommendations(id),
  risk_evaluation_id UUID NOT NULL REFERENCES risk_evaluations(id), version INTEGER NOT NULL, status VARCHAR(32) NOT NULL,
  entry_geometry JSONB NOT NULL, targets JSONB NOT NULL, initial_stop JSONB NOT NULL, trailing_policy JSONB NOT NULL,
  position_size JSONB NOT NULL, validity JSONB NOT NULL, created_at TIMESTAMPTZ NOT NULL,
  strategy_version VARCHAR(80) NOT NULL, config_hash VARCHAR(64) NOT NULL, git_sha VARCHAR(64) NOT NULL
);

CREATE TABLE order_events (
  id UUID PRIMARY KEY, event_id VARCHAR(160) NOT NULL UNIQUE, trade_plan_id VARCHAR(64) NOT NULL REFERENCES trade_plans(id),
  order_id VARCHAR(128), event_type VARCHAR(64) NOT NULL, occurred_at TIMESTAMPTZ NOT NULL,
  order_snapshot JSONB NOT NULL, reason_codes JSONB NOT NULL, strategy_version VARCHAR(80) NOT NULL,
  config_hash VARCHAR(64) NOT NULL, git_sha VARCHAR(64) NOT NULL
);

CREATE TABLE trade_events (
  id UUID PRIMARY KEY, event_id VARCHAR(160) NOT NULL UNIQUE, trade_plan_id VARCHAR(64) NOT NULL REFERENCES trade_plans(id),
  trade_id VARCHAR(128), event_type VARCHAR(64) NOT NULL, occurred_at TIMESTAMPTZ NOT NULL,
  trade_snapshot JSONB NOT NULL, reason_codes JSONB NOT NULL, strategy_version VARCHAR(80) NOT NULL,
  config_hash VARCHAR(64) NOT NULL, git_sha VARCHAR(64) NOT NULL
);

CREATE TABLE outcome_labels (
  id UUID PRIMARY KEY, episode_id VARCHAR(64) NOT NULL REFERENCES strategy_episodes(id), trade_plan_id VARCHAR(64) REFERENCES trade_plans(id),
  labelled_at TIMESTAMPTZ NOT NULL, label VARCHAR(64) NOT NULL, target_stop_ordering VARCHAR(64),
  mae NUMERIC(38,18), mfe NUMERIC(38,18), duration_seconds BIGINT, path_metrics JSONB NOT NULL,
  strategy_version VARCHAR(80) NOT NULL, config_hash VARCHAR(64) NOT NULL, git_sha VARCHAR(64) NOT NULL
);

CREATE TABLE run_manifests (
  id VARCHAR(64) PRIMARY KEY, run_type VARCHAR(32) NOT NULL, started_at TIMESTAMPTZ NOT NULL, completed_at TIMESTAMPTZ,
  status VARCHAR(32) NOT NULL, configuration JSONB NOT NULL, dataset_manifest JSONB NOT NULL,
  dependency_manifest_id VARCHAR(128) NOT NULL, artifact_refs JSONB NOT NULL,
  strategy_version VARCHAR(80) NOT NULL, config_hash VARCHAR(64) NOT NULL, git_sha VARCHAR(64) NOT NULL
);

CREATE TABLE incidents (
  id VARCHAR(64) PRIMARY KEY, service VARCHAR(64) NOT NULL, severity VARCHAR(16) NOT NULL, status VARCHAR(32) NOT NULL,
  opened_at TIMESTAMPTZ NOT NULL, resolved_at TIMESTAMPTZ, error_type VARCHAR(128), summary TEXT NOT NULL,
  safe_details JSONB NOT NULL, correlation_id VARCHAR(128), git_sha VARCHAR(64) NOT NULL
);

CREATE TABLE gui_action_events (
  id UUID PRIMARY KEY, event_id VARCHAR(160) NOT NULL UNIQUE, user_id VARCHAR(128) NOT NULL, session_id VARCHAR(128),
  action_type VARCHAR(64) NOT NULL, occurred_at TIMESTAMPTZ NOT NULL, entity_type VARCHAR(64), entity_id VARCHAR(128),
  proposal JSONB NOT NULL, decision JSONB NOT NULL, reason TEXT, correlation_id VARCHAR(128) NOT NULL,
  strategy_version VARCHAR(80) NOT NULL, config_hash VARCHAR(64) NOT NULL, git_sha VARCHAR(64) NOT NULL
);

CREATE TABLE alert_acknowledgements (
  id UUID PRIMARY KEY, alert_event_id VARCHAR(160) NOT NULL, user_id VARCHAR(128) NOT NULL,
  acknowledged_at TIMESTAMPTZ NOT NULL, snoozed_until TIMESTAMPTZ, escalation_status VARCHAR(32),
  navigation_target JSONB NOT NULL, note TEXT, CONSTRAINT uq_alert_ack_user UNIQUE(alert_event_id, user_id)
);

CREATE TABLE chart_snapshot_manifests (
  id VARCHAR(64) PRIMARY KEY, user_id VARCHAR(128), episode_id VARCHAR(64) REFERENCES strategy_episodes(id),
  symbol VARCHAR(40) NOT NULL, timeframes JSONB NOT NULL, range_start TIMESTAMPTZ NOT NULL, range_end TIMESTAMPTZ NOT NULL,
  overlay_versions JSONB NOT NULL, visible_object_ids JSONB NOT NULL, display_version VARCHAR(32) NOT NULL,
  artifact_ref TEXT, created_at TIMESTAMPTZ NOT NULL, strategy_version VARCHAR(80) NOT NULL,
  config_hash VARCHAR(64) NOT NULL, git_sha VARCHAR(64) NOT NULL
);
