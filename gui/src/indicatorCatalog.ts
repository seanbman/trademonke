import type {ChartLayerKey, IndicatorKey, PatternTypeKey} from "./chartLayers";
import {INDICATORS, LAYER_LABELS, PATTERN_LABELS} from "./chartLayers";

export type CatalogAuthority = "scored" | "overlay" | "soft_label" | "future";
export type CatalogKind = "indicator" | "layer" | "pattern" | "future";

export type CatalogEntry = {
  id: string;
  kind: CatalogKind;
  title: string;
  summary: string;
  looksLike: string;
  identification: string;
  guiFlags: string;
  authority: CatalogAuthority;
  guideHint?: string;
};

const INDICATOR_PAGES: Record<IndicatorKey, Omit<CatalogEntry, "id" | "kind" | "title">> = {
  htf_bias: {
    summary: "Higher-timeframe context: whether closes sit on the bullish or bearish side of a 50-period average.",
    looksLike: "No dedicated drawing. Evidence appears in Signal detail as each HTF close versus EMA-50.",
    identification: "On each configured higher timeframe, compare the latest closed candle’s close to that timeframe’s EMA-50. Long bias wants close above EMA; short bias wants close below. Uses closed candles only.",
    guiFlags: "Signal detail chip shows Confirmed / Not confirmed. Selecting it fills the evidence line with per-timeframe close vs EMA values.",
    authority: "scored",
    guideHint: "guide/10-six-component-confluence.md · guide/07-market-structure-vocabulary.md",
  },
  liquidity_sweep: {
    summary: "A wick that ran a confirmed liquidity level and closed back inside the range — measured, not guessed intent.",
    looksLike: "Liquidity layer: blue support / amber resistance horizontal marks at confirmed pivot levels linked to the focused idea.",
    identification: "Requires a confirmed pivot level. The candle’s wick must trade through the level and the close must finish back on the inside (long: sweep below then close above; short: reverse). Closed candles only.",
    guiFlags: "Confirmed chip when a sweep is recorded. Liquidity overlay toggle reveals the linked level; targets often reference related liquidity.",
    authority: "scored",
    guideHint: "guide/08-liquidity-maps-and-sweeps.md",
  },
  fvg_retest: {
    summary: "Price revisiting an active three-candle fair value gap (imbalance) in the setup direction.",
    looksLike: "Fair value gap layer: translucent violet band between gap lower/upper bounds.",
    identification: "Detect a directional 3-candle gap, keep it while status is active/waiting, then mark retest when later closed price interacts with the zone. Soft geometry only until confirmation passes.",
    guiFlags: "Confirmed chip plus FVG zone overlay when the layer is on. Evidence shows zone bounds and status text.",
    authority: "scored",
    guideHint: "guide/09-fvg-and-order-blocks.md",
  },
  retest_confirmation: {
    summary: "Closed-candle confirmation that the retest held beyond the gap midpoint and the prior close.",
    looksLike: "Does not draw a unique shape by itself. When a research plan exists, Entry zone (blue band) becomes available after confirmation paths succeed.",
    identification: "After an FVG retest context, require a closed candle that clears the gap midpoint and the previous candle’s close in the setup direction.",
    guiFlags: "Confirmed chip in Signal detail. Unlocks entry geometry for approved plans; three-questions Confirmation strip updates.",
    authority: "scored",
    guideHint: "guide/10-six-component-confluence.md · guide/13-unified-reading-protocol.md",
  },
  smt: {
    summary: "Cross-market divergence between the primary symbol and its comparison market (typically BTC vs ETH).",
    looksLike: "No chart polyline. Evidence text names the comparison symbol and data-quality state.",
    identification: "Over a fixed lookback of closed candles, compare swing extremes of primary vs comparison. Divergence passes when extremes disagree in the direction-specific sense coded in domain signals.",
    guiFlags: "Confirmed / Not confirmed chip with comparison + data-quality evidence. Never treated as order authority.",
    authority: "scored",
    guideHint: "guide/10-six-component-confluence.md",
  },
  structure: {
    summary: "A closed break beyond the prior range extreme — market structure shift on closed candles.",
    looksLike: "No separate structure polyline today. Structural stop geometry appears under Stop loss when a plan exists.",
    identification: "Compare the latest closed candle to a lookback of prior closed candles. Long: close above prior highs; short: close below prior lows (engine lookback).",
    guiFlags: "Confirmed chip; influences research stop placement and three-questions context language.",
    authority: "scored",
    guideHint: "guide/07-market-structure-vocabulary.md",
  },
};

