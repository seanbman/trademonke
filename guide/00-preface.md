# How to read this book

← [Table of contents](README.md) · [Next: Capability Architecture →](01-capability-architecture.md)

---

## Purpose

This guide answers one practical question:

> How do the trading concepts in this repository’s knowledge graph fit together as a coherent reading and research system — and how should Capability Architecture philosophy shape a **self-adaptive trading insight tool** that stays fail-closed, auditable, and honest about uncertainty?

It is not a live-trading manual. Execution authority remains with Freqtrade under dry-run / spot constraints unless product policy explicitly changes. Insight, recommendation, and research capabilities are the product under discussion.

## How chapters relate

```text
Part I   Capability vocabulary (what “adaptive software” means)
Part II  Market reading layers (auction → profile → footprint → patterns)
Part III Structure & confluence (liquidity, FVG/OB, six gates, sessions)
Part IV  Platform substrate + unified reading protocol
Part V   Hypothesis: capability-native adaptive insight system
```

Each chapter ends with:

- **Ties to the graph** — which concept clusters it rests on
- **Capability lens** — how the chapter would appear as capabilities, events, or authority
- **Next** — the following chapter link

## Versioning of claims

Capability Architecture Volume I distinguishes definitions, principles, hypotheses, observations, and implementation patterns. This guide adopts that discipline:

1. Trading **mechanics** that already exist in `docs/STRATEGY_SPEC.md` or domain code are treated as **extracted platform rules**.
2. Handwritten notes and screenshots contribute **concepts** and **reading heuristics**; discretionary or unsafe statements (e.g. “go all in”) are rejected.
3. Cross-links between order-flow philosophy and the six-component FVG model are often **synthesis** — useful, but not automatic identity.
4. Part V is labeled **Hypothesis** throughout.

## Suggested first hour

1. Skim [Capability Architecture](01-capability-architecture.md) (principles P-001–P-007).
2. Read [Order Flow Framework](03-auction-and-order-flow.md) (Context → Location → Confirmation).
3. Read [Six-component confluence](10-six-component-confluence.md).
4. Jump to [Unified reading protocol](13-unified-reading-protocol.md).
5. Skim Part V’s architecture patterns and cost/benefit tables.

Handing this to non-developers? Send them to the learner track instead: [Market Strategies for Dummies](market-strategies-for-dummies/README.md).

## Navigation

Every chapter links back to the [table of contents](README.md). Use the footer of each file for sequential reading.

---

← [Table of contents](README.md) · [Next: Capability Architecture →](01-capability-architecture.md)
