# 6. Classic chart patterns (triangles, wedges, flags)

← [Volume profile](05-volume-profile-and-value.md) · [TOC](README.md) · [Next: Market structure vocabulary →](07-market-structure-vocabulary.md)

---

## 6.1 What the graph actually contains

**Yes — wedge patterns are present as data**, along with a wide classic-pattern catalog extracted primarily from screenshot cheat sheets.

### Wedges (confirmed nodes)

| Pattern | Present? | Notes |
|---|---|---|
| **Rising Wedge** | Yes (multiple nodes) | Duplicate extractions across screenshots |
| **Falling Wedge** | Yes (multiple nodes) | Same |
| Expanding / diagonal variants by other names | Not as distinct wedge labels | May appear under broadening structures |

### Other highly connected pattern families

- Triangles: ascending, descending, symmetrical, broadening
- Flags / pennants (bull & bear)
- Head & shoulders / inverted
- Double/triple tops & bottoms
- Cup & handle, scallops, diamonds
- Measured moves

These live in communities such as **Chart Pattern Catalog**, **Triangle Patterns**, and related screenshot clusters.

## 6.2 How to use patterns without letting them drive the system

Classic patterns are **compressed stories about swing structure**. They overlap auction language:

| Pattern story | Auction / structure reading |
|---|---|
| Rising wedge | Often balance→imbalance risk; treat as hypothesis, not destiny |
| Falling wedge | Compression in decline; needs context confirmation |
| Flag/pennant | Pause in imbalance (continuation candidate) |
| Ascending triangle | Higher lows into resistance — still needs location + confirmation |
| Broadening | Rising volatility / contested discovery |

**Rule:** patterns are Layer-0 *hints*. They do not replace Context → Location → Confirmation, and they do not override six-component gates.

## 6.3 Ambiguity in the graph

Suggested questions in `GRAPH_REPORT.md` flag AMBIGUOUS edges (e.g. candlestick↔support/resistance). That honesty should remain: pattern sheets are pedagogical; edges between them are often weak.

## 6.4 Implementation strategies

1. **Catalog-only** — keep as wiki/graph concepts for explanation (current state for many nodes)
2. **Geometry detectors** — implement objective swing-compression metrics (trendline convergence, BB width, ATR crush) without requiring human pattern names
3. **Label assist** — model suggests pattern name for UI; never for eligibility

Prefer (2) for research features; keep (1) for education; restrict (3) with P-010.

## 6.5 Capability lens

**`pattern.catalog.v1`** — knowledge capability (documents + graph), no market authority  
**`compression.detect.v1`** — deterministic geometry capability feeding regime matchmaking ([Chapter 11](11-sessions-orb-amd-regimes.md))

---

← [Volume profile](05-volume-profile-and-value.md) · [TOC](README.md) · [Next: Market structure vocabulary →](07-market-structure-vocabulary.md)
