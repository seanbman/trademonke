CREATE TABLE service_heartbeats (
  service VARCHAR(64) PRIMARY KEY,
  observed_at TIMESTAMPTZ NOT NULL,
  status VARCHAR(32) NOT NULL,
  details JSONB NOT NULL,
  strategy_version VARCHAR(80) NOT NULL,
  git_sha VARCHAR(64) NOT NULL
);
CREATE INDEX ix_service_heartbeats_observed_at ON service_heartbeats(observed_at);
