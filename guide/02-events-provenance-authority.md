# 2. Events, provenance, and authority

← [Capability Architecture](01-capability-architecture.md) · [TOC](README.md) · [Next: Auction and order flow →](03-auction-and-order-flow.md)

---

## 2.1 Why this chapter sits before market patterns

Without provenance and authority, pattern knowledge becomes folklore. Capability Architecture insists that representations preserve **who asserted what, when, under which version**, and that **authority is machine-enforceable**. This platform already encodes much of that discipline.

## 2.2 Canonical events (platform)

From `docs/DATA_MODEL.md` and architecture docs:

- Events use a deterministic `event_id` for idempotency.
- Envelopes carry correlation/causation IDs, UTC times, service/software provenance, market context, decision context, measurements, severity, and safe external identifiers.
- Append-only histories exist for setup transitions, episode events, liquidity level observations, recommendation versions, and operator actions (e.g. alert acknowledgements).

**Capability mapping:** Layer 2 (Observation & Event) is not optional scaffolding — it is the memory that makes adaptation possible (H-008).

## 2.3 Provenance fields that must travel with every insight

| Field | Role |
|---|---|
| `strategy_version` | Semantic strategy contract |
| `config_hash` | Parameter identity |
| `git_sha` | Code identity |
| candle timestamp (UTC) | Closed-candle observability |
| `data_quality` | Missing/partial HTF or SMT inputs |
| confidence / EXTRACTED vs INFERRED | Graph and model honesty |

Principle **P-004**: organizational representations must preserve provenance.

## 2.4 Authority boundaries (non-negotiable for MVP)

From `AGENTS.md` and architecture:

1. **Freqtrade is sole order execution authority.** Direct CCXT is public-data-only.
2. **Live trading prohibited** unless fail-closed config enforces `dry_run=true` and spot mode.
3. Domain math is deterministic, closed-candle, testable — no lookahead.
4. GUI is a **read-only research workstation** (mutations limited to non-strategy actions like alert ack).
5. Do not store inferred institutional intent as fact — store measurements and evidence-based labels.

Principle **P-005** / **P-006**: authority explicit; agents bounded.

## 2.5 Control plane vs operational plane

| Plane | Examples |
|---|---|
| **Operational** | Ingest candles, advance episodes, score setups, emit recommendations |
| **Control** | Change HTF list, EMA length, gate thresholds, capability versions, rollout flags |

Changing control-plane parameters prospectively requires new provenance and often historical backfill for fair comparison (`STRATEGY_SPEC.md`).

## 2.6 Friction as first-class signal

Hypothesis **H-005**: persistent friction appears as repeated exception handling.

Trading friction examples already visible in the graph/docs:

- Footprint signals without HTF context (order-flow notes)
- SMT unwired → fail-closed execution adapter
- Ambiguous handwritten rules vs conservative platform rules
- Near-miss setups retained but not eligible

A capability-native system **logs friction events** (review time, false eligible, operator override requests) so discovery can propose new capabilities.

## 2.7 Ties to the graph

- Platform communities: telemetry models, setup lifecycle, recommendation service, kill switch / Telegram auth, migrations
- Surprising bridges: prompt-note rules ↔ `AGENTS.md` (execution authority, dry-run, no lookahead, provenance)

## 2.8 Capability lens

Define two always-on meta-capabilities:

1. **Evidence Capture** — authority: write events/telemetry only; outcome: completeness & idempotency
2. **Authority Guard** — authority: deny/allow capability activation; outcome: zero unauthorized order paths

Everything in Parts II–III runs *under* these.

---

← [Capability Architecture](01-capability-architecture.md) · [TOC](README.md) · [Next: Auction and order flow →](03-auction-and-order-flow.md)
