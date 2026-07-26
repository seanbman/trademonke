# 14. Hypothesis — Capability-native adaptive trading insight

← [Unified reading protocol](13-unified-reading-protocol.md) · [TOC](README.md) · [Glossary →](99-glossary.md)

---

> **Hypothesis (book-level):** A trading insight system becomes *self-adaptive* not by letting a model rewrite strategy online, but by treating detectors, scorers, explainers, and regime routers as **versioned capabilities** inside Capability Architecture’s observe → discover → register → realize → evaluate loop — while **authority over orders remains a separate, fail-closed capability** owned by Freqtrade policy.

This chapter is deliberately labeled **Hypothesis**. It synthesizes graph concepts (Parts II–III), platform substrate (Part IV), and *Capability Architecture Volume I*.

---

## 14.1 Problem statement

Static trading software drifts from reality:

- Notes and screenshots encode judgment the code does not
- Regimes change; fixed confluence weights miscalibrate
- Operators spend attention reconciling charts with alerts (**friction**)
- Adding “an AI layer on top” without events, authority, and outcomes creates confident nonsense (Volume I counterexample)

**Desired product (P-002):** a durable organizational *ability* to produce calibrated, explainable trading insights that improve from outcome-linked observation — not another dashboard.

---

## 14.2 Central hypothesis stack

| ID | Claim | Status |
|---|---|---|
| **TH-1** | The Unit of Adaptation should be the **capability definition** (detector/scorer/explainer/router), not a prompt or a monolith strategy file | Extends H-002 |
| **TH-2** | Self-adaptation means **governed promotion of capability versions** from discovery evidence, not unsupervised live mutation of gates | Extends P-003, P-007 |
| **TH-3** | Order Flow’s Context→Location→Confirmation is the right **orchestration ontology** for insight capabilities | Synthesis from graph |
| **TH-4** | Six-component confluence is the right **fail-closed skeleton**; contextual modules are pluggable capabilities | Platform extracted |
| **TH-5** | Agent runtimes may propose, explain, and mine — they must not gain order authority by side effect | P-005, P-006, AGENTS.md |
| **TH-6** | A knowledge graph of concepts (this repo’s graphify graph) is a practical **Layer-3/4 projection** for discovery and explanation | Extends H-001 |

---

## 14.3 Target system definition

**Name (working):** Capability-Native Insight System (CNIS)

**Outcomes to maximize (human purpose remains external — P-009):**

1. Explanation completeness for eligible and near-miss setups  
2. Score calibration vs forward research quality  
3. Reduction in operator friction hours per reviewed alert  
4. Zero unauthorized execution paths  
5. Measurable improvement when a new capability version is promoted  

**Non-goals:** autonomous live trading; unconstrained LLM tool use; silent blending of research modules into execution.

---

## 14.4 Reference architecture for CNIS

Specialize Volume I Figure 9.1:

```text
┌─────────────────────────────────────────────────────────────┐
│  Interfaces: GUI workstation · Telegram · research CLI      │
├─────────────────────────────────────────────────────────────┤
│  Observation: candles · episodes · setups · friction events │
├─────────────────────────────────────────────────────────────┤
│  Domain model: levels · imbalances · recommendations       │
│  + Concept graph projection (graphify / wiki)               │
├─────────────────────────────────────────────────────────────┤
│  Discovery: miners · regime drift · friction clustering     │
├─────────────────────────────────────────────────────────────┤
│  Capability registry: versions · tests · owners · rollout   │
├─────────────────────────────────────────────────────────────┤
│  Runtimes: deterministic engines · bounded explain agents   │
│  Execution adapter: Freqtrade-only, fail-closed             │
├─────────────────────────────────────────────────────────────┤
│  Cross-cut: identity · policy · eval · OTel · model gateway │
└─────────────────────────────────────────────────────────────┘
```

**Control plane:** capability YAML/JSON definitions, feature flags, eval thresholds, rollout percentages.  
**Operational plane:** closed-candle processing and artifact writes.

---

## 14.5 Architecture patterns (options)

### Pattern A — Monolithic strategy service

One process owns all detectors and scoring.

| Pros | Cons |
|---|---|
| Simple deploy | Hard to version one idea |
| Easy local reasoning | Adaptation becomes big-bang releases |
| | Blast radius on change |

**Verdict:** acceptable MVP; poor self-adaptive endgame.

### Pattern B — Capability micro-modules + orchestrator (recommended)

Each detector/scorer is a versioned module; `insight.read_protocol.v1` orchestrates ([Chapter 13](13-unified-reading-protocol.md)).

| Pros | Cons |
|---|---|
| Matches CA composition | More packaging overhead |
| Staged rollout per capability | Contract tests required |
| Clear authority scopes | Discovery must understand graph of deps |

**Verdict:** best fit for TH-1/TH-2.

### Pattern C — Event-sourced insight core

All observations append-only; projections build setups.

