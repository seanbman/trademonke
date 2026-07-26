# 10. The six-component confluence model

← [FVG and order blocks](09-fvg-and-order-blocks.md) · [TOC](README.md) · [Next: Sessions, ORB, AMD →](11-sessions-orb-amd-regimes.md)

---

## 10.1 The six auditable booleans

Platform score: one point each (weights stored for later research):

1. HTF bias  
2. Liquidity sweep  
3. FVG / imbalance indexing  
4. SMT  
5. Structure break  
6. (sixth component per strategy wiring — see indicator snapshots / strategy version)

Score bands (spec): 0–3 developing, 4 watch, 5 strong watch, 6 eligible.

**Critical rule:** score and contextual evidence **must not override** a failed mandatory gate or risk rejection.

## 10.2 Hyperedge in the graph

Graph hyperedge **Six-Component FVG Confluence Model** links HTF bias, liquidity sweep, FVG indexing, SMT, structure break, and scoring docs — a true multi-node capability signature.

## 10.3 Relationship to Context → Location → Confirmation

| Order-flow step | Confluence contribution |
|---|---|
| Context | HTF bias, structure break, SMT |
| Location | Sweep level + FVG geometry (+ future VP) |
| Confirmation | Retest/displacement modules; future footprint |

Confluence is the **deterministic skeleton**; order flow is the **interpretive stack**. Together they form a composite capability.

## 10.4 Risk after confluence

Risk validates directional geometry, R:R, costs, control state, notional, Decimal sizing. Same-candle stop/target ambiguity labeled stop-first.

Recommendations are versioned immutable geometry snapshots; execution remains disconnected until later gates.

## 10.5 Capability lens — composite capability

**`setup.confluence.v1`** composition contract:

```text
requires:
  - structure.htf_bias.v1
  - liquidity.sweep.v1
  - imbalance.fvg.v1
  - structure.smt.v1
  - structure.bos.v1
guarantees:
  - score 0..6 with per-component evidence payloads
  - no eligibility if any mandatory gate fails
authority:
  - may write setup/recommendation research records
  - may NOT place orders
outcomes:
  - calibration of score vs forward quality
  - gate failure explanations completeness
retirement:
  - superseded strategy_version
  - sustained miscalibration beyond threshold
```

This matches Volume I capability anatomy (authority, constraints, outcomes, tests, lifecycle).

---

← [FVG and order blocks](09-fvg-and-order-blocks.md) · [TOC](README.md) · [Next: Sessions, ORB, AMD →](11-sessions-orb-amd-regimes.md)
