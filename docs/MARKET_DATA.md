# Market data

The current Kraken deployment has two deliberately separate paths. REST OHLC collection
persists closed candles for authoritative calculations. The public WebSocket v2 feed relays
best-bid-offer ticker updates and forming OHLC candles through a backend-only port for GUI
presentation. `live-price.v1` is the Decimal midpoint between the reported best bid and ask;
it drives the watchlist and toolbar values. `live-candle.v1` drives only the forming chart bar,
and the browser rejects it unless its interval is newer than the latest persisted closed bar.
Both contracts carry `authoritative=false`, are not stored, and must never enter detection,
lifecycle, scoring, risk, recommendation, or execution code. Since Kraken OHLC updates are
trade-driven, the displayed BBO midpoint can change while a quiet market's forming chart bar
does not.

The research GUI centers on the three learner questions (context, location, confirmation).
Overlay toggles (liquidity, FVG, entry, stop, targets, patterns) control chart geometry only.
The six-signal checklist and shadow execution console stay collapsed under Signal detail /
Advanced. Human-readable labels are presentation metadata only.

Chart payloads include soft-label `patterns` computed on closed candles from confirmed pivots
(wedges, triangles, flags/pennants, double tops/bottoms). Patterns are optional location tags:
they never create entries, scores, risk approvals, or order intents. Hiding or showing a layer
never changes stored evidence, setup score, recommendation validity, risk, or execution state.
FVG and entry regions are rendered from stored lower/upper bounds; stop-loss and profit-target
prices remain exact lines because the backend does not define a price-width for those objects.

The workstation presents each strategy episode as a potential long or short idea. Chart
liquidity, imbalance, recommendation, stop, and target geometry is filtered to the focused
setup. Friendly state and reason labels are presentation-only; the API and database continue
to retain canonical lifecycle values for reproducibility.

The collector is public and read-only: it instantiates CCXT without credentials and exposes no order methods. OKX spot is the default because its public API supports the requested `BTC/USDT` and `ETH/USDT` history. Every row records exchange and source provenance. Funding and open interest use separate perpetual-contract symbols and are supplemental research inputs, never execution inputs.

## Seeding from legacy platform.db

The root `platform.db` SQLite file is a read-only archive (~508k candles for BTC/ETH/SOL). To bootstrap local PostgreSQL without a remote backfill:

```bash
docker compose up -d postgres
docker compose run --rm migrate
python scripts/import_platform_db.py
```

Then run `market-data run` for gap-fill and `relay-agent` to push snapshots to a Heroku relay deployment.

```bash
market-data backfill
market-data update
market-data candidates
```

`backfill` requests one year for each configured symbol/timeframe using advancing, idempotent pages. Only completed candles are stored. Re-running safely updates the same unique candle identities. `run` polls continuously and `/market-data/status` reports freshness. Start it locally with `market-data run --poll-seconds 30`, or with `docker compose up -d postgres platform-api market-data` after the initial backfill.

## Watchlist admission

The candidate command screens active USDT spot markets using primary exchange ticker evidence. It currently requires configured minimum 24-hour quote volume and maximum bid/ask spread. An `investigate` result is not automatic admission. Before adding a pair, collect at least 30 days of candles and review:

- missing-candle rate and timestamp continuity;
- median and adverse spread, not only one snapshot;
- quote volume persistence across several weeks;
- correlation and divergence usefulness relative to BTC and ETH;
- realized volatility and FVG/setup sample counts;
- exchange listing status and market-data stability.

Likely adjacent assets such as SOL, XRP, ADA, DOGE, LINK, and AVAX must earn admission from those measurements. This avoids hard-coding popularity as evidence.

## Database-backed watchlist

Assets have one of three states: `active` (collection plus setup evaluation), `probe` (collection only), or `disabled` (history retained, no collection). BTC/USDT and ETH/USDT are protected active anchors. The continuous collector reloads active and probe symbols from the database every poll cycle, so confirmed changes do not require a restart.

Telegram changes use a 15-minute confirmation token:

```text
/candidates
/candidate SOL/USDT
/watchlist probe SOL/USDT
/watchlist confirm ch_12345678
/watchlist add SOL/USDT
/watchlist remove SOL/USDT
/backfill SOL/USDT
```

The research GUI watchlist rail also supports symbol search and admission:

```text
GET  /api/v1/gui/watchlist/search?q=SOL
POST /api/v1/gui/watchlist/changes          # action: probe | add | remove
POST /api/v1/gui/watchlist/changes/{id}/confirm
```

Search queries the configured spot exchange markets (public CCXT) and falls back to local candidate/watchlist evidence if the exchange is unreachable. Results are USDT spot pairs only. Adding a symbol creates the same pending change + confirm flow as Telegram; probe confirmation queues the usual historical backfill.

Promotion from probe to active requires a current liquidity snapshot meeting volume/spread thresholds and at least 95% of the expected 30 days of hourly candles. Disabling preserves all historical research. Candidate ticker snapshots refresh hourly while the continuous collector runs.

Confirming a new probe automatically creates a persistent backfill job for every configured timeframe (currently `5m`, `15m`, `30m`, `1h`, `4h`, and `1d`). A background worker processes it alongside continuous polling and commits progress after every exchange page. Jobs retain the current timeframe, completed timeframes, processed row count, timestamps, and sanitized exception type. On collector restart, interrupted `running` jobs return to `pending` and resume idempotently.

An hourly history audit covers every active/probe asset and automatically queues newly configured or materially incomplete timeframes. A completed full-depth attempt counts as best available when an exchange or newly listed market cannot provide the entire requested range. Failed jobs cool down for one hour. `/backfill` lists all tracked assets, while the guided backfill menu can run the same audit immediately with `Sync missing history for all`.

For an already tracked active or probe asset, an operator may run:

```bash
market-data backfill-symbol SOL/USDT --days 365
market-data backfill-symbol SOL/USDT --days 30 --timeframes 1h
```

The command refuses untracked or disabled symbols, preventing a CLI backfill from silently changing watchlist status.

CCXT capability flags are checked at runtime. Funding and open interest are contract-only metrics and may be absent even when spot OHLCV is available. Failures are retried with bounded exponential backoff; persistent failures surface as errors rather than fabricated or silently positive data.
