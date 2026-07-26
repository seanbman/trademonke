from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Sequence


@dataclass(frozen=True)
class ResearchExample:
    episode_id: str
    timestamp: datetime
    success: bool
    features: dict[str, bool]


def chronological_split(examples: Sequence[ResearchExample], development=0.6,
                        validation=0.2) -> dict[str, list[ResearchExample]]:
    ordered = sorted(examples, key=lambda item: (item.timestamp, item.episode_id))
    n = len(ordered)
    dev_end = int(n * development)
    validation_end = dev_end + int(n * validation)
    return {"development": ordered[:dev_end], "validation": ordered[dev_end:validation_end],
            "untouched_test": ordered[validation_end:]}


def dataset_hash(examples: Sequence[ResearchExample]) -> str:
    payload = [{"episode_id": item.episode_id, "timestamp": item.timestamp.isoformat(),
                "success": item.success, "features": item.features}
               for item in sorted(examples, key=lambda row: (row.timestamp, row.episode_id))]
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def metrics(examples: Sequence[ResearchExample]) -> dict:
    count = len(examples)
    wins = sum(item.success for item in examples)
    rate = wins / count if count else None
    return {"sample_size": count, "wins": wins, "win_rate": rate}


def walk_forward(examples: Sequence[ResearchExample], folds: int = 3) -> list[dict]:
    ordered = sorted(examples, key=lambda item: (item.timestamp, item.episode_id))
    if not ordered:
        return []
    width = max(1, len(ordered) // (folds + 1))
    results = []
    for index in range(1, folds + 1):
        train = ordered[:index * width]
        test = ordered[index * width:min((index + 1) * width, len(ordered))]
        if test:
            results.append({"fold": index, "train": metrics(train), "test": metrics(test),
                            "train_end": train[-1].timestamp.isoformat(),
                            "test_start": test[0].timestamp.isoformat()})
    return results


def ablations(examples: Sequence[ResearchExample]) -> dict[str, dict]:
    feature_names = sorted({name for item in examples for name in item.features})
    return {name: {"present": metrics([item for item in examples if item.features.get(name)]),
                   "absent": metrics([item for item in examples if not item.features.get(name)])}
            for name in feature_names}
