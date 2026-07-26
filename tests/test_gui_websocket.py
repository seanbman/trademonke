import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.orm import sessionmaker

import app.api.main as api_main
from app.settings import Settings
from app.telemetry.db import Base, build_engine
from app.telemetry.models import CandleRecord, WatchlistAssetRecord


class FakeWebSocket:
    def __init__(self, subscription):
        self.subscription = subscription
        self.accepted = False
        self.closed = None
        self.sent = []

    async def accept(self):
        self.accepted = True

    async def receive_json(self):
        return self.subscription

    async def receive(self):
        return {"type": "websocket.disconnect"}

    async def close(self, code, reason):
        self.closed = (code, reason)

    async def send_json(self, message):
        self.sent.append(message)


def websocket_database(tmp_path):
    engine = build_engine(f"sqlite:///{tmp_path / 'websocket.db'}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    now = datetime.now(timezone.utc)
    with Session() as session:
        session.add(WatchlistAssetRecord(
            symbol="BTC/USDT", status="active", protected=True,
            created_at=now, updated_at=now, updated_by="test", reason="test"))
        session.add_all([
            CandleRecord(
                exchange="kraken", symbol="BTC/USDT", timeframe="5m",
                timestamp=now + timedelta(minutes=5),
                open=Decimal("100"), high=Decimal("102"), low=Decimal("99"),
                close=Decimal("101"), volume=Decimal("10"), source="test", closed=True),
            CandleRecord(
                exchange="kraken", symbol="BTC/USDT", timeframe="5m", timestamp=now,
                open=Decimal("101"), high=Decimal("103"), low=Decimal("100"),
                close=Decimal("102"), volume=Decimal("11"), source="test", closed=False),
        ])
        session.commit()
    return Session


def test_websocket_rejects_invalid_token(monkeypatch):
    settings = Settings(gui_access_token="correct-token")
    monkeypatch.setattr(api_main, "get_settings", lambda: settings)
    socket = FakeWebSocket({
        "type": "subscribe", "token": "wrong-token",
        "symbol": "BTC/USDT", "timeframe": "5m",
    })
    asyncio.run(api_main.gui_websocket(socket))
    assert socket.accepted is True
    assert socket.closed[0] == 1008
    assert socket.sent == []


def test_websocket_snapshot_contains_only_closed_candles(tmp_path, monkeypatch):
    Session = websocket_database(tmp_path)
    settings = Settings(gui_access_token="correct-token")
    monkeypatch.setattr(api_main, "SessionLocal", Session)
    monkeypatch.setattr(api_main, "get_settings", lambda: settings)

    async def run_in_process(function, *args):
        return function(*args)

    monkeypatch.setattr(api_main.asyncio, "to_thread", run_in_process)
    socket = FakeWebSocket({
        "type": "subscribe", "token": "correct-token",
        "symbol": "BTC/USDT", "timeframe": "5m",
    })
    asyncio.run(api_main.gui_websocket(socket))
    message = socket.sent[0]

    assert message["contract_version"] == "workstation.v1"
    assert message["type"] == "snapshot"
    assert message["data"]["chart"]["symbol"] == "BTC/USDT"
    assert [item["close"] for item in message["data"]["chart"]["candles"]] == ["101.000000000000000000"]


def test_snapshot_fingerprint_ignores_generation_time():
    first = {"bootstrap": {"generated_at": "first", "watchlist": []}, "chart": {}}
    second = {"bootstrap": {"generated_at": "second", "watchlist": []}, "chart": {}}
    assert api_main._snapshot_fingerprint(first) == api_main._snapshot_fingerprint(second)
