# Strategy specification

## Reference decisions and conflicts

The available Pine reference is v6.2, while the brief asks for v6.3. The v6.2 behavior is implemented where unambiguous and the missing v6.3 is a known limitation. The handwritten notes contain discretionary and unsafe statements (including “go all in”); these are rejected in favor of conservative configurable controls.

The six-component FVG model and the supplementary IFVG institutional sequence are related but distinct. Phase one implements the six deterministic primitives. IFVG, V-recovery, signal tiers, Fibonacci sniper reactions, session liquidity, and target boxes remain research modules for the next phase; they must not be silently blended into execution results.

## Exact FVG indexing

For current closed candle index `i`, Pine v6.2 says bullish `low[1] > high[2]` and bearish `high[1] < low[2]`. Thus:

- Bullish zone is `[high(i-2), low(i-1)]`; creation candle/timestamp is `i-1`, but it is detected at `i`.
- Bearish zone is `[high(i-1), low(i-2)]`; creation candle/timestamp is `i-1`, detected at `i`.
- Any range overlap is a retest. A long invalidates on close below the lower boundary; short mirrors above the upper boundary. Expiry occurs when age is strictly greater than `max_age`.
- Confirmation matches Pine v6.2: directional candle, close past the midpoint, and close past the prior close.

## Other objective rules

- Pivot: strict high/low against configurable left and right neighbors. Equality is not a pivot.
- Sweep: wick strictly beyond a confirmed level and close strictly back inside. A close beyond is continuation/acceptance context, not a reversal sweep.
- Structure break: candle close strictly beyond the extreme of the supplied completed lookback. A wick-only cross fails.
- SMT: primary creates a new lookback extreme while aligned comparison does not. Missing data is false with `data_quality=missing`.
- HTF bias: all configured close/EMA pairs must align. The Pine reference uses 15m, 30m, and 1h. Platform research defaults extend this with 4h and 1d using EMA 50; these additions are explicitly configuration, not claimed Pine parity.
- Score: six auditable booleans, one point each; 0–3 developing, 4 watch, 5 strong watch, 6 eligible. Component weights are stored for later research.
- Stops: one tick beyond FVG or ATR buffer beyond sweep extreme. Targets must be on the correct side and meet minimum 2R.

No component asserts institutional intent; reports describe measured price behavior only.

The research engine exposes base timeframe, HTF list, EMA length, structure lookback, SMT lookback, pivot lookback, FVG maximum age, setup detection score, and setup expiry through `PLATFORM_...` environment settings. Market-data timeframes must contain the configured base and HTF set. Parameter changes apply prospectively and must be accompanied by relevant historical backfills and a new strategy version for formal comparative research.

Persistent liquidity levels use strictly confirmed pivots with configurable left/right closed-candle windows. Nearby same-side pivots may form an equal-level cluster within the configured basis-point tolerance. Touch, wick-through-and-reclaim sweep, close-beyond accepted breakout, and maximum-age expiry are separate append-only observations. No label asserts institutional intent.

An episode may become armed only after all six mandatory gates currently pass with valid data quality. Gate evidence is stored independently from contextual ranking. Risk then validates directional geometry, reward-to-risk, execution costs, control state, notional constraints, and Decimal position sizing. Neither score nor contextual evidence may override a failed mandatory gate or risk rejection.

The linked imbalance must have a formation timestamp at or after the episode displacement and becomes observable only on a later completed candle. The research pipeline is idempotent per episode/candle and automatically persists features, gates, risk, recommendations and later outcomes. Same-candle target/stop ambiguity is labelled stop-first.