const LAYER_PAGES: Record<ChartLayerKey, Omit<CatalogEntry, "id" | "kind" | "title">> = {
  liquidity: {
    summary: "Confirmed liquidity levels tied to the focused idea.",
    looksLike: "Horizontal marks — blue for support-side, amber for resistance-side — at measured pivot prices.",
    identification: "Built from confirmed pivots with left/right confirmation; status filters inactive levels. Not every pivot is drawn — only levels linked to the focused setup when available.",
    guiFlags: "Overlay bar → Liquidity. Unavailable when no linked level exists for the focused idea.",
    authority: "overlay",
    guideHint: "guide/08-liquidity-maps-and-sweeps.md",
  },
  fvgZones: {
    summary: "Active fair value gap / imbalance zones for the focused episode.",
    looksLike: "Violet translucent rectangles between gap lower and upper prices.",
    identification: "Three-candle imbalance detection; zones expire/invalidate/consume via episode status. Overlay hides invalidated, expired, and consumed zones.",
    guiFlags: "Overlay bar → Fair value gap. Pair with the fvg_retest confluence chip for pass/fail state.",
    authority: "overlay",
    guideHint: "guide/09-fvg-and-order-blocks.md",
  },
  entry: {
    summary: "Approved research entry region from a versioned recommendation.",
    looksLike: "Blue translucent entry band from geometry.entry_region lower–upper.",
    identification: "Created only after qualification/risk approval produces a valid recommendation. Not a live order ticket.",
    guiFlags: "Overlay bar → Entry zone. Unavailable until a valid plan exists for the focused idea.",
    authority: "overlay",
    guideHint: "docs/GUI.md · guide/10-six-component-confluence.md",
  },
  stop: {
    summary: "Initial structural/research stop from approved geometry.",
    looksLike: "Red stop marker / price from geometry.initial_stop.",
    identification: "Derived from setup geometry after risk checks; immutable per recommendation version.",
    guiFlags: "Overlay bar → Stop loss. Research only — dry-run / no live submission here.",
    authority: "overlay",
  },
  targets: {
    summary: "Profit boxes / R-multiple targets from approved geometry.",
    looksLike: "Green target markers for each profit box label.",
    identification: "Versioned recommendation profit_boxes; not live bracket orders.",
    guiFlags: "Overlay bar → Targets when boxes exist on the focused plan.",
    authority: "overlay",
  },
  patterns: {
    summary: "Optional soft-label classic shapes (wedges, triangles, flags, doubles).",
    looksLike: "Dashed violet trend lines for upper/lower boundaries (legend: Pattern soft-label).",
    identification: "Closed-candle pivot geometry in app.domain.patterns. Each item is soft_label=true with authority=none.",
    guiFlags: "Overlay bar → Patterns, plus the pattern kit toggles for each shape family.",
    authority: "soft_label",
    guideHint: "guide/06-classic-chart-patterns.md · docs/GUI.md",
  },
};

const PATTERN_PAGES: Record<PatternTypeKey, Omit<CatalogEntry, "id" | "kind" | "title">> = {
  rising_wedge: {
    summary: "Both boundaries rise while the range narrows — soft location nickname only.",
    looksLike: "Two upward-sloping dashed violet lines converging.",
    identification: "Last two confirmed highs and lows: both slopes up, lower slope steeper, width narrows. Break status if close clears the upper boundary after the shape end.",
    guiFlags: "Pattern kit → Rising wedge. Drawn only when Patterns overlay is on and status ≠ expired.",
    authority: "soft_label",
    guideHint: "guide/06-classic-chart-patterns.md",
  },
  falling_wedge: {
    summary: "Both boundaries fall while the range narrows — soft location nickname only.",
    looksLike: "Two downward-sloping dashed violet lines converging.",
    identification: "Both slopes down, upper slope steeper (more negative), width narrows. Break if close takes out the lower boundary after the shape end.",
    guiFlags: "Pattern kit → Falling wedge. Soft tag; context beats pattern if they disagree.",
    authority: "soft_label",
    guideHint: "guide/06-classic-chart-patterns.md",
  },
  ascending_triangle: {
    summary: "Flat-ish highs with rising lows and a narrowing range.",
    looksLike: "Near-flat upper dashed line + rising lower line.",
    identification: "High slope within flat tolerance, low slope rising, width narrows. Direction hint long when classified.",
    guiFlags: "Pattern kit → Ascending triangle under Patterns overlay.",
    authority: "soft_label",
  },
  descending_triangle: {
    summary: "Flat-ish lows with falling highs and a narrowing range.",
    looksLike: "Near-flat lower dashed line + descending upper line.",
    identification: "Low slope flat, high slope falling, width narrows. Direction hint short when classified.",
    guiFlags: "Pattern kit → Descending triangle under Patterns overlay.",
    authority: "soft_label",
  },
  flag: {
    summary: "Short consolidation after a strong pole move — soft continuation cartoon.",
    looksLike: "Boundary lines over the consolidation window after the pole.",
    identification: "Measures a closed-candle pole then a tighter consolidation; classifies flag vs pennant by geometry. Soft label only.",
    guiFlags: "Pattern kit → Flag.",
    authority: "soft_label",
  },
  pennant: {
    summary: "Tightening consolidation after a pole — soft continuation cartoon.",
    looksLike: "Converging dashed lines after the pole segment.",
    identification: "Same pole+consolidation pipeline as flag with pennant geometry thresholds.",
    guiFlags: "Pattern kit → Pennant.",
    authority: "soft_label",
  },
  double_top: {
    summary: "Two similar highs separated by a pullback — soft reversal nickname.",
    looksLike: "Points/lines at the paired highs (and neck context in measurements).",
    identification: "Two confirmed highs within equal-tolerance bps with an intervening low. Soft label only.",
    guiFlags: "Pattern kit → Double top.",
    authority: "soft_label",
  },
  double_bottom: {
    summary: "Two similar lows separated by a bounce — soft reversal nickname.",
    looksLike: "Points/lines at the paired lows.",
    identification: "Two confirmed lows within equal-tolerance bps with an intervening high. Soft label only.",
    guiFlags: "Pattern kit → Double bottom.",
    authority: "soft_label",
  },
};

