from types import SimpleNamespace

from app.api.workstation import (
    EPISODE_EVENTS_PER_EPISODE_CAP,
    cap_episode_events,
    slim_bootstrap_for_snapshot,
    snapshot_fingerprint,
)


def test_slim_bootstrap_for_snapshot_drops_global_research_lists():
    slim = slim_bootstrap_for_snapshot(SimpleNamespace(
        contract_version="gui.v1",
        generated_at="2026-08-01T00:00:00+00:00",
        watchlist=[{"symbol": "BTC/USDT", "status": "active", "protected": True}],
        setups=[{"id": "setup-1"}],
        episodes=[{"id": "ep-1"}],
        recommendations=[{"id": "rec-1"}],
        controls={"paused": False, "kill_switch": False},
    ))
    assert slim["watchlist"][0]["symbol"] == "BTC/USDT"
    assert slim["controls"]["paused"] is False
    assert slim["setups"] == []
    assert slim["episodes"] == []
    assert slim["recommendations"] == []


def test_cap_episode_events_keeps_most_recent_per_episode():
    events = [
        SimpleNamespace(episode_id="ep_1", event_id=f"a{i}", occurred_at=i)
        for i in range(EPISODE_EVENTS_PER_EPISODE_CAP + 5)
    ] + [
        SimpleNamespace(episode_id="ep_2", event_id=f"b{i}", occurred_at=i)
        for i in range(3)
    ]
    capped, by_episode = cap_episode_events(events)
    assert len(by_episode["ep_1"]) == EPISODE_EVENTS_PER_EPISODE_CAP
    assert by_episode["ep_1"][0].event_id == "a5"
    assert by_episode["ep_1"][-1].event_id == f"a{EPISODE_EVENTS_PER_EPISODE_CAP + 4}"
    assert len(by_episode["ep_2"]) == 3
    assert len(capped) == EPISODE_EVENTS_PER_EPISODE_CAP + 3


def test_snapshot_fingerprint_stable_when_health_changes():
    base = {
        "bootstrap": {"generated_at": "t1", "watchlist": [], "controls": {"paused": False}},
        "chart": {"symbol": "BTC/USDT"},
        "alerts": [],
        "execution": {"mode": "shadow"},
        "events": [],
        "episode_events": {},
    }
    first = {**base, "health": {"status": "healthy"}}
    second = {**base, "health": {"status": "degraded"}}
    assert snapshot_fingerprint(first) == snapshot_fingerprint(second)
