import argparse
import asyncio
import json

import websockets

from app.settings import get_settings


async def verify(url: str, symbol: str, timeframe: str, timeout: int,
                 required_symbols: set[str], candle_updates: int,
                 price_updates: int) -> None:
    settings = get_settings()
    if not settings.gui_access_token:
        raise SystemExit("PLATFORM_GUI_ACCESS_TOKEN is required")
    async with websockets.connect(url, open_timeout=10) as socket:
        await socket.send(json.dumps({
            "type": "subscribe",
            "token": settings.gui_access_token,
            "symbol": symbol,
            "timeframe": timeframe,
        }))
        snapshot = None
        live = None
        selected_updates = []
        live_prices = {}
        observed_price_updates = 0
        message_counts = {}
        try:
            async with asyncio.timeout(timeout):
                while (snapshot is None or len(selected_updates) < candle_updates or
                       not required_symbols.issubset(live_prices) or
                       observed_price_updates < price_updates):
                    message = json.loads(await socket.recv())
                    message_type = message.get("type", "unknown")
                    message_counts[message_type] = message_counts.get(message_type, 0) + 1
                    if message_type == "snapshot":
                        snapshot = message
                    elif message_type == "live_price":
                        live_prices[message["symbol"]] = message["price"]
                        observed_price_updates += 1
                    elif message_type == "live_candle":
                        if message["symbol"] == symbol and message["timeframe"] == timeframe:
                            live = message
                            selected_updates.append(message["candle"])
        except TimeoutError as exc:
            diagnostic = {
                "message_counts": message_counts,
                "snapshot_received": snapshot is not None,
                "selected_candle_updates": len(selected_updates),
                "bbo_midpoint_prices": live_prices,
                "missing_price_symbols": sorted(required_symbols - live_prices.keys()),
            }
            raise SystemExit(f"WebSocket verification timed out: {json.dumps(diagnostic)}") from exc
    chart = snapshot["data"]["chart"]
    candles = chart["candles"]
    indicator_snapshots = chart.get("indicator_snapshots", [])
    print(json.dumps({
        "snapshot_contract": snapshot["contract_version"],
        "live_contract": live["contract_version"],
        "symbol": chart["symbol"],
        "timeframe": chart["timeframe"],
        "closed_candles": len(candles),
        "latest_closed_candle": candles[-1]["timestamp"] if candles else None,
        "forming_candle": live["candle"]["timestamp"],
        "live_close": live["candle"]["close"],
        "selected_updates": len(selected_updates),
        "first_live_close": selected_updates[0]["close"],
        "last_live_close": selected_updates[-1]["close"],
        "bbo_midpoint_prices": live_prices,
        "price_updates": observed_price_updates,
        "indicator_directions": [item["direction"] for item in indicator_snapshots],
        "indicator_scores": {
            item["direction"]: item["score"] for item in indicator_snapshots},
        "authoritative": live["authoritative"],
    }))


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify the authenticated GUI WebSocket")
    parser.add_argument("--url", default="ws://127.0.0.1:3000/api/v1/gui/ws")
    parser.add_argument("--symbol", default="BTC/USDT")
    parser.add_argument("--timeframe", default="5m")
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--require-symbols", default="")
    parser.add_argument("--updates", type=int, default=1)
    parser.add_argument("--price-updates", type=int, default=1)
    args = parser.parse_args()
    required_symbols = {item.strip() for item in args.require_symbols.split(",") if item.strip()}
    asyncio.run(verify(
        args.url, args.symbol, args.timeframe, args.timeout, required_symbols,
        max(1, args.updates), max(1, args.price_updates)))


if __name__ == "__main__":
    main()