| Pros | Cons |
|---|---|
| Excellent provenance (P-004) | Replay cost |
| Natural outcome linkage (H-008) | Harder ad-hoc queries without projections |
| Aligns with existing episode_events | Team must learn event design |

**Verdict:** already partially present — deepen rather than replace.

### Pattern D — LLM-first agent trader

Model plans trades with tools.

| Pros | Cons |
|---|---|
| Flexible narratives | Authority leakage risk |
| Fast demo | Non-deterministic gates |
| | Violates closed-candle discipline easily |

**Verdict:** reject as primary. Allow only as **explain/mine** tools behind gateway.

### Pattern E — Dual-loop cybernetic system

- **Fast loop:** deterministic protocol on each closed candle  
- **Slow loop:** discovery weekly/monthly proposes capability versions  

| Pros | Cons |
|---|---|
| Matches Wiener-style feedback in CA graph | Needs eval harness |
| Prevents online self-rewriting | Slower “adaptation” (feature, not bug) |

**Verdict:** adopt as organizational operating model.

---

## 14.6 Capability catalog (initial)

| Capability ID | Layer | Authority | Notes |
|---|---|---|---|
| `meta.evidence_capture.v1` | 2 | write telemetry | always on |
| `meta.authority_guard.v1` | governance | deny/allow | blocks live paths |
| `auction.context.v1` | insight | labels | Order Flow L1 |
| `location.profile.v1` | insight | annotate | optional VP |
| `liquidity.map.v1` | domain | CRUD levels | exists |
| `liquidity.sweep.v1` | domain | classify | exists |
| `imbalance.fvg.v1` | domain | geometry | exists |
| `imbalance.ifvg.v1` | research | geometry | staged |
| `structure.htf_bias.v1` | domain | boolean | exists |
| `structure.smt.v1` | domain | boolean+dq | exists |
| `structure.bos.v1` | domain | boolean | exists |
| `setup.confluence.v1` | composite | setups | exists skeleton |
| `risk.plan.v1` | domain | plans | exists |
| `recommend.publish.v1` | research | immutable versions | exists |
| `footprint.confirm.v1` | research | optional | vendor data |
| `pattern.catalog.v1` | knowledge | none | graph/docs |
| `regime.classify.v1` | discovery | observations | candidate |
| `explain.package.v1` | agent-assisted | narrative | LLM optional |
| `discover.friction_mine.v1` | discovery | proposals only | candidate |
| `exec.shadow_intent.v1` | boundary | shadow only | Freqtrade adapter |

---

## 14.7 Self-adaptation mechanism (slow loop)

```text
Outcome & friction events
        │
        ▼
Discovery jobs (deterministic stats ± bounded model assist)
        │
        ▼
Capability candidate (diff of definition + tests + predicted value)
        │
        ▼
Human/control-plane review (owner + eval thresholds)
        │
        ▼
Shadow deploy → compare vs champion version
        │
        ▼
Promote / rollback / retire (P-007)
```

**What adapts:** weights for *contextual* ranking, enabling of optional modules (IFVG, footprint, regime routing), explanation templates, alert thresholds.  
**What does not silently adapt:** mandatory gate logic, dry-run authority, Decimal risk invariants — those change only via versioned releases with tests.

---

## 14.8 Implementation strategies (phased)

### Phase 0 — Formalize what you already have (2–4 weeks)

- Document each domain function as a capability definition stub  
- Emit friction events (time-to-ack, false eligible marked by operators)  
- Keep fail-closed execution  

**Cost:** low · **Benefit:** unlocks measurement · **Risk:** low

### Phase 1 — Explicit registry (3–6 weeks)

- `capability_definitions` table + API  
- Link every setup component to capability version IDs  
- CI: load tests for each capability  

**Cost:** medium · **Benefit:** true versioning · **Risk:** medium (migration)

### Phase 2 — Protocol orchestrator (2–4 weeks)

- Implement `insight.read_protocol.v1` as explicit state machine  
- Early-stop with evidence packages for GUI  

**Cost:** medium · **Benefit:** aligns code with Order Flow pedagogy · **Risk:** low if pure refactor

### Phase 3 — Discovery MVP (4–8 weeks)

- Offline notebooks/jobs: regime drift, score calibration, component ablation  
- Output: candidate capability diffs, not auto-merge  

**Cost:** medium-high · **Benefit:** H-004/H-008 testbed · **Risk:** over-fitting — mitigate with sealed test periods (`BACKTESTING.md` ethos)

### Phase 4 — Bounded explain agents (optional)

- Model gateway; retrieve evidence package; produce narrative  
- No tools that can touch orders  
- Eval suite: faithfulness to evidence (citation required)

**Cost:** high ongoing (tokens) · **Benefit:** friction reduction · **Risk:** hallucination — mitigate with EXTRACTED-only citations

### Phase 5 — Optional data plane expansions

- Footprint/VP ingestion capabilities  
- IFVG module promotion when eval clears  

