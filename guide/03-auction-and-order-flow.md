# 3. Auction markets and the Order Flow Framework

← [Events & authority](02-events-provenance-authority.md) · [TOC](README.md) · [Next: Candlesticks and footprint →](04-candlesticks-and-footprint.md)

---

## 3.1 Definition — Order Flow Framework

**Extracted** from `docs/Order Flow White Paper.pdf` and `docs/transcribed_trading_notes.txt` (graph community **Order Flow Framework**).

The framework is **three resolutions of the same auction**, not three independent indicator systems:

| Layer | Question | Primary tools |
|---|---|---|
| **Order Flow / Auction Theory** | Balanced or discovering price? Who has HTF control? | HTF structure, anchored VWAP, swing highs/lows |
| **Volume Profile** | Where was price accepted vs traversed too fast? | POC, HVN, LVN (FVG ≈ LVN) |
| **Footprint Volume** | Who is in control *now* at this level/candle? | Bid×ask, delta, absorption/aggression, order blocks |

## 3.2 Required reading order

**Context → Location → Confirmation**

1. **Context** — auction state (balance vs imbalance)
2. **Location** — profile map; interesting LVN often overlaps FVG
3. **Confirmation** — footprint absorption/aggression at an order block

Skipping to footprint without context is called out as the most common failure mode: delta flips inside high-volume balance are noise.

## 3.3 Auction Market Theory (compressed)

Price is a continuous two-way auction seeking agreement.

- **Balance** — rotates between high and low; builds volume in the middle (value area)
- **Imbalance** — one side overwhelms; leaves thin, fast-traded areas that later appear as FVG/LVN

First decision of the framework: **reversion (balance)** vs **continuation (imbalance)**.

## 3.4 Anchored VWAP and swing structure

- Anchored VWAP (HTF pivot, 4H swing, session) = running fair-value line for the active leg
- Holding above VWAP in an up-leg (below in a down-leg) supports ongoing imbalance
- Swing highs/lows are structural fingerprints: trending discovery vs overlapping balance
- Same structure later validates order-block location

## 3.5 Three live questions

Ask in order; do not skip:

1. What is the market doing broadly? *(Auction / Order Flow)*
2. Where specifically is that interesting? *(Volume Profile)*
3. Is that level defended right now? *(Footprint)*

## 3.6 Relationship to the six-component FVG model

| Order-flow idea | Platform / FVG model analogue |
|---|---|
| HTF auction bias | HTF bias EMA alignment (component) |
| Imbalance residue | FVG / imbalance geometry |
| Level interest | Liquidity map / pivots |
| Confirmation at OB | Retest + displacement evidence (research modules) |

These are **aligned lenses**, not identical implementations. Phase-one platform code implements six deterministic primitives; full footprint confirmation remains a research capability candidate.

## 3.7 Ties to the graph

Nodes include: Three-Layer Order Flow Framework, Reading Order: Context → Location → Confirmation, Auction Market Theory, Balanced vs Imbalanced Markets, Anchored VWAP, Swing Highs/Lows, Volume Profile, Footprint Chart, Absorption, Aggression, Delta, Delta Shift, HVN, LVN, FVG, Order Block.

## 3.8 Capability lens

Propose capability **`auction.context.v1`**:

- **Inputs:** HTF candles, anchors, swing pivots
- **Outputs:** `{state: balance|imbalance, bias, evidence[], data_quality}`
- **Authority:** research labels only
- **Outcomes:** agreement with later eligible setups; reduced false footprint alerts
- **Retirement:** if state labels stop predicting continuation/reversion better than baseline

---

← [Events & authority](02-events-provenance-authority.md) · [TOC](README.md) · [Next: Candlesticks and footprint →](04-candlesticks-and-footprint.md)
