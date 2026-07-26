# 1. Capability Architecture for trading systems

← [Preface](00-preface.md) · [TOC](README.md) · [Next: Events, provenance, and authority →](02-events-provenance-authority.md)

---

## 1.1 Why import an organizational architecture into trading research?

Most trading software is specified like a finished workflow: indicators → signals → orders. Markets and research practice are not finished specifications. Edge decays, regimes shift, notes disagree with code, and “what we meant” rarely matches “what we measured.”

*The Capability Architecture, Volume I* asks a different question: how should an intelligent organization be represented computationally so software can **observe**, **understand changing structure**, and **develop new capabilities** in response?

Mapped to this project:

| Organizational idea | Trading research analogue |
|---|---|
| Organization | Research desk + platform + operator policies |
| Work object | Symbol, episode, setup, recommendation, level |
| Friction | Repeated false signals, manual chart reconciliation, ambiguous invalidation |
| Capability | Persistent ability to produce a class of insights/outcomes |
| Agent | Bounded runtime realizing a capability (not a chat box) |
| Authority | What the system may decide, publish, or escalate — never silent live authority |

## 1.2 Core definitions (from Volume I)

**Capability** — A persistent ability to achieve a class of outcomes with reduced dependence on scarce expertise. Not a feature, prompt, dashboard, or model alone.

**Capability definition** — Versioned governed specification including: identity/purpose, inputs, knowledge, authority, constraints, procedure/strategy, tools, outcome measures, tests/simulations, ownership/lifecycle.

**Agent** — Identifiable decision-making runtime under a mandate. A language model is only *part* of an agent when wrapped with identity, memory, tools, policies, authority, and evaluation.

**Observation** — Timestamped assertion about reality with provenance (human, system, or model — distinguished).

**Friction** — Repeated avoidable expenditure of time, attention, coordination, or error correction.

**Event** — Recorded occurrence relevant to state, with temporal order and identity.

## 1.3 Principles that transfer directly

| ID | Principle | Trading implication |
|---|---|---|
| **P-001** | Theory precedes implementation | Strategy math and claim types before UI or LLM glue |
| **P-002** | Capability is the product | The product is improved research ability, not another chart widget |
| **P-003** | Evolve from observation, not specification alone | Let failed setups, near-misses, and operator friction invent candidates |
| **P-004** | Preserve provenance | `strategy_version`, `config_hash`, `git_sha`, event envelopes |
| **P-005** | Authority explicit and machine-enforceable | Dry-run fail-closed; Freqtrade sole order authority |
| **P-006** | Agents receive bounded autonomy | Insight agents propose; they do not gain order paths by default |
| **P-007** | Capabilities require outcomes and retirement | Every detector/scorer has metrics and a kill condition |
| **P-008** | Plural organizational model | Events + relational state + documents + graph projections |
| **P-009** | Human purpose external to optimization | Maximize explainable research quality under risk policy — not “maximize PnL at any cost” |
| **P-010** | Make uncertainty visible | `data_quality`, AMBIGUOUS edges, confidence scores, missing SMT data → false |

## 1.4 Hypotheses from Volume I (status as in manuscript)

- **H-001** — Organizations as temporal knowledge graphs (under investigation)
- **H-002** — Capability stronger reusable unit than feature/prompt (tentatively supported)
- **H-003** — Agents are runtime realizations of capabilities (speculative)
- **H-004** — Structured observation reveals unarticulated requirements (under investigation)
- **H-005** — Persistent friction appears as repeated exception handling (under investigation)
- **H-006** — Agent value is encoded judgment, memory, policy, eval — not the base model (speculative)
- **H-007** — Capabilities can become licensable components (speculative)
- **H-008** — Outcome-linked event histories reduce learning cost (under investigation)

Part V of this book applies these to a trading insight system as **working hypotheses**, not settled engineering requirements.

## 1.5 Reference architecture layers (compressed)

Volume I’s six layers, specialized for trading insight:

1. **Human work & interfaces** — GUI workstation, Telegram reports, research review
2. **Observation & event** — closed-candle snapshots, episode transitions, alert acks
3. **Organizational / domain model** — liquidity levels, episodes, setups, recommendations
4. **Inference & discovery** — pattern mining, regime classifiers, capability candidates
5. **Capability registry** — versioned detectors, scorers, explainers, with tests and owners
6. **Agent runtime** — bounded automation realizing approved capabilities

Cross-cutting: governance, identity, evaluation, audit.

**Control plane** (schemas, policies, capability versions, rollout) stays separate from **operational plane** (day-to-day candle processing).

## 1.6 Ties to the graph

Capability Architecture communities (from the architecture corpus graph): Agents & Registry, Events & Provenance, Capability Value Loop, Org as Knowledge Graph, Agent Runtime Patterns, Work Objects & Friction, Authority & Policy.

Trading graph hubs that *should become capabilities* rather than loose scripts: Order Flow Framework, FVG Strategy Concepts, Liquidity Concepts, Setup Lifecycle Engine, Risk Qualification, Freqtrade Intent Adapter.

## 1.7 Capability lens

Treat each major trading idea (HTF bias, sweep, FVG lifecycle, confluence score) as a **capability candidate** with:

- explicit inputs (closed candles, HTF series, config)
- explicit authority (research-only vs recommendation vs shadow intent)
- explicit outcomes (precision/recall of eligible setups, calibration of score, time-to-review)
- retirement criteria (regime shift, degraded data quality, superseded version)

---

← [Preface](00-preface.md) · [TOC](README.md) · [Next: Events, provenance, and authority →](02-events-provenance-authority.md)
