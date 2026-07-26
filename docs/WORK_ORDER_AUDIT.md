# Technical development specification conformance audit

Audit basis: `docs/prompt_notes/trading_bot_technical_development_specification_gui_updated.pdf`, revision 1.1. Audit date: 2026-07-11. Branch: `develop/pine-parity-validation`.

## Executive finding

The repository now contains the requested fail-closed foundation, persistence contracts, liquidity and episode primitives, qualification/risk services, recommendations, research tooling, shadow boundary, and a read-only workstation. The complete work order is **not operationally complete**. Phase 4 has no labelled ordered-episode dataset or validation evidence, so the specification explicitly prohibits Phase 5 dry-run connection. The GUI dry-run console consequently remains locked.

Passing unit tests demonstrate implementation consistency; they do not substitute for migrations against PostgreSQL, continuous replay, baseline expectancy evidence, shadow reconciliation, restore drills, or Freqtrade validation.

## Backlog status

| # | Work item | Status | Audit note |
|---|---|---|---|
| 1 | Compose networking | Implemented, unverified locally | PostgreSQL is internal-only and outbound services have a separate network. Docker is unavailable on the audit host. |
| 2 | Normalize configuration | Implemented | Canonical `PLATFORM_*` names are present in example and real local environment files. The local GUI token is intentionally empty and fails closed. |
| 3 | Pause/kill semantics | Implemented | Setup processing and shadow intents check persisted controls; exits remain outside these research paths. |
| 4 | Eligibility downgrade | Implemented | Current and highest states are separate and tested. |
| 5 | CI and dependency pinning | Implemented with gap | Python and GUI locks plus CI exist. CI does not run the Freqtrade strategy check. |
| 6 | Real health and heartbeats | Partially implemented | Database, feed, controls and recorded services are reported. Services that never heartbeat are not explicitly reported missing; exchange/Freqtrade reachability is absent. |
| 7 | Migrations | Implemented, PostgreSQL boot not locally verified | Ordered checksummed migrations and CI PostgreSQL boot exist. The legacy local SQLite database is not upgradeable by the PostgreSQL SQL migrations. |
| 8 | Canonical logging envelope | Partially implemented | Domain event envelope exists. Operational services still primarily emit plain text logs rather than structured JSON envelopes. |
| 9 | Research tables | Implemented | Proposed tables and ORM records needed by current services exist. Restore and retention drills remain unperformed. |
| 10 | GUI API/event contracts | Partially implemented | Versioned bootstrap/chart/execution contracts exist. SSE is a finite query response rather than a continuously reconnecting stream with durable cursor/gap recovery. |
| 11 | Read-only GUI console | Partially implemented | Charts, overlays, episodes, plans, health, alerts and shared-token authentication exist. RBAC, watchlist mutation confirmation, notes, exports, alert snooze/escalation UI and chart manifests are incomplete. |
| 12 | Unify venue | Implemented | Kraken is the default research and Freqtrade venue. |
| 13 | Persistent liquidity map | Implemented with validation gap | Confirmed pivots, clustering, touches, sweeps, accepted breaks and expiry are persisted. Golden historical fixtures and full replay evidence are absent. |
| 14 | Ordered episode engine | Implemented with correctness review required | Closed-candle state persistence exists. FVG origin timing needs a golden-dataset audit to prove every linked imbalance forms after the episode displacement rather than merely appearing in the recent window. |
| 15 | GUI overlays and replay | Partially implemented | Canonical levels, plans and episode timelines render. Failure markers, chart review history, snapshot artifacts and richer FVG zone rendering remain incomplete. |
| 16 | Mandatory gates/risk governor | Partially implemented | Deterministic services and persistence exist, but the collector does not automatically invoke qualification/risk after retest; operator/service orchestration is missing. |
| 17 | Target/stop/trailing recommendations | Implemented with gap | Versioned geometry and supersession exist. Each displayed profit box is not independently filtered by minimum R:R, and formal expiry/disarm refresh is not scheduled continuously. |
| 18 | Visualize approved plans | Implemented | Entry, stop, targets, size provenance and trailing policy are rendered from backend geometry. |
| 19 | Reproducible baseline research | **Blocked / incomplete** | Tooling exists, but the database has no ordered episode outcomes or feature snapshots. Buy-and-hold/trend baselines, fees/slippage sensitivity, lookahead, recursive analysis, regime segmentation and untouched-test evaluation have not run. |
| 20 | Freqtrade shadow then dry-run | **Blocked / incomplete** | Shadow intent/reconciliation records exist and are gated. No real reviewed manifest exists. Freqtrade is deliberately inert and dry-run submission is code-locked. |
| 21 | GUI dry-run operator console | **Blocked / incomplete** | The console shows plans, shadow events and gate reasons. Approvals, real dry-run fills, stop changes, exits and reconciliation cannot be implemented truthfully before item 20 passes. |

