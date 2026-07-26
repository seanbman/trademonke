CONFLUENCE-BASED TRADE FILTRATION SYSTEM

A Weighted Scorecard Architecture for Multi-Asset Entry Validation

Futures • Forex • Crypto • Indices • Gold

1. Purpose

This white paper specifies a filtration engine that screens multi-asset
universes for high-probability entries and suppresses low-quality
setups. The system replaces rigid all-or-nothing parameter matching with
a weighted scorecard: each trade candidate is scored across seven
confluence categories, gated by three non-negotiable conditions, and
assigned a tier — A+, A++, or A+++ — that determines position sizing.

2. Architecture Overview

Every candidate setup passes through two stages:

-   Stage 1: Gatekeepers — binary pass/fail conditions. Fail any one and
    the setup is rejected before scoring.

-   Stage 2: Weighted Scorecard — 100-point scale across seven
    confluence categories, each carrying an importance weight reflecting
    its historical reliability as a probability driver.

3. Gatekeeper Filters

  -------------------- --------------------------------------------------
  Gate                 Pass Condition

  Minimum Risk:Reward  Projected R:R (structural invalidation vs. target
                       liquidity) must be ≥ 1:2. Below that, reject
                       regardless of confluence score.

  HTF Directional Bias HTF trend must resolve to exclusively Bullish or
                       Bearish. “Ranging” HTF disqualifies the setup
                       outright — no scoring applied.

  Session / Kill-Zone  Entry must fall inside the asset’s active
  Timing               liquidity window (see Section 5). Setups forming
                       outside kill zones are down-weighted or rejected.
  -------------------- --------------------------------------------------

4. Confluence Scorecard (100 pts)

  -------------------- -------- ------------ -------------------------------
  Category             Weight   Importance   Key Signals

  Multi-Timeframe      20       Critical /   HTF trend regime (50/200 EMA),
  Alignment (HTF bias           Gate         LTF BOS/CHoCH firing in same
  → LTF trigger)                             direction as HTF bias.

  Market Structure     20       Critical     Sharp displacement leg leaving
  Shift + Displacement                       an unmitigated FVG or inverse
                                             FVG; confirms institutional
                                             intent, not a slow drift.

  Order Flow /         15       High         CVD divergence vs. price, Order
  Microstructure                             Book Imbalance ≥60% one side,
                                             footprint delta clusters
                                             (trapped orders).

  Volatility Expansion 15       High         IV percentile ≤20th expanding,
  Confirmation                               price outside 2nd-dev VWAP band
                                             on heavy relative volume,
                                             ADX>25 with +DI/-DI cross.

  Premium/Discount     10       Medium       Entry in discount (longs) or
  Positioning                                premium (shorts) zone of HTF
                                             dealing range; not chasing an
                                             extended move.

  Macro / Intermarket  10       Medium       DXY inverse check, SMT
  Correlation                                divergence between correlated
                                             pairs (EURUSD/GBPUSD, BTC/ETH),
                                             equity-index anchor (ES/NQ) for
                                             crypto risk-on/off.

  Asset-Class Specific 10       Medium       Volume Profile/session behavior
  Layer                                      specific to the instrument
                                             being traded — see Section 5.
  -------------------- -------- ------------ -------------------------------

5. Asset-Class Specific Layers

Category 7 of the scorecard (10 pts) is populated by the
instrument-specific filters below. These are not interchangeable — apply
only the layer matching the asset being screened.

5.1 Futures (ES, NQ, YM, RTY)

  ----------------------- -----------------------------------------------
  Filter                  Purpose

  Volume Profile &        Filters entries around High-Volume Nodes (HVN);
  Session Deviations      execution must stay aligned with Value Area
                          boundaries, not chase into low-volume air.

  Footprint Delta         Aggressive market sell (or buy) orders failing
  Clusters                to move price at a structural level, leaving a
                          trapped-order cluster on the wick — absorption
                          signal.

  VIX Filter (equity      Only trade ES/NQ/YM setups when VIX > 16;
  index futures)          low-VIX sessions materially reduce win rate on
                          breakout-style entries.

  Kill Zone               New York AM (07:00–10:00 ET) is primary; the
                          10:00–11:00 ET Silver Bullet window is the
                          secondary high-probability entry.
  ----------------------- -----------------------------------------------

5.2 Forex (FX)

  ----------------------- -----------------------------------------------
  Filter                  Purpose

  Session Time-Block      Alerts restricted to London/New York overlap to
  Gating                  avoid flat consolidation and low-liquidity
                          chop.

  Interest Rate           Rank pairs by central-bank swap differential;
  Differentials           favor setups aligned with the positive carry
                          direction.

  News Blackout           Gate the system to stop generating entries 15
                          minutes before/after CPI, NFP, and FOMC
                          releases.

  Kill Zone               London (02:00–05:00 ET) for EUR/GBP majors; New
                          York AM for USD-driven continuation.
  ----------------------- -----------------------------------------------

5.3 Crypto

  ----------------------- -----------------------------------------------
  Filter                  Purpose

  Open Interest & Funding Validates breakouts by requiring OI expansion
  Discrepancies           alongside the move — confirms new positioning,
                          not just short-covering noise.

  Funding Rate Extremes + Deeply negative funding stacked with cascading
  Liquidation Heatmap     short liquidations on the heatmap flags a
                          high-probability short-squeeze long.

  BTC/ETH SMT Divergence  If BTC prints a new lower low but ETH fails to
                          follow, that’s hidden accumulation — mark ETH
                          as the higher-probability long.

  Kill Zone               New York AM behaves almost identically to ES/NQ
                          since the same institutional desks trade both;
                          widen FVG threshold (>0.15% of price) to avoid
                          noise at crypto volatility levels.
  ----------------------- -----------------------------------------------

