# 9. Fair value gaps, inversions, and order blocks

← [Liquidity maps](08-liquidity-maps-and-sweeps.md) · [TOC](README.md) · [Next: Six-component confluence →](10-six-component-confluence.md)

---

## 9.1 FVG indexing (platform — extracted)

For closed candle index `i` (Pine v6.2 parity where unambiguous):

- **Bullish zone** `[high(i-2), low(i-1)]` — created at `i-1`, detected at `i`
- **Bearish zone** `[high(i-1), low(i-2)]` — same timing rule
- Overlap ⇒ retest; invalidate on close beyond outer boundary; expiry by `max_age`
- Confirmation: directional candle, close past midpoint, close past prior close

No future candles; no centered windows.

## 9.2 FVG in the Order Flow Framework

FVG is the geometric scar of imbalance; often co-located with **LVN**. Location layer uses this scar; confirmation layer asks whether an **order block** at/near that scar is defended on footprint.

## 9.3 IFVG (inversion) and institutional sequence

Graph/docs distinguish:

- Six-component FVG model (phase one)
- Supplementary IFVG / V-recovery / fib sniper / session liquidity / TP boxes (next-phase research)

**Must not silently blend** into execution results (`STRATEGY_SPEC.md`).

IFVG model breakdown docs describe sequences such as liquidity sweep → V-recovery → inversion → directional bias, with A/A+/A++ confluence types.

## 9.4 Order blocks

Notes: absorption at a level helps *form* what traders call an order block. Platform should store **OB candidates as geometry + evidence**, not “institutional orders.”

Order-flow confirmation: absorption/aggression at OB after context+location.

## 9.5 Fib sniper / OTE overlays

Fib retest sniper notes (0.618–0.786, manipulation leg anchors) appear as concept clusters. Treat as **contextual ranking features**, never mandatory gate overrides.

## 9.6 Ties to the graph

`detect_fvgs()`, `advance_fvg()`, imbalance tables, FVG Strategy Concepts communities, IFVG lab reports, Order Block nodes in Order Flow Framework.

## 9.7 Capability lens

| Capability | Status posture |
|---|---|
| `imbalance.fvg.v1` | production research primitive |
| `imbalance.ifvg.v1` | staged research module |
| `imbalance.ob_candidate.v1` | research; evidence-based |
| `imbalance.fib_reaction.v1` | contextual only |

Composition: episode/setup capabilities depend on FVG; IFVG must declare explicit contract and fail closed when unwired.

---

← [Liquidity maps](08-liquidity-maps-and-sweeps.md) · [TOC](README.md) · [Next: Six-component confluence →](10-six-component-confluence.md)
