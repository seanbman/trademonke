# Research GUI

TradeMonke Lab is a dry-run research workstation. The primary reading path is:

1. Watchlist / idea rail (live ticking prices; historical candles load on the chart only)
2. Context · Location · Confirmation (three questions)
3. Chart with overlay toggles, drawing tools, and preset labels (LQ / BSL / SSL / BOS / CHoC / MSS)
4. Technical analysis summary (gates, open FVGs, measured invalidations, research geometry)
5. Optional pattern kit (soft-labels only; full formation span)
6. Collapsed signal detail and advanced operator tools

## Drawings and presets

Authenticated GUI routes manage annotations:

- `GET/POST /api/v1/gui/annotations`
- `DELETE /api/v1/gui/annotations/{id}`
- Chart payloads include `annotations[]`

Geometry uses Decimal-safe price strings and UTC unix candle anchors. Drawings never invent fills.

## Invalidation alerts

`POST /api/v1/gui/invalidations/evaluate` records measured events from annotation breaks,
liquidity sweeps/accepted breakouts, and structure breaks. List via
`GET /api/v1/gui/invalidations`. Copy describes measurements only (no institutional intent).

## TA summary

`GET /api/v1/gui/summary/{symbol}` returns a read-only stance (`watch` / `no_trade` /
`insufficient_evidence`) from six-component gates plus open liquidity/FVG evidence.

## Symbol search

The watchlist rail searches via `GET /api/v1/gui/watchlist/search?q=…`. Technique filters
require an explicit OK/Apply confirmation before they stick. Probe/promote/remove still
require the existing confirmation flow.

## Indicator guide

The workstation **Guide** control (and ⓘ buttons on confluence chips, overlays, and pattern
toggles) opens in-app pages for every scored component, chart layer, and soft-label pattern:
what it is, how it looks, how it is identified on closed candles, and how the GUI flags it.
Future concepts (order blocks, volume profile, ORB, footprint, oscillators) are listed as
*Not in workstation yet*.

## Patterns

`GET /api/v1/gui/chart/{symbol}` returns `patterns[]` from `app.domain.patterns.detect_patterns`.
Each item carries `soft_label=true` and `authority=none`. Pattern kit toggles only change what
is drawn. Rising/falling wedges are included. If a pattern’s direction hint disagrees with
higher-timeframe context, the Location strip prefers context.

## Safety

Live trading is prohibited. Shadow execution stays under Advanced and remains fail-closed when
dry-run submission is locked.
