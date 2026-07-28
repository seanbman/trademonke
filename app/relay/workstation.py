from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def truncate_chart_for_cache(chart: dict[str, Any], hours: int = 24) -> dict[str, Any]:
    cutoff = datetime.now(timezone.utc).timestamp() - hours * 3600
    candles = chart.get("candles") or []
    trimmed = [
        item for item in candles
        if datetime.fromisoformat(str(item["timestamp"]).replace("Z", "+00:00")).timestamp() >= cutoff
    ]
    result = dict(chart)
    result["candles"] = trimmed
    result["episodes"] = []
    result["recommendations"] = []
    result["liquidity_levels"] = []
    result["imbalances"] = []
    result["indicator_snapshots"] = []
    result["episode_events"] = {}
    result["annotations"] = []
    result["patterns"] = []
    return result
