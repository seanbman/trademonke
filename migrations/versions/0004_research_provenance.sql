ALTER TABLE events ADD COLUMN schema_version VARCHAR(16) NOT NULL DEFAULT '1.0';
ALTER TABLE events ADD COLUMN correlation_id VARCHAR(128) NOT NULL DEFAULT 'standalone';
ALTER TABLE events ADD COLUMN causation_id VARCHAR(128);
ALTER TABLE events ADD COLUMN recorded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE events ADD COLUMN candle_timestamp TIMESTAMPTZ;
ALTER TABLE events ADD COLUMN service VARCHAR(64) NOT NULL DEFAULT 'platform';
ALTER TABLE events ADD COLUMN environment VARCHAR(32) NOT NULL DEFAULT 'development';
ALTER TABLE events ADD COLUMN market_context JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE events ADD COLUMN decision_context JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE events ADD COLUMN measurements JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE events ADD COLUMN severity VARCHAR(16) NOT NULL DEFAULT 'info';
ALTER TABLE events ADD COLUMN retry_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE events ADD COLUMN latency_ms INTEGER;
ALTER TABLE events ADD COLUMN external_request_id VARCHAR(128);
ALTER TABLE events ADD COLUMN image_version VARCHAR(128) NOT NULL DEFAULT 'unknown';
ALTER TABLE events ADD COLUMN dependency_manifest_id VARCHAR(128) NOT NULL DEFAULT 'unknown';
CREATE INDEX ix_events_correlation_id ON events(correlation_id);

CREATE TABLE liquidity_levels (
  id VARCHAR(64) PRIMARY KEY, exchange VARCHAR(32) NOT NULL, symbol VARCHAR(40) NOT NULL,
  timeframe VARCHAR(10) NOT NULL, direction VARCHAR(8) NOT NULL, level_type VARCHAR(32) NOT NULL,
  price NUMERIC(38,18) NOT NULL, status VARCHAR(32) NOT NULL, observed_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL, measurements JSONB NOT NULL, strategy_version VARCHAR(80) NOT NULL,
  config_hash VARCHAR(64) NOT NULL, git_sha VARCHAR(64) NOT NULL
);
CREATE INDEX ix_liquidity_levels_symbol ON liquidity_levels(symbol);
CREATE INDEX ix_liquidity_levels_status ON liquidity_levels(status);

CREATE TABLE strategy_episodes (
  id VARCHAR(64) PRIMARY KEY, liquidity_level_id VARCHAR(64) NOT NULL REFERENCES liquidity_levels(id),
  exchange VARCHAR(32) NOT NULL, symbol VARCHAR(40) NOT NULL, timeframe VARCHAR(10) NOT NULL,
  direction VARCHAR(8) NOT NULL, current_state VARCHAR(32) NOT NULL,
  highest_state_reached VARCHAR(32) NOT NULL, started_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL, terminal_reason TEXT, current_gate_snapshot JSONB NOT NULL,
  strategy_version VARCHAR(80) NOT NULL, config_hash VARCHAR(64) NOT NULL, git_sha VARCHAR(64) NOT NULL
);
CREATE INDEX ix_strategy_episodes_symbol ON strategy_episodes(symbol);
CREATE INDEX ix_strategy_episodes_current_state ON strategy_episodes(current_state);

CREATE TABLE episode_events (
  id UUID PRIMARY KEY, event_id VARCHAR(160) NOT NULL UNIQUE,
  episode_id VARCHAR(64) NOT NULL REFERENCES strategy_episodes(id), event_type VARCHAR(64) NOT NULL,
  prior_state VARCHAR(32), current_state VARCHAR(32) NOT NULL, occurred_at TIMESTAMPTZ NOT NULL,
  candle_timestamp TIMESTAMPTZ NOT NULL, reason_codes JSONB NOT NULL, measurements JSONB NOT NULL,
  strategy_version VARCHAR(80) NOT NULL, config_hash VARCHAR(64) NOT NULL, git_sha VARCHAR(64) NOT NULL
);
CREATE INDEX ix_episode_events_episode_id ON episode_events(episode_id);

CREATE TABLE imbalances (
  id VARCHAR(64) PRIMARY KEY, episode_id VARCHAR(64) REFERENCES strategy_episodes(id),
  exchange VARCHAR(32) NOT NULL, symbol VARCHAR(40) NOT NULL, timeframe VARCHAR(10) NOT NULL,
  direction VARCHAR(8) NOT NULL, imbalance_type VARCHAR(16) NOT NULL,
  lower_price NUMERIC(38,18) NOT NULL, upper_price NUMERIC(38,18) NOT NULL,
  status VARCHAR(32) NOT NULL, created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL,
  measurements JSONB NOT NULL, strategy_version VARCHAR(80) NOT NULL,
  config_hash VARCHAR(64) NOT NULL, git_sha VARCHAR(64) NOT NULL
);
CREATE INDEX ix_imbalances_episode_id ON imbalances(episode_id);
CREATE INDEX ix_imbalances_symbol ON imbalances(symbol);
