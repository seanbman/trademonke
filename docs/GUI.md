# Research GUI

TradeMonke Lab is a dry-run research workstation. The primary reading path is:

1. Watchlist / idea rail  
2. Context · Location · Confirmation (three questions)  
3. Chart with overlay toggles  
4. Optional pattern kit (soft-labels only)  
5. Collapsed signal detail and advanced operator tools  

## Symbol search

The watchlist rail searches via `GET /api/v1/gui/watchlist/search?q=…`. Suggestions include a
display name, USDT-spot subtitle, and a public ticker price (BBO midpoint when available).
Probe/promote/remove still require the existing confirmation flow.

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
