# Roadmap

Completed foundation: public market collection/backfill, dynamic probe watchlist, six-component closed-candle snapshots, transition alerts, and research-only setup lifecycles with `/setup` and `/why` explanations.

Queued subsequent increments, in order:

1. Validate v6.2 primitives and setup transitions against TradingView exports; obtain the requested v6.3 source and resolve differences explicitly.
2. ~~Implement persistent liquidity-level lifecycles…~~ Partially complete: CHoCH/MSS/BOS labels, order/rejection blocks, IFVG/V-recovery research streams, kill-zone + premium/discount measurements, and research-only confluence scorecard are in domain modules (not execution authority).
3. Build reproducible baseline backtests, lookahead/recursive analysis, component ablations, walk-forward validation, and an untouched test period.
4. Wire validated setup eligibility into Freqtrade dry-run only, including mirrored spot exits, risk callbacks, and persistent trade linkage. Live execution remains a separately reviewed future decision.
5. Add A/A+/A++ analytical streams, independent immediate/Fib-sniper models, target boxes, session-aware draws on liquidity, and outcome attribution (tier labels now research-only on the scorecard).
6. Install local service supervision through Docker Compose or systemd so PostgreSQL, API, collector, Telegram, and Freqtrade dry-run recover after reboot.
7. Expand authenticated FastAPI setup/indicator/watchlist endpoints for the future GUI without exposing internal Freqtrade storage.
