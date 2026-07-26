# 8. Liquidity maps, sweeps, and equal highs/lows

← [Market structure](07-market-structure-vocabulary.md) · [TOC](README.md) · [Next: FVG and order blocks →](09-fvg-and-order-blocks.md)

---

## 8.1 Persistent liquidity map (platform)

From strategy/data model docs:

- Levels from **strictly confirmed pivots** (left/right closed-candle windows)
- Nearby same-side pivots may cluster as equal levels within bps tolerance
- Observations are append-only: touch, wick-through-and-reclaim sweep, close-beyond acceptance, expiry
- **No label asserts institutional intent**

This is Capability Architecture done right at the domain layer: measurements with provenance, not mythology.

## 8.2 Sweep definition (platform)

Wick strictly beyond a confirmed level **and** close strictly back inside. A close beyond is continuation/acceptance — not a reversal sweep.

Aligns with order-flow idea of failed breakout / reclaim, without claiming “stop hunt” as fact. Notes may say stop hunt; storage should say **sweep measurement**.

## 8.3 BSL / SSL / EQH / EQL

Graph glossary nodes:

- **BSL** — buy-side liquidity (often unswept highs)
- **SSL** — sell-side liquidity
- **EQH / EQL** — equal highs / equal lows

Useful narrative overlays on the liquidity map. Automation should prefer pivot clusters + sweep events.

## 8.4 Episodes

An episode materializes ordered state for an originating level. Armed only after mandatory gates pass with valid data quality. Gate evidence is stored independently from contextual ranking.

This is the work-object lifecycle Volume I describes for organizational routines — applied to market structure narratives.

## 8.5 Ties to the graph

`LiquidityMapService`, `LiquidityLevelRecord`, liquidity domain functions, screenshot liquidity glossaries, IFVG sequence docs referencing sweeps.

## 8.6 Capability lens

**`liquidity.map.v1`** — maintain levels + events  
**`liquidity.sweep.v1`** — classify sweep vs acceptance  
**`liquidity.episode.v1`** — ordered state machine  

Outcomes: reproducibility of episode paths; explanation completeness for GUI `/why` style evidence.

---

← [Market structure](07-market-structure-vocabulary.md) · [TOC](README.md) · [Next: FVG and order blocks →](09-fvg-and-order-blocks.md)
