# 11. Sessions, ORB, AMD, and regime matchmaking

← [Six-component confluence](10-six-component-confluence.md) · [TOC](README.md) · [Next: Platform substrate →](12-platform-as-capability-substrate.md)

---

## 11.1 Sessions as temporal context

Graph concepts: London Open, New York Open, Asia session, midnight open, PDH/PDL, session VWAP anchors.

Sessions do not create edge by themselves; they **condition prior probabilities** for sweep/imbalance behavior and define anchors for VWAP/profile ranges.

## 11.2 Opening Range Breakout (ORB)

Notes cover ORB on 5m/15m/30–60m, retest entries, consecutive closes, session filters. Graph also links ORB remediation ideas (EMA/HTF filters, fib).

**Platform stance:** ORB is a research narrative module unless promoted with a versioned detector and tests. Unsafe note language is rejected.

## 11.3 AMD — Power of Three

Accumulation → Manipulation → Distribution appears across screenshots and notes.

Useful as a **story template** for episode phases; dangerous if reified as claimed intent. Prefer mapping to measurable episode states (e.g. level formation → sweep → displacement → imbalance link) already closer to platform episodes.

## 11.4 Regime matchmaking (from notes)

Screenshot “strategy matchmaker” maps environments to tactics:

| Environment | Hint |
|---|---|
| Clear trend | Continuation / pullback tools |
| Sideways consolidation | AMD-style rotation / mean reversion |
| High news volatility | Stand down or widen filters |
| Low volume quiet | Avoid forced breakout tactics |

Indicators cited as environment sensors: 200 EMA, flat Bollinger + low ADX, ATR spikes, consolidating VWAP.

## 11.5 How this feeds Capability Architecture

Regime detection is a **discovery input** (Layer 4): it should not silently rewrite strategy code. It should:

1. emit regime observation events
2. propose enabling/disabling contextual capabilities
3. require control-plane approval for anything that changes eligibility

## 11.6 Ties to the graph

ORB/AMD communities, ADX/ATR/BB concept nodes, session glossary, handwritten matchmaker sheets.

## 11.7 Capability lens

**`regime.classify.v1`** — outputs regime posterior + features  
**`session.anchor.v1`** — session bounds & opens  
**`orb.detect.v1`** — optional research  

Composite policy capability **`policy.regime_routing.v1`** selects which contextual scorers are active — never bypasses mandatory gates.

---

← [Six-component confluence](10-six-component-confluence.md) · [TOC](README.md) · [Next: Platform substrate →](12-platform-as-capability-substrate.md)
