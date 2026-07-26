# Trading Insight & Capability Architecture

### A working guide synthesizing the project knowledge graph with *The Capability Architecture, Volume I*

This folder is arranged as a book. Start at the table of contents, then follow chapter links (or use **Next →** / **← Previous** at the top and bottom of each file).

### Companion track (learners / cohort guinea pigs)

Plain-language trading practice for humans who will stress-test the insight tools:

→ **[Market Strategies for Dummies](market-strategies-for-dummies/README.md)**

Builders: read this master book first, then run cohorts via [lesson 13 in the learner track](market-strategies-for-dummies/13-for-builders-cohorts.md).

**Sources**

- Project knowledge graph (`graphify-out/`) — trading concepts, strategy specs, platform code, notes, and screenshots
- *The Capability Architecture, Volume I: Foundations* (v0.3) — capability, authority, observation, agents, and adaptive software
- Platform docs in `docs/` and repository rules in `AGENTS.md`

**Claim discipline**

| Label | Meaning |
|---|---|
| **Definition** | Precise meaning used in this guide |
| **Principle** | Design commitment (Capability Architecture P-00x where cited) |
| **Extracted** | Present as nodes/edges in the knowledge graph or platform docs |
| **Hypothesis** | Plausible but not proven; labeled explicitly |
| **Implementation pattern** | Replaceable technical shape |

Measurements describe price behavior. Do not treat inferred participant intent as fact.

---

## Table of contents

### Front matter

| # | Chapter | File |
|---|---------|------|
| — | [How to read this book](00-preface.md) | `00-preface.md` |
| — | [Glossary](99-glossary.md) | `99-glossary.md` |

### Part I — Capability foundations

| # | Chapter | File |
|---|---------|------|
| 1 | [Capability Architecture for trading systems](01-capability-architecture.md) | `01-capability-architecture.md` |
| 2 | [Events, provenance, and authority](02-events-provenance-authority.md) | `02-events-provenance-authority.md` |

### Part II — Market reading layers

| # | Chapter | File |
|---|---------|------|
| 3 | [Auction markets and the Order Flow Framework](03-auction-and-order-flow.md) | `03-auction-and-order-flow.md` |
| 4 | [Candlesticks, footprint, absorption, and delta](04-candlesticks-and-footprint.md) | `04-candlesticks-and-footprint.md` |
| 5 | [Volume profile, value, and FVG as LVN](05-volume-profile-and-value.md) | `05-volume-profile-and-value.md` |
| 6 | [Classic chart patterns (triangles, wedges, flags)](06-classic-chart-patterns.md) | `06-classic-chart-patterns.md` |

### Part III — Structure, liquidity, and confluence

| # | Chapter | File |
|---|---------|------|
| 7 | [Market structure vocabulary (BOS, CHoCH, SMT)](07-market-structure-vocabulary.md) | `07-market-structure-vocabulary.md` |
| 8 | [Liquidity maps, sweeps, and equal highs/lows](08-liquidity-maps-and-sweeps.md) | `08-liquidity-maps-and-sweeps.md` |
| 9 | [Fair value gaps, inversions, and order blocks](09-fvg-and-order-blocks.md) | `09-fvg-and-order-blocks.md` |
| 10 | [The six-component confluence model](10-six-component-confluence.md) | `10-six-component-confluence.md` |
| 11 | [Sessions, ORB, AMD, and regime matchmaking](11-sessions-orb-amd-regimes.md) | `11-sessions-orb-amd-regimes.md` |

### Part IV — Platform substrate and synthesis

| # | Chapter | File |
|---|---------|------|
| 12 | [This platform as a capability substrate](12-platform-as-capability-substrate.md) | `12-platform-as-capability-substrate.md` |
| 13 | [Unified reading protocol — how the concepts stack](13-unified-reading-protocol.md) | `13-unified-reading-protocol.md` |

### Part V — Hypothesis: a self-adaptive insight system

| # | Chapter | File |
|---|---------|------|
| 14 | [Hypothesis — Capability-native adaptive trading insight](14-hypothesis-adaptive-insight-system.md) | `14-hypothesis-adaptive-insight-system.md` |

---

## Suggested reading paths

1. **Trader / researcher** — [Preface](00-preface.md) → [Order Flow](03-auction-and-order-flow.md) → [Confluence](10-six-component-confluence.md) → [Unified protocol](13-unified-reading-protocol.md) → [Hypothesis](14-hypothesis-adaptive-insight-system.md)
2. **Engineer / architect** — [Preface](00-preface.md) → [Capability Architecture](01-capability-architecture.md) → [Events & authority](02-events-provenance-authority.md) → [Platform substrate](12-platform-as-capability-substrate.md) → [Hypothesis](14-hypothesis-adaptive-insight-system.md)
3. **Full book** — read chapters **1 → 14** in order, using the footer links.

---

## Graph orientation (selected hubs)

Concepts in this guide map to graph communities such as **Order Flow Framework**, **FVG Strategy Concepts**, **Chart Pattern Catalog**, **Liquidity Concepts**, **Candlestick Patterns**, and platform modules (`episodes`, `setups`, `liquidity`, `qualification`, Freqtrade adapter). God nodes in the code graph include `Settings`, `Candle`, `Direction`, and lifecycle engines — the durable computational objects around which capabilities should form.

---

← Start here: **[How to read this book →](00-preface.md)**
