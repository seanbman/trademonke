# 5. Volume profile, value, and FVG as LVN

← [Candlesticks & footprint](04-candlesticks-and-footprint.md) · [TOC](README.md) · [Next: Classic chart patterns →](06-classic-chart-patterns.md)

---

## 5.1 Volume profile as a sideways auction

Volume profile plots **volume-at-price** rather than volume-over-time. It answers: where did the auction *accept* price, and where did it *traverse* without agreement?

| Term | Meaning |
|---|---|
| **POC** | Point of Control — price with most volume |
| **Value Area** | Band containing a configured share of volume (commonly ~70%) |
| **HVN** | High Volume Node — accepted/fair areas; expect rotation or defense |
| **LVN** | Low Volume Node — thin acceptance; expect faster traversal or magnet behavior |

## 5.2 The key identity in the Order Flow paper

> **Fair Value Gap (FVG) ≈ Low Volume Node (LVN)** in many practical readings.

Imbalance legs leave thin areas; those areas later appear as geometric FVGs *and* as LVNs on a profile of the same move. This is a powerful **location** bridge between ICT-style imbalance geometry and auction-profile language.

## 5.3 How location feeds confirmation

Practical sequence from notes:

1. Establish balanced vs trending context
2. Find LVN that overlaps an FVG
3. Seek footprint absorption/aggression at the related order block

Skipping (1) or (2) produces false (3).

## 5.4 Platform analogue

Platform stores **imbalances** (FVG/IFVG geometry) and **liquidity levels** (confirmed pivots), not necessarily a full volume-profile engine yet. Profile is therefore:

- conceptually first-class in the graph
- an **implementation candidate** for a location capability
- optional if FVG geometry + liquidity map already provide location proxies

## 5.5 Cost/benefit of adding real profile computation

| Benefit | Cost |
|---|---|
| Better “accepted vs thin” language | Tick/volume data requirements |
| Aligns notes ↔ detectors | Storage and replay complexity |
| Improves location precision | Vendor differences in VP algorithms |

**Implementation strategy:** start with closed-candle FVG ∩ pivot proximity as a cheap LVN proxy; graduate to true VP when data contracts exist.

## 5.6 Ties to the graph

Order Flow Framework nodes: Volume Profile, POC, Value Area, HVN, LVN, FVG; plus screenshot FRVP/HVN overlays.

## 5.7 Capability lens

**`location.profile.v1`**

- Inputs: range definition (session, swing, anchored), volume-at-price or proxy
- Outputs: POC/VA/HVN/LVN set + overlap flags with imbalances
- Authority: annotate only
- Outcomes: lift in precision of eligible setups when location gate is enabled
- Constraint: no lookahead; profile finalized on closed range rules

---

← [Candlesticks & footprint](04-candlesticks-and-footprint.md) · [TOC](README.md) · [Next: Classic chart patterns →](06-classic-chart-patterns.md)
