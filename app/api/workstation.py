from __future__ import annotations

import hashlib
import json
from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.settings import Settings
from app.telemetry.models import EpisodeEventRecord

# Keep websocket snapshots bounded for long-lived GUI sessions.
EPISODE_EVENTS_PER_EPISODE_CAP = 50


def slim_bootstrap_for_snapshot(bootstrap: Any) -> dict[str, Any]:
    """Watchlist + controls only; chart payload already carries symbol-scoped research objects."""
    if hasattr(bootstrap, "model_dump"):
        payload = bootstrap.model_dump()
    elif isinstance(bootstrap, dict):
        payload = dict(bootstrap)
    else:
        payload = {
            "contract_version": getattr(bootstrap, "contract_version", "gui.v1"),
            "generated_at": getattr(bootstrap, "generated_at", None),
            "watchlist": getattr(bootstrap, "watchlist", []),
            "controls": getattr(bootstrap, "controls", {}),
        }
    return {
        "contract_version": payload.get("contract_version", "gui.v1"),
        "generated_at": payload.get("generated_at"),
        "watchlist": payload.get("watchlist") or [],
        "setups": [],
        "episodes": [],
        "recommendations": [],
        "controls": payload.get("controls") or {},
    }


def cap_episode_events(
    events: list[Any],
    *,
    per_episode: int = EPISODE_EVENTS_PER_EPISODE_CAP,
) -> tuple[list[Any], dict[str, list[Any]]]:
    """Keep the most recent events per episode (input ordered by occurred_at ascending)."""
    episode_events: dict[str, list[Any]] = {}
    for event in events:
        episode_id = getattr(event, "episode_id", None)
        if episode_id is None and isinstance(event, dict):
            episode_id = event.get("episode_id")
        if not episode_id:
            continue
        episode_events.setdefault(episode_id, []).append(event)
    for episode_id, bucket in list(episode_events.items()):
        if len(bucket) > per_episode:
            episode_events[episode_id] = bucket[-per_episode:]
    capped: list[Any] = []
    for bucket in episode_events.values():
        capped.extend(bucket)
    return capped, episode_events


def snapshot_fingerprint(payload: dict) -> str:
    stable = dict(payload)
    bootstrap = dict(stable.get("bootstrap") or {})
    bootstrap.pop("generated_at", None)
    # Ignore bulk research lists if a full bootstrap ever appears; snapshots send slim bootstrap.
    stable["bootstrap"] = {
        "watchlist": bootstrap.get("watchlist"),
        "controls": bootstrap.get("controls"),
    }
    # Health is status strings only, but exclude it so near-threshold stale flips do not
    # force full snapshot churn to the chart.
    stable.pop("health", None)
    encoded = json.dumps(stable, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode()).hexdigest()


def build_workstation_snapshot(symbol: str, timeframe: str, settings: Settings,
                               session: Session, *, bootstrap_builder,
                               chart_builder, health_builder,
                               alerts_builder, execution_builder) -> dict:
    bootstrap = slim_bootstrap_for_snapshot(bootstrap_builder(session))
    chart = chart_builder(symbol, timeframe, 500, session, settings)
    episode_ids = [item.id for item in chart.episodes]
    events = [] if not episode_ids else list(session.scalars(
        select(EpisodeEventRecord).where(
            EpisodeEventRecord.episode_id.in_(episode_ids)
        ).order_by(EpisodeEventRecord.occurred_at)
    ))
    events, episode_events = cap_episode_events(events)
    payload = {
        "bootstrap": bootstrap,
        "chart": chart,
        "events": events,
        "episode_events": episode_events,
        "health": health_builder(settings, session),
        "alerts": alerts_builder(100, session),
        "execution": execution_builder(settings, session),
    }
    return jsonable_encoder(payload)