**Cost:** high (data) · **Benefit:** richer Location/Confirmation · **Risk:** vendor lock-in

---

## 14.9 Cost–benefit matrix (executive)

| Investment | CapEx / OpEx | Benefit | Payback signal |
|---|---|---|---|
| Registry + provenance deepen | Eng weeks | Safe adaptation | % setups with full capability lineage |
| Protocol orchestrator | Eng weeks | Shared mental model with notes | Review time ↓ |
| Friction telemetry | Small | Discovery fuel | Friction events/week usable |
| Calibration jobs | Data eng | Better contextual weights | Brier/reliability diagrams |
| Footprint/VP | Data $$ | Confirmation quality | Precision↑ at constant recall |
| LLM explainer | Token $$ | Operator speed | Time-to-understand ↓ with faithfulness SLA |
| Autonomous gate mutation | Appears cheap | — | **Negative EV** — reject |

---

## 14.10 Authority & safety design patterns

1. **Capability passports** — each runtime presents capability ID + version; guard checks scope  
2. **Two-person rule for promotion** — owner + reviewer on registry promote  
3. **Shadow vs live** — new scorers only affect ranking channels until promoted  
4. **Degradation** — if model gateway down, deterministic path continues (Volume I reliability)  
5. **Tenant/memory isolation** — if multi-user, no cross-user learning without policy  
6. **Intent honesty** — labels remain behavioral; “stop hunt” stays vernacular in UI copy, not DB facts  

---

## 14.11 Mapping Order Flow + confluence into registry dependencies

```text
insight.read_protocol.v1
├── auction.context.v1
├── location.* (liquidity.map, imbalance.fvg, location.profile?)
├── confirm.* (liquidity.sweep, footprint.confirm?)
├── setup.confluence.v1
│   ├── structure.htf_bias.v1
│   ├── liquidity.sweep.v1
│   ├── imbalance.fvg.v1
│   ├── structure.smt.v1
│   └── structure.bos.v1
├── risk.plan.v1
└── recommend.publish.v1
```

Discovery may propose edges (e.g. enable `imbalance.ifvg.v1` under regime X) as **policy capability** changes, not code smuggling.

---

## 14.12 Knowledge graph as organizational memory

This repository’s graphify graph already clusters Order Flow, FVG, patterns, and platform modules. CNIS should:

- Treat graph nodes as **concept work objects**  
- Attach capability definitions to concept IDs  
- Use `graphify query/path` during explanation to bridge note language ↔ code symbols  
- Run `graphify update` when docs/notes change (observation of knowledge work)

That is H-001 in miniature: a temporal knowledge graph of the research organization itself.

---

## 14.13 Evaluation plan (to falsify or support TH-*)

| Question | Method | Falsifier |
|---|---|---|
| Does registry slow delivery without benefit? | Time-to-merge metrics | Cycle time ↑ with no calibration gain |
| Does protocol orchestrator reduce missed context errors? | Annotated error taxonomy | No change in footprint-first mistakes |
| Do friction mines yield real capabilities? | Count promotions / quarter | Zero promotions after 2 quarters |
| Do explain agents reduce review time faithfully? | Timed review + citation audit | Faster but faithfulness < threshold |
| Does contextual adaptation improve calibration? | Sealed forward windows | Reliability worsens |

---

## 14.14 Economic hypothesis (H-006 applied)

Differentiated value will not be “which LLM.” It will be:

- curated episode/outcome memory  
- tested capability definitions  
- authority boundaries competitors skip  
- concept graph linking pedagogy to detectors  
- eval harnesses for promotion  

That is the IP of a research desk encoded as software.

---

## 14.15 What “self-adaptive” means in one sentence

**CNIS self-adapts by continually turning observed market outcomes and operator friction into reviewed, versioned capability changes that improve insight quality under explicit authority — while the fast path on each candle remains deterministic, closed-candle, and fail-closed.**

---

## 14.16 Open research questions

1. What evidence threshold promotes a contextual module into mandatory gates?  
2. How to prevent overfitting when mining friction from a single operator?  
3. Can footprint capabilities be standardized across venues enough to share definitions?  
4. Should regime routing be a policy capability or a model-assisted suggestion only?  
5. How to visualize capability lineage in the GUI without overwhelming the first viewport of research UX?

---

## 14.17 Chapter summary

- Adaptation belongs in a **slow, governed capability loop**, not in live nondeterministic trading.  
- Order Flow Framework supplies the **orchestration ontology**; six-component confluence supplies the **law**.  
- Platform already implements much of Layers 1–3 and partial 6; **registry + discovery** are the strategic gaps.  
- Architecture Pattern **B + C + E** (modules + events + dual loop) is the recommended shape.  
- Cost/benefit favors provenance, friction telemetry, and calibration before expensive footprint/LLM spend.  
- Authority Guard remains the most important capability in the catalog.

---

← [Unified reading protocol](13-unified-reading-protocol.md) · [TOC](README.md) · [Glossary →](99-glossary.md)
