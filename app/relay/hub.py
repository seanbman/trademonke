from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.relay.cache import RelayCache


@dataclass
class GuiSubscription:
    websocket: Any
    symbol: str
    timeframe: str


class RelayHub:
    def __init__(self, cache: RelayCache | None = None):
        self.cache = cache or RelayCache()
        self.gui_clients: list[GuiSubscription] = []
        self._lock = asyncio.Lock()

    async def set_feeder_connected(self, connected: bool) -> None:
        async with self._lock:
            self.cache.feeder_connected = connected
            if connected:
                self.cache.feeder_last_seen = datetime.now(timezone.utc)

    async def ingest(self, message: dict[str, Any]) -> None:
        async with self._lock:
            self.cache.feeder_last_seen = datetime.now(timezone.utc)
        contract = message.get("contract_version")
        if contract == "workstation.v1" and message.get("type") == "snapshot":
            data = message.get("data") or {}
            chart = data.get("chart") or {}
            symbol = chart.get("symbol")
            timeframe = chart.get("timeframe")
            generated_at = message.get("generated_at")
            if not isinstance(symbol, str) or not isinstance(timeframe, str):
                return
            observed = datetime.fromisoformat(generated_at) if isinstance(generated_at, str) else datetime.now(timezone.utc)
            if observed.tzinfo is None:
                observed = observed.replace(tzinfo=timezone.utc)
            fingerprint = str(message.get("fingerprint", ""))
            async with self._lock:
                self.cache.store_snapshot(symbol, timeframe, observed, data, fingerprint)
            await self._broadcast_snapshot(symbol, timeframe, message)
            return
        if contract in {"live-price.v1", "live-candle.v1", "market-stream-status.v1", "feeder-status.v1"}:
            async with self._lock:
                if contract not in {"market-stream-status.v1", "feeder-status.v1"}:
                    self.cache.store_live(message)
            if contract != "feeder-status.v1":
                await self._broadcast_live(message)
            return

    async def register_gui(self, subscription: GuiSubscription) -> None:
        async with self._lock:
            self.gui_clients.append(subscription)

    async def unregister_gui(self, subscription: GuiSubscription) -> None:
        async with self._lock:
            self.gui_clients = [item for item in self.gui_clients if item is not subscription]

    async def _broadcast_snapshot(self, symbol: str, timeframe: str, message: dict[str, Any]) -> None:
        clients = [item for item in self.gui_clients
                   if item.symbol == symbol and item.timeframe == timeframe]
        for client in clients:
            await client.websocket.send_json(message)

    async def _broadcast_live(self, message: dict[str, Any]) -> None:
        symbol = message.get("symbol")
        for client in list(self.gui_clients):
            if message.get("contract_version") == "live-price.v1":
                await client.websocket.send_json(message)
            elif (message.get("contract_version") == "live-candle.v1" and
                  symbol == client.symbol and message.get("timeframe") == client.timeframe):
                await client.websocket.send_json(message)
            elif message.get("contract_version") == "market-stream-status.v1":
                await client.websocket.send_json(message)

    def feeder_status_message(self) -> dict[str, Any]:
        status = self.cache.feeder_status()
        return {
            "contract_version": "feeder-status.v1",
            "type": "feeder_status",
            "status": status,
            "observed_at": datetime.now(timezone.utc).isoformat(),
        }


relay_hub = RelayHub()
