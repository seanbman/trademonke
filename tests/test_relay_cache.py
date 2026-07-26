import asyncio
from datetime import datetime, timedelta, timezone

from app.settings import Settings
from app.relay.cache import RelayCache
from app.relay.hub import GuiSubscription, RelayHub
from app.relay.workstation import truncate_chart_for_cache


def test_relay_cache_prunes_expired_snapshots():
    cache = RelayCache(ttl=timedelta(hours=24))
    now = datetime(2026, 7, 14, 12, tzinfo=timezone.utc)
    cache.store_snapshot(
        "BTC/USDT", "5m", now - timedelta(hours=25),
        {"chart": {"symbol": "BTC/USDT", "timeframe": "5m", "candles": []}}, "old",
    )
    cache.store_snapshot(
        "ETH/USDT", "5m", now - timedelta(hours=1),
        {"chart": {"symbol": "ETH/USDT", "timeframe": "5m", "candles": []}}, "new",
    )
    cache.prune(now)
    assert ("BTC/USDT", "5m") not in cache.snapshots
    assert ("ETH/USDT", "5m") in cache.snapshots


def test_gui_subscription_registration():
    hub = RelayHub()
    subscription = GuiSubscription(websocket=object(), symbol="BTC/USDT", timeframe="5m")
    asyncio.run(hub.register_gui(subscription))
    assert hub.gui_clients == [subscription]
    asyncio.run(hub.unregister_gui(subscription))
    assert hub.gui_clients == []


def test_feeder_status_live_cached_offline():
    cache = RelayCache(ttl=timedelta(hours=24))
    now = datetime(2026, 7, 14, 12, tzinfo=timezone.utc)
    assert cache.feeder_status(now) == "offline"

    cache.feeder_connected = True
    cache.feeder_last_seen = now - timedelta(hours=1)
    assert cache.feeder_status(now) == "live"

    cache.feeder_connected = False
    cache.store_snapshot(
        "BTC/USDT", "5m", now - timedelta(hours=2),
        {"chart": {"symbol": "BTC/USDT", "timeframe": "5m"}}, "fp",
    )
    assert cache.feeder_status(now) == "cached"

    cache.snapshots.clear()
    assert cache.feeder_status(now) == "offline"


def test_relay_episode_events_from_cache(monkeypatch):
    import app.api.main as api_main
    from app.relay.hub import relay_hub

    relay_hub.cache.snapshots.clear()
    now = datetime.now(timezone.utc)
    relay_hub.cache.store_snapshot(
        "BTC/USDT", "5m", now,
        {
            "episode_events": {
                "ep_1": [{"event_id": "e1", "episode_id": "ep_1", "occurred_at": now.isoformat(),
                          "current_state": "swept", "reason_codes": ["level_crossed"]}],
            },
        },
        "fp",
    )
    settings = Settings(platform_mode="relay")
    monkeypatch.setattr(api_main, "get_settings", lambda: settings)
    result = api_main.episode_events("ep_1", session=object(), settings=settings)
    assert len(result) == 1
    assert result[0]["event_id"] == "e1"


def test_truncate_chart_for_cache_keeps_recent_candles_only():
    now = datetime(2026, 7, 14, 12, tzinfo=timezone.utc)
    chart = {
        "candles": [
            {"timestamp": (now - timedelta(hours=30)).isoformat()},
            {"timestamp": (now - timedelta(hours=2)).isoformat()},
        ],
        "episodes": [{"id": "ep-1"}],
        "recommendations": [{"id": "rec-1"}],
        "liquidity_levels": [{"id": "lvl-1"}],
        "imbalances": [{"id": "imb-1"}],
        "indicator_snapshots": [{"id": "ind-1"}],
    }
    trimmed = truncate_chart_for_cache(chart, hours=24)
    assert len(trimmed["candles"]) == 1
    assert trimmed["episodes"] == []
    assert trimmed["recommendations"] == []
    assert trimmed["liquidity_levels"] == []
    assert trimmed["imbalances"] == []
    assert trimmed["indicator_snapshots"] == []
