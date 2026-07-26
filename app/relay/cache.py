from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any


@dataclass
class CachedSnapshot:
    symbol: str
    timeframe: str
    generated_at: datetime
    payload: dict[str, Any]
    fingerprint: str


@dataclass
class RelayCache:
    ttl: timedelta = field(default_factory=lambda: timedelta(hours=24))
    snapshots: dict[tuple[str, str], CachedSnapshot] = field(default_factory=dict)
    live_frames: dict[tuple[str, str], dict[str, Any]] = field(default_factory=dict)
    feeder_connected: bool = False
    feeder_last_seen: datetime | None = None

    def prune(self, now: datetime | None = None) -> None:
        now = now or datetime.now(timezone.utc)
        expired = [
            key for key, item in self.snapshots.items()
            if now - item.generated_at > self.ttl
        ]
        for key in expired:
            self.snapshots.pop(key, None)
            self.live_frames.pop(key, None)

    def store_snapshot(self, symbol: str, timeframe: str, generated_at: datetime,
                       payload: dict[str, Any], fingerprint: str) -> None:
        self.snapshots[(symbol, timeframe)] = CachedSnapshot(
            symbol, timeframe, generated_at, payload, fingerprint)
        self.feeder_last_seen = generated_at
        self.prune(generated_at)

    def store_live(self, message: dict[str, Any]) -> None:
        symbol = message.get("symbol")
        timeframe = message.get("timeframe", "price")
        if isinstance(symbol, str):
            self.live_frames[(symbol, timeframe)] = message
            self.feeder_last_seen = datetime.now(timezone.utc)

    def get_snapshot(self, symbol: str, timeframe: str,
                     now: datetime | None = None) -> CachedSnapshot | None:
        self.prune(now)
        return self.snapshots.get((symbol, timeframe))

    def feeder_status(self, now: datetime | None = None) -> str:
        now = now or datetime.now(timezone.utc)
        if self.feeder_connected:
            return "live"
        if self.snapshots:
            newest = max(item.generated_at for item in self.snapshots.values())
            if now - newest <= self.ttl:
                return "cached"
        return "offline"
