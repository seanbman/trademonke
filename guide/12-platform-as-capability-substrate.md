# 12. This platform as a capability substrate

← [Sessions & regimes](11-sessions-orb-amd-regimes.md) · [TOC](README.md) · [Next: Unified reading protocol →](13-unified-reading-protocol.md)

---

## 12.1 Map Volume I layers → trading-bot-x

| CA layer | Platform reality |
|---|---|
| 1 Human interfaces | React GUI (read-only research), Telegram reports/controls |
| 2 Observation & event | Telemetry events, episode_events, setup_transitions, indicator snapshots |
| 3 Organizational model | PostgreSQL entities: levels, episodes, setups, recommendations, candles |
| 4 Inference & discovery | Research pipeline, candidates, future miners (partial) |
| 5 Capability registry | *Implicit today* via strategy_version/config_hash/git_sha — **explicit registry is the gap** |
| 6 Agent runtime | Services + Freqtrade adapter (bounded); not LLM agents by default |

Governance: kill switch, allowlists, GUI token fail-closed, dry-run enforcement.

## 12.2 Separation of concerns (already aligned)

`AGENTS.md`: market data, detection, lifecycle, scoring, risk, execution, notifications, telemetry, API presentation stay separate. Domain calculations deterministic and closed-candle.

This matches **theory precedes implementation** and **control vs operational plane**.

## 12.3 God nodes as durable objects

Graph god nodes (`Settings`, `Candle`, `Direction`, engines, records) are the nouns a capability registry should reference. Capabilities are verbs/abilities over those nouns.

## 12.4 What is missing for full Capability Architecture

1. **Explicit capability registry** (definitions, owners, tests, rollout state)
2. **Friction event taxonomy** (operator time, false eligible, data gaps)
3. **Discovery loop** that proposes capability candidates from outcome-linked histories
4. **Staged autonomy** beyond shadow intents
5. **Model gateway** (if/when LLMs explain or mine patterns) with versioned prompts and eval

Part V designs these without abandoning fail-closed MVP constraints.

## 12.5 Execution boundary as a feature

Freqtrade sole authority + disconnected recommendations is an **authority capability**, not a temporary embarrassment. Adaptive insight systems that skip this become unsafe automation.

## 12.6 Ties to the graph

Architecture docs bridges; docker compose research stack hyperedge; security/auth communities; setup lifecycle engine; qualification/risk services.

---

← [Sessions & regimes](11-sessions-orb-amd-regimes.md) · [TOC](README.md) · [Next: Unified reading protocol →](13-unified-reading-protocol.md)
