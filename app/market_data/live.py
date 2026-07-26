from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import websockets
from websockets.asyncio.server import ServerConnection


KRAKEN_WS_V2 = "wss://ws.kraken.com/v2"
TIMEFRAME_MINUTES = {
    "1m": 1,
    "5m": 5,
    "15m": 15,
    "30m": 30,
    "1h": 60,
    "4h": 240,
    "1d": 1440,
    "1w": 10080,
}
MINUTES_TIMEFRAME = {minutes: timeframe for timeframe, minutes in TIMEFRAME_MINUTES.items()}


def normalize_ohlc_message(message: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert Kraken forming candles into a presentation-only contract."""
    if message.get("channel") != "ohlc" or message.get("type") not in {"snapshot", "update"}:
        return []
    observed_at = message.get("timestamp") or datetime.now(timezone.utc).isoformat()
    latest: dict[tuple[str, str], dict[str, Any]] = {}
    for item in message.get("data", []):
        timeframe = MINUTES_TIMEFRAME.get(item.get("interval"))
        if timeframe is None or not item.get("symbol") or not item.get("interval_begin"):
            continue
        normalized = {
            "contract_version": "live-candle.v1",
            "type": "live_candle",
            "exchange": "kraken",
            "symbol": item["symbol"],
            "timeframe": timeframe,
            "observed_at": observed_at,
            "authoritative": False,
            "candle": {
                "timestamp": item["interval_begin"],
                "open": str(item["open"]),
                "high": str(item["high"]),
                "low": str(item["low"]),
                "close": str(item["close"]),
                "volume": str(item["volume"]),
            },
        }
        key = (item["symbol"], timeframe)
        if key not in latest or normalized["candle"]["timestamp"] > latest[key]["candle"]["timestamp"]:
            latest[key] = normalized
    return list(latest.values())


def normalize_ticker_message(message: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert Kraken BBO updates into non-authoritative midpoint prices."""
    if message.get("channel") != "ticker" or message.get("type") not in {"snapshot", "update"}:
        return []
    normalized = []
    for item in message.get("data", []):
        if not item.get("symbol") or item.get("bid") is None or item.get("ask") is None:
            continue
        bid, ask = Decimal(str(item["bid"])), Decimal(str(item["ask"]))
        midpoint = (bid + ask) / Decimal("2")
        normalized.append({
            "contract_version": "live-price.v1",
            "type": "live_price",
            "exchange": "kraken",
            "symbol": item["symbol"],
            "observed_at": item.get("timestamp") or datetime.now(timezone.utc).isoformat(),
            "authoritative": False,
            "price_kind": "bbo_midpoint",
            "price": format(midpoint, "f"),
            "bid": format(bid, "f"),
            "ask": format(ask, "f"),
        })
    return normalized


class LiveMarketRelay:
    """Relay Kraken public BBO and OHLC updates to backend-only clients."""

    def __init__(self, symbols: tuple[str, ...], timeframes: tuple[str, ...],
                 host: str = "0.0.0.0", port: int = 8100,
                 upstream_url: str = KRAKEN_WS_V2):
        self.symbols = symbols
        self.intervals = tuple(
            TIMEFRAME_MINUTES[item] for item in timeframes if item in TIMEFRAME_MINUTES)
        self.host = host
        self.port = port
        self.upstream_url = upstream_url
        self.clients: set[ServerConnection] = set()
        self.latest: dict[tuple[str, str], dict[str, Any]] = {}

    async def client(self, websocket: ServerConnection) -> None:
        self.clients.add(websocket)
        try:
            for message in self.latest.values():
                await websocket.send(json.dumps(message, separators=(",", ":")))
            await websocket.wait_closed()
        finally:
            self.clients.discard(websocket)

    async def broadcast(self, message: dict[str, Any]) -> None:
        if not self.clients:
            return
        encoded = json.dumps(message, separators=(",", ":"))
        clients = tuple(self.clients)
        results = await asyncio.gather(
            *(client.send(encoded) for client in clients),
            return_exceptions=True,
        )
        for client, result in zip(clients, results, strict=True):
            if isinstance(result, Exception):
                self.clients.discard(client)

    async def consume_upstream(self) -> None:
        async with websockets.connect(self.upstream_url, ping_interval=20, ping_timeout=20) as upstream:
            await upstream.send(json.dumps({
                "method": "subscribe",
                "params": {
                    "channel": "ticker",
                    "symbol": list(self.symbols),
                    "event_trigger": "bbo",
                    "snapshot": True,
                },
                "req_id": 1000,
            }))
            for request_id, interval in enumerate(self.intervals, start=1):
                await upstream.send(json.dumps({
                    "method": "subscribe",
                    "params": {
                        "channel": "ohlc",
                        "symbol": list(self.symbols),
                        "interval": interval,
                        "snapshot": True,
                    },
                    "req_id": request_id,
                }))
            async for raw in upstream:
                message = json.loads(raw)
                updates = [*normalize_ticker_message(message), *normalize_ohlc_message(message)]
                for update in updates:
                    cache_key = update.get("timeframe", "price")
                    self.latest[(update["symbol"], cache_key)] = update
                    await self.broadcast(update)

    async def upstream_forever(self) -> None:
        delay = 1
        while True:
            try:
                await self.consume_upstream()
                delay = 1
            except asyncio.CancelledError:
                raise
            except Exception:
                await asyncio.sleep(delay)
                delay = min(delay * 2, 30)

    async def run_forever(self) -> None:
        async with websockets.serve(self.client, self.host, self.port):
            await self.upstream_forever()
