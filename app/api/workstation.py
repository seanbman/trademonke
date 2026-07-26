from __future__ import annotations

import hashlib
import json

from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.settings import Settings
from app.telemetry.models import EpisodeEventRecord


def snapshot_fingerprint(payload: dict) -> str:
    stable = dict(payload)
    stable["bootstrap"] = dict(stable["bootstrap"])
    stable["bootstrap"].pop("generated_at", None)
    encoded = json.dumps(stable, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def build_workstation_snapshot(symbol: str, timeframe: str, settings: Settings,
                               session: Session, *, bootstrap_builder,
                               chart_builder, health_builder,
                               alerts_builder, execution_builder) -> dict:
    bootstrap = bootstrap_builder(session)
    chart = chart_builder(symbol, timeframe, 500, session, settings)
    episode_ids = [item.id for item in chart.episodes]
    events = [] if not episode_ids else list(session.scalars(
        select(EpisodeEventRecord).where(
            EpisodeEventRecord.episode_id.in_(episode_ids)
        ).order_by(EpisodeEventRecord.occurred_at)
    ))
    episode_events: dict[str, list] = {}
    for event in events:
        episode_events.setdefault(event.episode_id, []).append(event)
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
