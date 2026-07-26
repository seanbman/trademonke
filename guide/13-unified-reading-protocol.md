# 13. Unified reading protocol — how the concepts stack

← [Platform substrate](12-platform-as-capability-substrate.md) · [TOC](README.md) · [Next: Hypothesis — adaptive insight system →](14-hypothesis-adaptive-insight-system.md)

---

## 13.1 One stack, many vocabularies

This chapter is the synthesis: a **single step-by-step protocol** that uses Order Flow Framework language, ICT/SMC vocabulary, classic patterns as hints, and platform gates as law.

```text
0. Provenance & data quality     (always)
1. Context — auction / HTF       (Order Flow L1 + HTF bias + structure)
2. Location — levels & thinness  (liquidity map + FVG/LVN + optional VP)
3. Compression / pattern hints   (optional; non-gating)
4. Confirmation — reclaim/defend (sweep rules + retest + optional footprint)
5. Confluence score & gates      (six components; fail closed)
6. Risk & recommendation         (Decimal geometry; no order authority)
7. Outcome capture               (for adaptation later)
```

## 13.2 Step-by-step (operator or agent checklist)

### Step 0 — Can we know?

- Closed candles only; UTC; required HTF series present
- If `data_quality=missing` on SMT/HTF → component false; uncertainty visible
- Record strategy_version / config_hash / git_sha

### Step 1 — Context (balanced or discovering?)

Ask: rotating value or trending imbalance?

Evidence sources:

- Swing structure / BOS narrative
- Anchored VWAP side
- HTF EMA alignment (platform boolean)
- Regime classifier if enabled

**Outputs:** bias direction or “no trade context”

### Step 2 — Location (where is interesting?)

- Confirmed liquidity levels / EQ clusters
- FVG/IFVG geometry (IFVG only if capability enabled)
- LVN ∩ FVG when profile available
- Premium/discount or OTE as *contextual* tags only

**Outputs:** candidate zones with IDs

### Step 3 — Optional pattern hint

- Rising/falling wedge, flag, triangle labels from catalog
- Or compression metrics

**Outputs:** explanation tags — **never eligibility alone**

### Step 4 — Confirmation

- Sweep = wick beyond + close back inside (platform)
- Acceptance = close beyond
- Retest of FVG per platform rules
- Footprint absorption/aggression if capability available

**Outputs:** confirmation events linked to level/imbalance IDs

### Step 5 — Confluence law

Evaluate six components. Eligible only if mandatory gates pass. Contextual modules (fib sniper, ORB, AMD story) may rank, not override.

### Step 6 — Risk & insight artifact

Produce versioned recommendation / trade plan geometry. `execution_connected=false` unless a later governed capability says otherwise.

### Step 7 — Learn

Store outcomes, near-misses, operator friction. These feed Part V discovery.

## 13.3 Worked conceptual example (hypothetical narrative)

1. HTF bias aligned long; anchored VWAP holding; structure not broken against.
2. Sell-side liquidity swept on a confirmed pivot; close back inside.
3. Bullish FVG forms after displacement; overlaps a thin profile region.
4. Optional: falling wedge label on LTF compression — tagged only.
5. Components flip true → score 6 → risk OK → recommendation vN.
6. No order placed by insight system; Freqtrade path remains separately governed.

## 13.4 Anti-patterns

| Anti-pattern | Why it fails |
|---|---|
| Footprint-first entries | No context/location |
| Pattern-sheet trading | Ambiguous edges; no gates |
| Score overrides risk | Violates platform law |
| Intent labels as facts | Violates AGENTS honesty |
| Silent IFVG blend into execution | Spec conflict |

## 13.5 Capability lens

Encode this protocol as capability **`insight.read_protocol.v1`**: an orchestration capability that calls subordinate capabilities in order, emits a single evidence package, and stops early on failed preconditions (IP-001: plan broadly, commit narrowly).

---

← [Platform substrate](12-platform-as-capability-substrate.md) · [TOC](README.md) · [Next: Hypothesis — adaptive insight system →](14-hypothesis-adaptive-insight-system.md)
