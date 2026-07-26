CREATE TABLE IF NOT EXISTS setups (
  id VARCHAR(64) PRIMARY KEY, pair VARCHAR(40) NOT NULL, timeframe VARCHAR(10) NOT NULL,
  direction VARCHAR(8) NOT NULL, state VARCHAR(32) NOT NULL, components JSONB NOT NULL,
  detected_at TIMESTAMPTZ NOT NULL, strategy_version VARCHAR(80) NOT NULL,
  config_hash VARCHAR(64) NOT NULL, git_sha VARCHAR(64) NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_setups_state ON setups(state);
CREATE INDEX IF NOT EXISTS ix_setups_detected_at ON setups(detected_at);
CREATE TABLE IF NOT EXISTS setup_transitions (
  id UUID PRIMARY KEY, setup_id VARCHAR(64) NOT NULL REFERENCES setups(id), from_state VARCHAR(32) NOT NULL,
  to_state VARCHAR(32) NOT NULL, occurred_at TIMESTAMPTZ NOT NULL, reason TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
  id UUID PRIMARY KEY, event_id VARCHAR(128) NOT NULL UNIQUE, event_type VARCHAR(64) NOT NULL,
  occurred_at TIMESTAMPTZ NOT NULL, payload JSONB NOT NULL, strategy_version VARCHAR(80) NOT NULL,
  config_hash VARCHAR(64) NOT NULL, git_sha VARCHAR(64) NOT NULL
);
CREATE TABLE IF NOT EXISTS market_candles (
  id UUID PRIMARY KEY, exchange VARCHAR(32) NOT NULL, symbol VARCHAR(40) NOT NULL,
  timeframe VARCHAR(10) NOT NULL, timestamp TIMESTAMPTZ NOT NULL,
  open NUMERIC(38,18) NOT NULL, high NUMERIC(38,18) NOT NULL, low NUMERIC(38,18) NOT NULL,
  close NUMERIC(38,18) NOT NULL, volume NUMERIC(38,18) NOT NULL,
  source VARCHAR(32) NOT NULL, closed BOOLEAN NOT NULL DEFAULT TRUE,
  CONSTRAINT uq_candle_identity UNIQUE(exchange, symbol, timeframe, timestamp)
);
CREATE INDEX IF NOT EXISTS ix_market_candles_lookup ON market_candles(exchange, symbol, timeframe, timestamp DESC);
CREATE TABLE IF NOT EXISTS supplemental_metrics (
  id UUID PRIMARY KEY, exchange VARCHAR(32) NOT NULL, symbol VARCHAR(40) NOT NULL,
  timestamp TIMESTAMPTZ NOT NULL, metric_type VARCHAR(32) NOT NULL, values JSONB NOT NULL,
  source VARCHAR(32) NOT NULL,
  CONSTRAINT uq_supplement_identity UNIQUE(exchange, symbol, metric_type, timestamp)
);
CREATE TABLE IF NOT EXISTS control_state (
  key VARCHAR(32) PRIMARY KEY, enabled BOOLEAN NOT NULL, updated_at TIMESTAMPTZ NOT NULL,
  updated_by VARCHAR(64) NOT NULL, reason TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS watchlist_assets (
  symbol VARCHAR(40) PRIMARY KEY, status VARCHAR(16) NOT NULL, protected BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL,
  updated_by VARCHAR(64) NOT NULL, reason TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_watchlist_assets_status ON watchlist_assets(status);
CREATE TABLE IF NOT EXISTS candidate_evidence (
  id UUID PRIMARY KEY, exchange VARCHAR(32) NOT NULL, symbol VARCHAR(40) NOT NULL,
  observed_at TIMESTAMPTZ NOT NULL, quote_volume NUMERIC(38,8) NOT NULL,
  spread_bps NUMERIC(20,8), recommendation VARCHAR(32) NOT NULL, reasons JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_candidate_evidence_symbol_time ON candidate_evidence(symbol, observed_at DESC);
CREATE TABLE IF NOT EXISTS watchlist_changes (
  id VARCHAR(20) PRIMARY KEY, symbol VARCHAR(40) NOT NULL, target_status VARCHAR(16) NOT NULL,
  state VARCHAR(16) NOT NULL, requested_at TIMESTAMPTZ NOT NULL, expires_at TIMESTAMPTZ NOT NULL,
  requested_by VARCHAR(64) NOT NULL, confirmed_at TIMESTAMPTZ, confirmed_by VARCHAR(64), reason TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS backfill_jobs (
  id VARCHAR(20) PRIMARY KEY, exchange VARCHAR(32) NOT NULL, symbol VARCHAR(40) NOT NULL,
  timeframes JSONB NOT NULL, days INTEGER NOT NULL, status VARCHAR(16) NOT NULL,
  current_timeframe VARCHAR(10), completed_timeframes JSONB NOT NULL, rows_processed INTEGER NOT NULL DEFAULT 0,
  requested_at TIMESTAMPTZ NOT NULL, started_at TIMESTAMPTZ, updated_at TIMESTAMPTZ NOT NULL,
  completed_at TIMESTAMPTZ, requested_by VARCHAR(64) NOT NULL, error_type VARCHAR(128)
);
CREATE INDEX IF NOT EXISTS ix_backfill_jobs_status_requested ON backfill_jobs(status, requested_at);
CREATE TABLE IF NOT EXISTS backfill_requests (
  id VARCHAR(20) PRIMARY KEY, exchange VARCHAR(32) NOT NULL, symbol VARCHAR(40) NOT NULL,
  timeframes JSONB NOT NULL, days INTEGER NOT NULL, state VARCHAR(16) NOT NULL,
  requested_at TIMESTAMPTZ NOT NULL, expires_at TIMESTAMPTZ NOT NULL, requested_by VARCHAR(64) NOT NULL,
  confirmed_at TIMESTAMPTZ, confirmed_by VARCHAR(64), job_id VARCHAR(20)
);
CREATE TABLE IF NOT EXISTS indicator_snapshots (
  id UUID PRIMARY KEY, exchange VARCHAR(32) NOT NULL, symbol VARCHAR(40) NOT NULL,
  timeframe VARCHAR(10) NOT NULL, candle_timestamp TIMESTAMPTZ NOT NULL, evaluated_at TIMESTAMPTZ NOT NULL,
  direction VARCHAR(8) NOT NULL, score INTEGER NOT NULL, setup_state VARCHAR(32) NOT NULL,
  components JSONB NOT NULL, strategy_version VARCHAR(80) NOT NULL,
  CONSTRAINT uq_indicator_snapshot UNIQUE(exchange, symbol, timeframe, candle_timestamp, direction)
);
CREATE TABLE IF NOT EXISTS indicator_alert_events (
  id UUID PRIMARY KEY, event_id VARCHAR(160) NOT NULL UNIQUE, exchange VARCHAR(32) NOT NULL,
  symbol VARCHAR(40) NOT NULL, timeframe VARCHAR(10) NOT NULL, candle_timestamp TIMESTAMPTZ NOT NULL,
  direction VARCHAR(8) NOT NULL, event_type VARCHAR(64) NOT NULL, component VARCHAR(64),
  old_value TEXT, new_value TEXT, score INTEGER NOT NULL, message TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL, delivered_at TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS alert_subscriptions (
  id UUID PRIMARY KEY, chat_id VARCHAR(64) NOT NULL, user_id VARCHAR(64) NOT NULL,
  symbol VARCHAR(40) NOT NULL, enabled BOOLEAN NOT NULL, components JSONB NOT NULL,
  minimum_score INTEGER NOT NULL, created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL,
  CONSTRAINT uq_alert_subscription UNIQUE(chat_id, user_id, symbol)
);
