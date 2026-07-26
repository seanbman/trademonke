# 7. Market structure vocabulary (BOS, CHoCH, SMT)

← [Classic patterns](06-classic-chart-patterns.md) · [TOC](README.md) · [Next: Liquidity maps →](08-liquidity-maps-and-sweeps.md)

---

## 7.1 Why a shared vocabulary

ICT/SMC notes in the graph use overlapping acronyms (BOS, CHoCH/ChoC/MSS, IDM, OB, FVG, IFVG, BSL/SSL). Platform code uses **objective closed-candle rules**. This chapter aligns names without claiming they are identical.

## 7.2 Break of Structure (BOS)

**Notes sense:** price closes beyond a relevant swing, continuing the directional story.

**Platform sense (`structure_break`):** close strictly beyond the extreme of a completed lookback. Wick-only cross fails (`STRATEGY_SPEC.md`).

Use platform definition for automation; use notes language for narration in the GUI.

## 7.3 Change of Character (CHoCH / ChoC / MSS)

Notes treat CHoCH/MSS as a shift in the auction’s character (often against prior structure). Graph nodes include multiple spellings.

**Capability stance:** store as a **labeled hypothesis event** until a single deterministic definition is versioned in the capability registry. Do not silently merge spellings into one detector.

## 7.4 SMT divergence

**Platform rule:** primary creates a new lookback extreme while aligned comparison symbol does not. Missing data → `false` with `data_quality=missing`.

Current Freqtrade adapter may leave SMT unwired → fail-closed (false), keeping execution inert — an authority feature, not a bug narrative.

## 7.5 HTF bias

**Platform:** all configured close/EMA pairs must align. Pine reference uses 15m/30m/1h; research defaults may add 4h/1d EMA50 via configuration (explicit non-parity).

Maps cleanly to Order Flow **context**.

## 7.6 Premium / discount / OTE / EQ

Graph includes OTE, premium/discount, equilibrium. These are **location heuristics** relative to a dealing range — complementary to VP/LVN, not substitutes for gates.

## 7.7 Ties to the graph

Liquidity / FVG strategy communities; screenshot ICT glossaries; domain functions `structure_break()`, `smt_divergence()`, `htf_bias` pathway via indicator engine.

## 7.8 Capability lens

Version each as its own capability:

| Capability ID | Authority |
|---|---|
| `structure.bos.v1` | research boolean + evidence |
| `structure.choch.v1` | research-only until definition locked |
| `structure.smt.v1` | boolean + data_quality |
| `structure.htf_bias.v1` | boolean vector per timeframe |

Composite confluence ([Chapter 10](10-six-component-confluence.md)) *consumes* these; it must not redefine them inline (composition contracts from Volume I Ch. 7).

---

← [Classic patterns](06-classic-chart-patterns.md) · [TOC](README.md) · [Next: Liquidity maps →](08-liquidity-maps-and-sweeps.md)
