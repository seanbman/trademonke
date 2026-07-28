CREATE TABLE chart_annotations (
  id UUID PRIMARY KEY,
  exchange VARCHAR(32) NOT NULL,
  symbol VARCHAR(40) NOT NULL,
  timeframe VARCHAR(10) NOT NULL,
  kind VARCHAR(32) NOT NULL,
  label VARCHAR(64) NOT NULL,
  checklist_item VARCHAR(128),
  geometry JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL,
  created_by VARCHAR(64) NOT NULL,
  active BOOLEAN NOT NULL DEFAULT TRUE
);
CREATE INDEX ix_chart_annotations_symbol_tf ON chart_annotations(exchange, symbol, timeframe, active);

CREATE TABLE watchlist_invalidation_events (
  id UUID PRIMARY KEY,
  event_id VARCHAR(160) NOT NULL UNIQUE,
  exchange VARCHAR(32) NOT NULL,
  symbol VARCHAR(40) NOT NULL,
  timeframe VARCHAR(10) NOT NULL,
  event_type VARCHAR(64) NOT NULL,
  source VARCHAR(64) NOT NULL,
  annotation_id UUID REFERENCES chart_annotations(id),
  liquidity_level_id VARCHAR(64),
  candle_timestamp TIMESTAMPTZ NOT NULL,
  message TEXT NOT NULL,
  measurements JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  delivered_at TIMESTAMPTZ
);
CREATE INDEX ix_watchlist_invalidation_symbol ON watchlist_invalidation_events(symbol, created_at);
CREATE INDEX ix_watchlist_invalidation_type ON watchlist_invalidation_events(event_type, created_at);
