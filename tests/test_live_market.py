import asyncio
import json

from app.api.main import _forward_to_gui
from app.market_data.live import (
    LiveMarketRelay,
    normalize_ohlc_message,
    normalize_ticker_message,
)


def test_kraken_ohlc_normalization_keeps_latest_forming_candle_only():
    message = {
        "channel": "ohlc",
        "type": "snapshot",
        "timestamp": "2026-07-13T06:01:01Z",
        "data": [
            {"symbol": "BTC/USDT", "interval": 5, "interval_begin": "2026-07-13T05:55:00Z",
             "open": 100, "high": 102, "low": 99, "close": 101, "volume": 10},
            {"symbol": "BTC/USDT", "interval": 5, "interval_begin": "2026-07-13T06:00:00Z",
             "open": 101, "high": 103, "low": 100, "close": 102, "volume": 11},
        ],
    }

    result = normalize_ohlc_message(message)

    assert len(result) == 1
    assert result[0]["contract_version"] == "live-candle.v1"
    assert result[0]["authoritative"] is False
    assert result[0]["timeframe"] == "5m"
    assert result[0]["candle"] == {
        "timestamp": "2026-07-13T06:00:00Z", "open": "101", "high": "103",
        "low": "100", "close": "102", "volume": "11",
    }


def test_kraken_heartbeat_is_not_market_data():
    assert normalize_ohlc_message({"channel": "heartbeat"}) == []


def test_kraken_ticker_normalization_uses_decimal_bbo_midpoint():
    message = {
        "channel": "ticker",
        "type": "update",
        "data": [{
            "symbol": "ETH/USDT",
            "bid": "1776.51",
            "ask": "1776.63",
            "timestamp": "2026-07-13T06:01:01.123456Z",
        }],
    }

    assert normalize_ticker_message(message) == [{
        "contract_version": "live-price.v1",
        "type": "live_price",
        "exchange": "kraken",
        "symbol": "ETH/USDT",
        "observed_at": "2026-07-13T06:01:01.123456Z",
        "authoritative": False,
        "price_kind": "bbo_midpoint",
        "price": "1776.57",
        "bid": "1776.51",
        "ask": "1776.63",
    }]


def test_live_relay_broadcasts_normalized_contract():
    class Client:
        def __init__(self):
            self.messages = []

        async def send(self, message):
            self.messages.append(message)

    relay = LiveMarketRelay(("BTC/USDT",), ("5m",))
    client = Client()
    relay.clients.add(client)
    asyncio.run(relay.broadcast({"type": "live_candle"}))
    assert client.messages == ['{"type":"live_candle"}']


def test_live_relay_replays_cached_prices_to_new_clients():
    class Client:
        def __init__(self):
            self.messages = []

        async def send(self, message):
            self.messages.append(message)

        async def wait_closed(self):
            return None

    relay = LiveMarketRelay(("BTC/USDT", "ETH/USDT"), ("5m",))
    relay.latest[("BTC/USDT", "5m")] = {"symbol": "BTC/USDT", "type": "live_candle"}
    relay.latest[("ETH/USDT", "5m")] = {"symbol": "ETH/USDT", "type": "live_candle"}
    client = Client()

    asyncio.run(relay.client(client))

    assert len(client.messages) == 2
    assert {"BTC/USDT", "ETH/USDT"} == {
        json.loads(message)["symbol"] for message in client.messages}


def test_gui_receives_selected_candle_and_all_base_timeframe_prices():
    def candle(symbol, timeframe, authoritative=False):
        return {"contract_version": "live-candle.v1", "symbol": symbol,
                "timeframe": timeframe, "authoritative": authoritative}

    assert _forward_to_gui(candle("ETH/USDT", "5m"), "BTC/USDT", "4h", "5m")
    assert _forward_to_gui(candle("BTC/USDT", "4h"), "BTC/USDT", "4h", "5m")
    assert not _forward_to_gui(candle("ETH/USDT", "4h"), "BTC/USDT", "4h", "5m")
    assert not _forward_to_gui(candle("ETH/USDT", "5m", True), "BTC/USDT", "4h", "5m")
    assert _forward_to_gui(
        {"contract_version": "live-price.v1", "authoritative": False},
        "BTC/USDT", "4h", "5m")
    assert not _forward_to_gui(
        {"contract_version": "live-price.v1", "authoritative": True},
        "BTC/USDT", "4h", "5m")
