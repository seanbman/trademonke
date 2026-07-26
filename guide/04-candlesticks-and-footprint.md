# 4. Candlesticks, footprint, absorption, and delta

← [Order Flow](03-auction-and-order-flow.md) · [TOC](README.md) · [Next: Volume profile →](05-volume-profile-and-value.md)

---

## 4.1 Candlestick anatomy (extracted)

Graph communities under **Candlestick Patterns** / cheat sheets capture:

- OHLC: open, high, low, close
- Body vs upper/lower wick
- Classic names: doji, engulfing, hammer, harami, marubozu, spinning top, abandoned baby, etc.

**Role in the stack:** candlesticks are the *time-aggregated* view. They are necessary but incomplete — they do not show bid/ask aggression inside the bar.

## 4.2 Footprint chart

A footprint replaces a plain candle with a **price × bid/ask volume grid** inside that bar:

- Sellers hitting the bid vs buyers lifting the offer
- Finest chart-native resolution of order flow
- “Blueprint of the candle” from open to close

## 4.3 Absorption

**Definition (notes + white paper):** one side absorbs aggressive flow at a price without surrendering a new extreme (e.g. large bids absorb selling without a new low).

On footprint: outsized size at the same price across prints/candles. Notes link absorption to **order block formation** — treat as a *measurement-linked hypothesis*, not proven institutional intent.

## 4.4 Aggression and delta

- **Aggression** — dominant aggressive side forcing price
- **Delta** — ask-side volume minus bid-side volume (implementation details vary by vendor)
- **Delta shift** — change in delta regime that may confirm or deny a level defense

Without Layer-1 context, delta alone is underdetermined.

## 4.5 Candlestick patterns vs footprint confirmation

| Pattern sheet claim | Safer research use |
|---|---|
| Engulfing = reversal | Candidate *after* auction context + location |
| Doji = indecision | Compatible with balance; not a trade by itself |
| Wick rejection | Related to sweep/reclaim measurements on levels |

Platform domain code prefers **objective geometry** (wick beyond level + close back inside) over named candlestick folklore.

## 4.6 Ties to the graph

Multiple screenshot-derived communities duplicate pattern names (expected). Prefer platform `Candle` / `CandleRecord` as computational god objects; treat sheet names as educational overlays.

## 4.7 Capability lens

Capabilities to separate:

1. **`candle.geometry.v1`** — pure OHLC features (deterministic)
2. **`footprint.confirm.v1`** — optional vendor-specific prints (research; higher cost; may be absent)
3. **`pattern.label.v1`** — soft labels from classic patterns (explainability only; never sole eligibility)

Authority: none may create orders. Footprint capability degrades gracefully to “unavailable” (P-010 uncertainty visible).

---

← [Order Flow](03-auction-and-order-flow.md) · [TOC](README.md) · [Next: Volume profile →](05-volume-profile-and-value.md)
