# Data model

`setups` stores the canonical setup identity, direction, component snapshot, current lifecycle state, highest state reached, and provenance (`strategy_version`, `config_hash`, `git_sha`). `setup_transitions` is append-only history with reasons.

`events` uses a unique deterministic `event_id` for idempotency and a versioned canonical envelope. The envelope records correlation/causation IDs, UTC occurrence and recording times, service and software provenance, market and decision context, typed measurements, severity, retry/latency metadata, and only safe external request identifiers. Applicable identifiers such as liquidity level, episode, setup, recommendation, plan, and trade belong in `market_context`; decisions, reason codes, gates, features, and data quality belong in `decision_context`.

Setup IDs are deterministic per structural episode. Current evidence includes the six component payloads, score, last processed candle, eligibility gate, and an explicit `execution_connected=false`. Near misses are retained from meaningful context, while empty candles do not create records. Current eligibility may downgrade while `highest_state_reached` preserves historical progress.

`liquidity_levels` stores stable observable level identities, Decimal geometry, status, measurements, and provenance. `strategy_episodes` materializes current and highest ordered state for one originating level. `episode_events` is the append-only, idempotent transition history with causal measurements and reason codes. `imbalances` stores stable FVG/IFVG geometry and may link to the originating episode. These tables establish persistence and API contracts; they do not yet claim that the ordered episode detector is implemented.

`indicator_snapshots` stores one long and short component structure per evaluated closed candle. `indicator_alert_events` stores deduplicated changes and delivery state. `alert_subscriptions` stores per-chat, per-user, per-symbol component filters and score thresholds. `backfill_requests` provides expiring Telegram confirmation, while `backfill_jobs` stores restart-safe execution and page-level progress.

PostgreSQL stores the closed candles used by the research engine and retains feature snapshots around qualified and near-qualified events. Dedicated tables preserve gate and risk decisions, versioned recommendations and trade plans, order/trade events, outcomes, immutable run manifests, operational incidents, GUI actions, alert acknowledgements, and reproducible chart-view manifests. Execution tables remain inert until the later Freqtrade dry-run gate is explicitly reached.

Recommendation versions are immutable geometry snapshots. Creating a newer valid recommendation marks the prior version superseded and appends lifecycle events; it does not overwrite the prior geometry. Trade plans reference exactly one approved risk evaluation and retain an explicit disconnected execution state.

Timestamps are UTC-aware. Prices used by domain and risk code are Decimal. JSON component values retain raw measurements, threshold/version metadata, weights, and data-quality states.