/** Concepts documented in guides but not scored/overlaid in the workstation yet. */
export const FUTURE_CATALOG: CatalogEntry[] = [
  {
    id: "future:order_blocks",
    kind: "future",
    title: "Order blocks / IFVG fib boxes",
    summary: "Institutional candle / fib sniper boxes appear in research guides but are not a first-class detector in this MVP.",
    looksLike: "Not drawn in the current workstation.",
    identification: "Not implemented as a closed-candle domain detector here.",
    guiFlags: "Listed as Not in workstation yet. Use confluence FVG + structure instead.",
    authority: "future",
    guideHint: "guide/09-fvg-and-order-blocks.md",
  },
  {
    id: "future:volume_profile",
    kind: "future",
    title: "Volume profile / value area",
    summary: "Auction-market value tools from the guide stack — not wired into GUI overlays yet.",
    looksLike: "Not drawn in the current workstation.",
    identification: "Not implemented.",
    guiFlags: "Not in workstation yet.",
    authority: "future",
    guideHint: "guide/05-volume-profile-and-value.md",
  },
  {
    id: "future:sessions_orb",
    kind: "future",
    title: "Sessions / ORB / AMD regimes",
    summary: "Session and opening-range framing from the guides — not a scored component yet.",
    looksLike: "Not drawn in the current workstation.",
    identification: "Not implemented.",
    guiFlags: "Not in workstation yet.",
    authority: "future",
    guideHint: "guide/11-sessions-orb-amd-regimes.md",
  },
  {
    id: "future:footprint",
    kind: "future",
    title: "Footprint / absorption / delta",
    summary: "Order-flow reading aids — outside the deterministic OHLC confluence MVP.",
    looksLike: "Not drawn in the current workstation.",
    identification: "Not implemented (no footprint feed).",
    guiFlags: "Not in workstation yet.",
    authority: "future",
    guideHint: "guide/04-candlesticks-and-footprint.md",
  },
  {
    id: "future:oscillators",
    kind: "future",
    title: "Classic oscillators (RSI, MACD, …)",
    summary: "Not part of the six-component structure/liquidity/FVG model used here.",
    looksLike: "Not drawn in the current workstation.",
    identification: "Not implemented by design for this research stack.",
    guiFlags: "Not in workstation yet.",
    authority: "future",
  },
];

export function buildCatalog(): CatalogEntry[] {
  const indicators = INDICATORS.map((item) => ({
    id: `indicator:${item.key}`,
    kind: "indicator" as const,
    title: item.label,
    ...INDICATOR_PAGES[item.key],
  }));
  const layers = LAYER_LABELS.map((item) => ({
    id: `layer:${item.key}`,
    kind: "layer" as const,
    title: item.label,
    ...LAYER_PAGES[item.key],
  }));
  const patterns = PATTERN_LABELS.map((item) => ({
    id: `pattern:${item.key}`,
    kind: "pattern" as const,
    title: item.label,
    ...PATTERN_PAGES[item.key],
  }));
  return [...indicators, ...layers, ...patterns, ...FUTURE_CATALOG];
}

export const CATALOG = buildCatalog();

export function catalogById(id: string): CatalogEntry | undefined {
  return CATALOG.find((item) => item.id === id);
}

export function indicatorCatalogId(key: IndicatorKey): string {
  return `indicator:${key}`;
}

export function layerCatalogId(key: ChartLayerKey): string {
  return `layer:${key}`;
}

export function patternCatalogId(key: PatternTypeKey): string {
  return `pattern:${key}`;
}
