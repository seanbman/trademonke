# Telegram

Freqtrade native Telegram remains the standard control plane and is disabled in the template until token/chat ID are supplied outside Git. Custom reporting is limited to setup explanations and future approval workflow. It must allowlist numeric user IDs, audit mutations, require confirmation for dangerous actions, redact credentials, and never enable live mode.

The custom long-polling service reads `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, and `PLATFORM_TELEGRAM_ALLOWED_USER_IDS` from `.env`. Start locally with `.venv/bin/telegram-bot` or `make telegram`. With Docker available, use `docker compose up -d postgres platform-api market-data telegram-bot`.

At startup the service registers its canonical command list through Telegram `setMyCommands`. Restarting the service automatically synchronizes the group slash-command menu with the implemented handlers; BotFather command-menu updates are unnecessary.

`/menu` opens a guided inline-keyboard interface. `/alerts menu`, `/indicators menu`, `/backfill menu`, and `/watchlist menu` jump directly to symbol buttons sourced from the persistent watchlist. Backfill and watchlist mutations produce explicit confirmation buttons containing the same expiring request IDs used by typed commands. Callback queries enforce both configured chat ID and individual user allowlist before dispatch.

The backfill menu displays every active/probe asset's latest job status and provides `Sync missing history for all`. The button invokes the configured-history audit and queues only missing timeframes, so it is safe to press repeatedly.

Only the configured group is accepted. Group membership alone does not authorize commands; the sender's numeric user ID must also be allowlisted. `/pause`, `/resume`, and confirmed `/kill` changes are persisted and written to the event audit table. `/kill` requires the exact command `/kill confirm`; it cannot be cleared from Telegram.

Authorized users are still rejected when messaging the bot privately because chat authorization and user authorization are independent. A routine long-poll `ReadTimeout` is retried automatically and logged as a warning; repeated HTTP failures or a lack of subsequent command responses require investigation.

HTTP transport logging is suppressed because Telegram embeds the bot token in request URLs. If a token appears in any screenshot, terminal log, or shared output, revoke it through BotFather before restarting the service.

Watchlist commands create pending database changes and require `/watchlist confirm CHANGE_ID` within 15 minutes. Probe assets collect research data but are not execution eligible. Promotion to active is rejected until the configured liquidity and 30-day data-coverage gates pass. BTC and ETH anchors cannot be removed through Telegram.

Probe confirmation queues its historical backfill automatically. `/backfill SYMBOL` reports pending, running, completed, or failed state; completed/total timeframes; page-level rows processed; current timeframe; sanitized error type; and job ID. `/candidate SYMBOL` includes the same summary when exchange evidence is available.

Existing active/probe symbols may request a customized job with `/backfill request SYMBOL [DAYS] [TF,TF]`; `/backfill confirm REQUEST_ID` must follow within 15 minutes. The request never changes watchlist state.

`/marketdata` labels timestamps as candle open → close, shows when the next completed candle is expected, and marks each stream `CURRENT` or `OVERDUE`. This avoids treating a daily candle's opening timestamp as data-feed latency.

`/indicators SYMBOL` displays the latest persisted long and short six-component snapshots. `/alerts enable|disable SYMBOL`, `/alerts component SYMBOL COMPONENT`, and `/alerts score SYMBOL 0-6` manage per-user group subscriptions. Alerts are closed-candle transitions, use deterministic deduplication IDs, and are delivered once. Historical events are not replayed when a subscription is enabled later.

Setup lifecycle transitions are opt-out and default to a 4/6 minimum for active and probe symbols. Lower-score near misses remain persisted without Telegram noise. The alert menu provides 2/6, 4/6, 5/6, and 6/6 threshold buttons; `/alerts score SYMBOL N` is the typed equivalent. The newest explicit `/alerts disable SYMBOL` suppresses the symbol and `/alerts enable SYMBOL` restores it. Terminal events retain the previously achieved score so qualifying setups still report later invalidation, expiry, or cancellation. Raw indicator-component transitions remain opt-in.

`/alerts` displays effective state for every active, probe, or disabled watchlist row. `setup=ON(default≥4)` means no explicit subscription was necessary; indicator filters remain `off` until enabled by that user.

`/setups` lists active research episodes. `/setup ID` displays the current component checklist and provenance, while `/why ID` explains passing/missing components, eligibility gates, and recent transition reasons. Setup transitions may generate subscribed group alerts, but all setup records explicitly remain disconnected from execution.

`/kill` must engage the platform kill switch immediately for new entries; it must not impede position-risk handling or exits. Telegram failure must never stop Freqtrade. Evidence should say, for example, “price wicked 0.34 ATR below the London low and closed back above,” never claim knowledge of participant intent.
