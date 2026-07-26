ALTER TABLE setups RENAME COLUMN state TO current_state;
ALTER TABLE setups ADD COLUMN highest_state_reached VARCHAR(32);
UPDATE setups SET highest_state_reached = current_state WHERE highest_state_reached IS NULL;
ALTER TABLE setups ALTER COLUMN highest_state_reached SET NOT NULL;
CREATE INDEX IF NOT EXISTS ix_setups_current_state ON setups(current_state);
