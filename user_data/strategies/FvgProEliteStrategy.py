"""Thin Freqtrade adapter. Domain behavior lives under app/domain."""
from __future__ import annotations

from functools import reduce

import pandas as pd
from freqtrade.strategy import IStrategy, merge_informative_pair


class FvgProEliteStrategy(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "5m"
    can_short = False
    minimal_roi = {"0": 2.0}
    stoploss = -0.05
    process_only_new_candles = True
    startup_candle_count = 210
    use_exit_signal = True
    informative_timeframes = ("15m", "30m", "1h")

    def informative_pairs(self):
        return [(pair, tf) for pair in self.dp.current_whitelist() for tf in self.informative_timeframes]

    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        frames = []
        for tf in self.informative_timeframes:
            informative = self.dp.get_pair_dataframe(pair=metadata["pair"], timeframe=tf).copy()
            informative["ema_50"] = informative["close"].ewm(span=50, adjust=False).mean()
            dataframe = merge_informative_pair(dataframe, informative, self.timeframe, tf, ffill=True)
            frames.append(dataframe[f"close_{tf}"] > dataframe[f"ema_50_{tf}"])
        dataframe["htf_bull"] = reduce(lambda a, b: a & b, frames).fillna(False)

        # At candle i this reproduces Pine's low[1] > high[2] / high[1] < low[2].
        dataframe["new_bull_fvg"] = dataframe["low"].shift(1) > dataframe["high"].shift(2)
        dataframe["bull_fvg_lower"] = dataframe["high"].shift(2).where(dataframe["new_bull_fvg"]).ffill(limit=40)
        dataframe["bull_fvg_upper"] = dataframe["low"].shift(1).where(dataframe["new_bull_fvg"]).ffill(limit=40)
        dataframe["inside_bull_fvg"] = (dataframe["low"] <= dataframe["bull_fvg_upper"]) & (dataframe["high"] >= dataframe["bull_fvg_lower"])
        prior_low = dataframe["low"].shift(1).rolling(10).min()
        dataframe["sweep_low"] = (dataframe["low"] < prior_low) & (dataframe["close"] > prior_low)
        dataframe["bull_retest"] = dataframe["inside_bull_fvg"] & (dataframe["close"] > dataframe["open"]) & (dataframe["close"] > (dataframe["bull_fvg_lower"] + dataframe["bull_fvg_upper"]) / 2) & (dataframe["close"] > dataframe["close"].shift(1))
        dataframe["bull_structure"] = dataframe["close"] > dataframe["high"].shift(1).rolling(10).max()
        # SMT requires aligned informative comparison data and remains false until wired.
        dataframe["bull_smt"] = False
        dataframe["long_score"] = dataframe[["htf_bull", "sweep_low", "inside_bull_fvg", "bull_retest", "bull_smt", "bull_structure"]].sum(axis=1)
        return dataframe

    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        # Fail closed: platform-approved intents are not connected to Freqtrade yet.
        # This strategy must remain inert until the reviewed shadow-reconciliation gate passes.
        dataframe["enter_long"] = 0
        return dataframe

    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe.loc[dataframe["close"] < dataframe["bull_fvg_lower"], "exit_long"] = 1
        return dataframe
