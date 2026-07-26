import asyncio
from datetime import datetime, timezone

import app.api.main as api_main
from app.relay.hub import relay_hub
from app.settings import Settings


class RelaySocket:
    def __init__(self, auth_token: str, messages: list[dict]):
        self.auth_token = auth_token
        self.messages = list(messages)
        self.accepted = False
        self.closed = None
        self.sent: list[dict] = []
        self._auth_sent = False

    async def accept(self):
        self.accepted = True

    async def receive_json(self):
        if not self._auth_sent:
            self._auth_sent = True
            return {"type": "authenticate", "token": self.auth_token}
        if self.messages:
            return self.messages.pop(0)
        await asyncio.sleep(3600)
        raise asyncio.CancelledError

    async def close(self, code, reason):
        self.closed = (code, reason)


class GuiRelaySocket:
    def __init__(self, subscription: dict):
        self.subscription = subscription
        self.accepted = False
        self.closed = None
        self.sent: list[dict] = []

    async def accept(self):
        self.accepted = True

    async def receive_json(self):
        return self.subscription

    async def receive(self):
        raise asyncio.TimeoutError

    async def close(self, code, reason):
        self.closed = (code, reason)

    async def send_json(self, message):
        self.sent.append(message)


def test_relay_websocket_rejects_invalid_feeder_token(monkeypatch):
    relay_hub.cache.snapshots.clear()
    settings = Settings(feeder_token="feeder-secret", platform_mode="relay")
    monkeypatch.setattr(api_main, "get_settings", lambda: settings)
    socket = RelaySocket("wrong-token", [])
    asyncio.run(api_main.relay_websocket(socket))
    assert socket.closed == (1008, "valid feeder token required")


def test_relay_websocket_ingests_snapshot(monkeypatch):
    relay_hub.cache.snapshots.clear()
    settings = Settings(feeder_token="feeder-secret", platform_mode="relay")
    monkeypatch.setattr(api_main, "get_settings", lambda: settings)
    snapshot = {
        "contract_version": "workstation.v1",
        "type": "snapshot",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "fingerprint": "abc",
        "data": {
            "chart": {"symbol": "BTC/USDT", "timeframe": "5m", "candles": []},
            "bootstrap": {"watchlist": []},
        },
    }

    class IngestSocket:
        def __init__(self):
            self.accepted = False
            self.closed = None
            self.step = 0

        async def accept(self):
            self.accepted = True

        async def receive_json(self):
            if self.step == 0:
                self.step = 1
                return {"type": "authenticate", "token": "feeder-secret"}
            if self.step == 1:
                self.step = 2
                return snapshot
            await asyncio.sleep(3600)

        async def close(self, code, reason):
            self.closed = (code, reason)

    async def run_once():
        socket = IngestSocket()
        task = asyncio.create_task(api_main.relay_websocket(socket))
        await asyncio.sleep(0.05)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    asyncio.run(run_once())
    cached = relay_hub.cache.get_snapshot("BTC/USDT", "5m")
    assert cached is not None
    assert cached.fingerprint == "abc"


def test_gui_websocket_relay_serves_cached_snapshot(monkeypatch):
    relay_hub.cache.snapshots.clear()
    now = datetime.now(timezone.utc)
    relay_hub.cache.store_snapshot(
        "BTC/USDT", "5m", now,
        {
            "bootstrap": {"watchlist": [{"symbol": "BTC/USDT", "status": "active", "protected": True}]},
            "chart": {
                "symbol": "BTC/USDT", "timeframe": "5m",
                "candles": [{"timestamp": now.isoformat(), "open": "1", "high": "2", "low": "1", "close": "2"}],
                "episodes": [{"id": "ep-1"}], "recommendations": [], "liquidity_levels": [],
                "imbalances": [], "indicator_snapshots": [],
            },
            "health": {"status": "healthy"},
            "alerts": [],
            "execution": {"mode": "disabled"},
        },
        "fp",
    )
    settings = Settings(
        gui_access_token="gui-secret",
        platform_mode="relay",
        relay_cache_hours=24,
    )
    monkeypatch.setattr(api_main, "get_settings", lambda: settings)

    async def run_once():
        socket = GuiRelaySocket({
            "type": "subscribe", "token": "gui-secret",
            "symbol": "BTC/USDT", "timeframe": "5m",
        })
        await api_main._send_relay_snapshot(socket, "BTC/USDT", "5m", settings)
        return socket

    socket = asyncio.run(run_once())
    feeder_messages = [item for item in socket.sent if item.get("type") == "feeder_status"]
    snapshot_messages = [item for item in socket.sent if item.get("type") == "snapshot"]
    assert feeder_messages
    assert feeder_messages[0]["status"] == "cached"
    assert snapshot_messages
    assert snapshot_messages[0]["data"]["chart"]["episodes"] == []