## High-priority findings

1. **Phase 4 evidence gate has not passed.** The audit database contains 507,989 candles, 28 legacy setups, and 1,246 indicator snapshots, but no new ordered episodes, decision-time feature snapshots, or outcome labels. No expectancy claim is possible.
2. **Phase 5 and item 21 must remain locked.** Enabling Freqtrade entries now would violate the specification. `FvgProEliteStrategy` deliberately emits no entries and the adapter rejects dry-run mode.
3. **Strategy orchestration is incomplete.** Liquidity and episode services run from the collector, but qualification, risk, recommendation refresh, outcome labelling and review sampling are not an automatic pipeline.
4. **Provenance is not yet production-grade.** Several domain records still use `config_hash="runtime"`, while the local `PLATFORM_GIT_SHA` is `unknown`. Every formal setup/trade therefore cannot yet be reconstructed from immutable configuration and code identity.
5. **Local SQLite and deployment migrations diverge.** The real local `platform.db` predates the new schema, while migration SQL targets PostgreSQL. Local API boot against that file can fail on renamed/new columns. A supported local migration path or a PostgreSQL-only development posture is required.
6. **GUI authentication is not RBAC.** One shared token protects GUI routes, but roles, per-user identity, sensitive-action confirmation challenges, session expiry/revocation and administrative permissions are not implemented.
7. **Health can under-report missing services.** Only heartbeat rows that exist are evaluated. A never-started Telegram/Freqtrade service is not necessarily listed as missing.
8. **Operational proof is absent on this host.** Docker Compose rendering, migration boot, backup restore, exchange outage, stale-feed, Telegram outage, restart recovery, and Freqtrade strategy loading could not be exercised because Docker/Freqtrade are unavailable.

## Required path to genuine completion

1. Establish a supported PostgreSQL development database, apply migrations, set a real Git SHA and deterministic safe configuration hash, and replay the closed-candle history through liquidity, episodes, features, gates and outcomes.
2. Add golden fixtures and correct any episode/FVG timing discrepancies found during replay.
3. Run the documented baseline, naive comparisons, ablations, walk-forward, fee/slippage sensitivity, lookahead and recursive analyses; seal and separately evaluate the untouched test; record results regardless of whether expectancy is positive.
4. Review and sign the baseline manifest only if all integrity gates pass. Run shadow mode for a sustained sample and reconcile every intent.
5. Only then implement/enable the Freqtrade dry-run connector and unlock the GUI dry-run lifecycle. Live trading remains prohibited.
6. Complete RBAC, durable live events, watchlist/control confirmations, notes/exports, chart manifests, incidents, missing-service health and operational drills.

## Verification performed

- Backend unit/integration suite and Ruff.
- GUI TypeScript no-emit build and Vite production build.
- Dependency audit previously returned zero vulnerabilities for the committed GUI lock.
- Git diff whitespace validation and clean-branch checks.
- Local persisted-data inventory without modifying the database.

Not performed locally: Docker Compose rendering, PostgreSQL migration boot, Freqtrade strategy check, external API availability, restore drill, or historical phase-4 validation.
