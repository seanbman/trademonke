from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone

import websockets
from websockets.asyncio.client import ClientConnection

from app.api import main as api_main
from app.api.workstation import build_workstation_snapshot, snapshot_fingerprint
from app.settings import Settings, get_settings
from app.telemetry.db import SessionLocal
from app.market_data.watchlist import collection_symbols


def _workstation_snapshot(symbol: str, timeframe: str, settings: Settings) -> dict:
    with SessionLocal() as session:
        return build_workstation_snapshot(
            symbol, timeframe, settings, session,
            bootstrap_builder=lambda active_session: api_main._gui_bootstrap_data(active_session, settings),
            chart_builder=api_main.gui_chart,
            health_builder=api_main.health,
            alerts_builder=api_main.gui_alerts,
            execution_builder=api_main.gui_execution,
        )


async def _push_snapshot(remote: ClientConnection, symbol: str, timeframe: str,
                         settings: Settings, last_fingerprints: dict[tuple[str, str], str]) -> None:
    payload = await asyncio.to_thread(_workstation_snapshot, symbol, timeframe, settings)
    fingerprint = snapshot_fingerprint(payload)
    key = (symbol, timeframe)
    if fingerprint == last_fingerprints.get(key):
        return
    last_fingerprints[key] = fingerprint
    await remote.send(json.dumps({
        "contract_version": "workstation.v1",
        "type": "snapshot",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "fingerprint": fingerprint,
        "data": payload,
    }, separators=(",", ":")))


async def run(settings: Settings, poll_seconds: int, timeframe: str) -> None:
    if not settings.remote_relay_url or not settings.feeder_token:
        raise SystemExit("PLATFORM_REMOTE_RELAY_URL and PLATFORM_FEEDER_TOKEN are required")
    last_fingerprints: dict[tuple[str, str], str] = {}
    delay = 1
    while True:
        try:
            async with websockets.connect(
                    settings.remote_relay_url, open_timeout=10,
                    ping_interval=20, ping_timeout=20) as remote:
                await remote.send(json.dumps({
                    "type": "authenticate",
                    "token": settings.feeder_token,
                }))
                await remote.send(json.dumps({
                    "contract_version": "market-stream-status.v1",
                    "type": "market_status",
                    "status": "connected",
                    "observed_at": datetime.now(timezone.utc).isoformat(),
                }))
                market_task = asyncio.create_task(_forward_live_market(remote, settings))
                try:
                    heartbeat = asyncio.create_task(_relay_heartbeat(remote))
                    try:
                        while True:
                            with SessionLocal() as session:
                                symbols = collection_symbols(session)
                            for symbol in symbols:
                                await _push_snapshot(remote, symbol, timeframe, settings, last_fingerprints)
                            await asyncio.sleep(poll_seconds)
                    finally:
                        heartbeat.cancel()
                        await asyncio.gather(heartbeat, return_exceptions=True)
                finally:
                    market_task.cancel()
                    await asyncio.gather(market_task, return_exceptions=True)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print(f"relay-agent: connection error: {exc!r}", flush=True)
            await asyncio.sleep(delay)
            delay = min(delay * 2, 30)


async def _relay_heartbeat(remote: ClientConnection) -> None:
    while True:
        await remote.send(json.dumps({
            "contract_version": "feeder-status.v1",
            "type": "feeder_status",
            "status": "live",
            "observed_at": datetime.now(timezone.utc).isoformat(),
        }, separators=(",", ":")))
        await asyncio.sleep(15)


async def _forward_live_market(remote: ClientConnection, settings: Settings) -> None:
    async with websockets.connect(
            settings.market_stream_url, open_timeout=5, ping_interval=20, ping_timeout=20) as market:
        while True:
            raw = await market.recv()
            if isinstance(raw, bytes):
                raw = raw.decode()
            message = json.loads(raw)
            await remote.send(json.dumps(message, separators=(",", ":")))


def main() -> None:
    parser = argparse.ArgumentParser(description="Push local workstation snapshots to remote relay")
    parser.add_argument("--poll-seconds", type=int, default=5)
    parser.add_argument("--timeframe", default="5m")
    args = parser.parse_args()
    asyncio.run(run(get_settings(), args.poll_seconds, args.timeframe))


if __name__ == "__main__":
    main()
