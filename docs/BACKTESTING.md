# Backtesting and research

Download data using Freqtrade, define non-overlapping development, validation, and untouched test periods, and run `scripts/backtest.sh YYYYMMDD-YYYYMMDD`. The example Kraken taker fee is explicitly passed as 0.26%; confirm current exchange fees before relying on results.

Before Hyperopt: pass unit tests, reconcile Pine behavior, run a baseline backtest, then run Freqtrade `lookahead-analysis` and `recursive-analysis`. Evaluate slippage sensitivity, simple EMA/buy-and-hold baselines, walk-forward windows, and report by pair, timeframe, score, regime, and component ablation. Warn on small samples. Never tune on the untouched test period or blend immediate and sniper entry outcomes.

The platform research command creates deterministic chronological development, validation, and untouched-test manifests from persisted decision-time features and outcomes. The untouched IDs and dataset hash are stored before evaluation. Walk-forward and ablation reports must use development plus validation only; formal untouched-test evaluation is a separate reviewed action. A completed run manifest is reproducibility evidence, not evidence of positive expectancy when the sample is empty or small.

Shadow intent generation remains blocked until a baseline manifest has been independently marked reviewed. Shadow events never submit orders and must be reconciled against contemporaneous spread, slippage, minimums, and would-fill observations. Dry-run submission remains code-locked until the shadow review gate is added and passed; changing an environment variable alone cannot bypass it.