5.4 Indices (Broad Market)

  ----------------------- -----------------------------------------------
  Filter                  Purpose

  Equity Index Anchor     Use ES/NQ as the macro risk gauge for crypto
  (ES/NQ)                 and high-beta names; heavy downside liquidation
                          on ES/NQ should throttle or down-weight long
                          alerts elsewhere.

  Market Breadth / VIX    VIX > 16 gatekeeper as above; extreme VIX
  Regime                  spikes (>30) favor mean-reversion setups over
                          breakout continuation.

  SMT Divergence (ES vs.  When ES makes a new high but NQ fails to
  NQ)                     confirm, that’s an early warning of
                          broad-market exhaustion — use as a fade
                          confluence.

  Kill Zone               09:30–10:30 ET (NYSE cash open) is the
                          highest-conviction window; most intraday index
                          moves begin or complete here.
  ----------------------- -----------------------------------------------

5.5 Gold (XAUUSD)

  ----------------------- -----------------------------------------------
  Filter                  Purpose

  DXY Inverse Correlation ~−0.85 historical correlation. Bullish XAUUSD
                          setup with DXY simultaneously breaking its own
                          LTF support materially increases confidence.

  Correlation Breakout    When DXY and gold move together (both up or
  Awareness               both down), treat it as a rare regime shift —
                          not noise — and reduce size rather than fade it
                          blindly.

  Real Yields (US 10Y     Rising real yields pressure gold even against a
  minus inflation         weakening dollar since gold carries no yield —
  expectations)           check this before trusting the DXY signal
                          alone.

  EURUSD Cross-Check      EURUSD and gold are positively correlated; a
                          gold long wants EURUSD also bullish or
                          approaching a bullish point of interest.

  Kill Zone               London (02:00–05:00 ET) typically produces
                          gold’s daily high or low; New York AM for
                          continuation.
  ----------------------- -----------------------------------------------

6. Trade Rating System

Final tier is determined by total scorecard points plus the minimum R:R
floor for that tier. A higher score with an insufficient R:R is capped
at the tier below.

  -------- --------- -------- -------------------------------------------
  Tier     Score     Min R:R  Requirements

  A+       60–74     1:2      All 3 gatekeepers pass. HTF/LTF alignment +
                              Market Structure Shift categories both
                              scored. Baseline tradable setup — smallest
                              position size in the tiering system.

  A++      75–89     1:3      Everything in A+, plus Order Flow
                              confirmation AND Volatility Expansion both
                              scored. At least 5 of 7 categories
                              contributing points. Standard position
                              size.

  A+++     90–100    1:4      Full-confluence setup: all 7 categories
                              scored, Macro/Intermarket correlation
                              confirmed (not just neutral), and entry
                              lands inside the primary kill zone for that
                              asset class. Maximum position size —
                              reserved for the cleanest, rarest setups.
  -------- --------- -------- -------------------------------------------

7. Technical Implementation Checklist

-   Asset Screener: Continuously sweep the selected token, futures
    ticker, or currency-pair universe for high RVOL and expanding ATR/IV
    percentile.

-   Directional Gating: Classify HTF trend as exclusively Bullish,
    Bearish, or Ranging. Ranging = automatic rejection (Gate 2).

-   Scoring Engine: Run the 100-point scorecard only after both
    gatekeepers (R:R, directional bias) pass.

-   R:R Pre-Calculation: Auto-calculate invalidation (structural swing
    high/low) against target liquidity zones; reject anything under 1:2
    before scoring even runs.

-   Correlation Cross-Reference: Cross-check DXY, ES/NQ, and BTC/ETH SMT
    divergence for every candidate regardless of asset class —
    correlated markets are cross-referenced, not siloed.

-   Session Gating: Gate alerts to each asset's primary kill zone
    (Section 5); setups forming outside these windows are down-weighted,
    not treated equally.

8. Scoring Logic (Reference Pseudocode)

def evaluate_trade(asset_data): # Stage 1 — Gatekeepers (binary) if
asset_data.risk_reward < 2.0: return "REJECT" if asset_data.htf_bias ==
"RANGING": return "REJECT" if not asset_data.in_killzone: score_penalty
= True # Stage 2 — Weighted scorecard (100 pts) score = 0 if
asset_data.htf_ltf_aligned: score += 20 if asset_data.displacement_fvg:
score += 20 if asset_data.cvd_divergence or asset_data.obi_active: score
+= 15 if asset_data.iv_expanding or asset_data.adx > 25: score += 15 if
asset_data.in_discount_or_premium: score += 10 if
asset_data.macro_correlation_aligned: score += 10 if
asset_data.asset_specific_layer_met: score += 10 # Stage 3 — Tier
assignment if score >= 90 and asset_data.risk_reward >= 4.0: return
"A+++" if score >= 75 and asset_data.risk_reward >= 3.0: return "A++" if
score >= 60 and asset_data.risk_reward >= 2.0: return "A+" return "NO
TRADE"
