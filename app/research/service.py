from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from app.telemetry.models import (EpisodeEventRecord, FeatureSnapshotRecord,
                                  GateEvaluationRecord, ImbalanceRecord,
                                  IndicatorAlertEventRecord, LiquidityLevelRecord,
                                  OutcomeLabelRecord, RecommendationRecord,
                                  RiskEvaluationRecord, RunManifestRecord,
                                  StrategyEpisodeRecord)

from .validation import (ResearchExample, ablations, chronological_split, dataset_hash,
                         metrics, walk_forward)


class ResearchService:
    def __init__(self, session_factory, strategy_version: str, config_hash: str,
                 git_sha: str, dependency_manifest_id: str, artifact_root: Path):
        self.session_factory = session_factory
        self.strategy_version = strategy_version
        self.config_hash = config_hash
        self.git_sha = git_sha
        self.dependency_manifest_id = dependency_manifest_id
        self.artifact_root = artifact_root

    def baseline(self) -> RunManifestRecord:
        started = datetime.now(timezone.utc)
        with self.session_factory() as session:
            outcomes = list(session.scalars(select(OutcomeLabelRecord).order_by(
                OutcomeLabelRecord.labelled_at, OutcomeLabelRecord.episode_id)))
            examples = []
            for outcome in outcomes:
                feature = session.scalar(select(FeatureSnapshotRecord).where(
                    FeatureSnapshotRecord.episode_id == outcome.episode_id).order_by(
                        FeatureSnapshotRecord.candle_timestamp.desc()).limit(1))
                examples.append(ResearchExample(
                    outcome.episode_id, outcome.labelled_at,
                    outcome.target_stop_ordering == "target_first",
                    {key: bool(value) for key, value in (feature.features if feature else {}).items()}))
            digest = dataset_hash(examples)
            split = chronological_split(examples)
            report = {
                "schema_version": "baseline.v1", "dataset_hash": digest,
                "splits": {name: metrics(rows) for name, rows in split.items()},
                "walk_forward": walk_forward(split["development"] + split["validation"]),
                "ablations": ablations(split["development"] + split["validation"]),
                "untouched_test_sealed": True,
                "untouched_episode_ids": [item.episode_id for item in split["untouched_test"]],
            }
            run_id = "run_" + hashlib.sha256(
                f"{digest}|{self.strategy_version}|{self.config_hash}|{self.git_sha}".encode()).hexdigest()[:20]
            self.artifact_root.mkdir(parents=True, exist_ok=True)
            artifact = self.artifact_root / f"{run_id}.json"
            artifact.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
            manifest = session.get(RunManifestRecord, run_id)
            if manifest is None:
                manifest = RunManifestRecord(
                    id=run_id, run_type="baseline", started_at=started,
                    completed_at=datetime.now(timezone.utc), status="completed",
                    configuration={"split": ["60%", "20%", "20%"], "folds": 3},
                    dataset_manifest={"hash": digest, "examples": len(examples),
                                      "untouched_test_sealed": True},
                    dependency_manifest_id=self.dependency_manifest_id,
                    artifact_refs=[str(artifact)], strategy_version=self.strategy_version,
                    config_hash=self.config_hash, git_sha=self.git_sha)
                session.add(manifest)
                session.commit()
            return manifest

    def review_bundle(self, episode_id: str) -> dict:
        with self.session_factory() as session:
            episode = session.get(StrategyEpisodeRecord, episode_id)
            if episode is None:
                raise ValueError("episode not found")
            level = session.get(LiquidityLevelRecord, episode.liquidity_level_id)
            bundle = {
                "schema_version": "review-bundle.v1", "generated_at": datetime.now(timezone.utc).isoformat(),
                "episode": self._record(episode), "liquidity_level": self._record(level),
                "timeline": [self._record(item) for item in session.scalars(select(EpisodeEventRecord).where(
                    EpisodeEventRecord.episode_id == episode_id).order_by(EpisodeEventRecord.occurred_at))],
                "imbalances": [self._record(item) for item in session.scalars(select(ImbalanceRecord).where(ImbalanceRecord.episode_id == episode_id))],
                "features": [self._record(item) for item in session.scalars(select(FeatureSnapshotRecord).where(FeatureSnapshotRecord.episode_id == episode_id))],
                "gates": [self._record(item) for item in session.scalars(select(GateEvaluationRecord).where(GateEvaluationRecord.episode_id == episode_id))],
                "risk": [self._record(item) for item in session.scalars(select(RiskEvaluationRecord).where(RiskEvaluationRecord.episode_id == episode_id))],
                "recommendations": [self._record(item) for item in session.scalars(select(RecommendationRecord).where(RecommendationRecord.episode_id == episode_id))],
                "alerts": [self._record(item) for item in session.scalars(select(IndicatorAlertEventRecord).where(
                    IndicatorAlertEventRecord.symbol == episode.symbol,
                    IndicatorAlertEventRecord.candle_timestamp >= episode.started_at))],
                "provenance": {"strategy_version": episode.strategy_version,
                               "config_hash": episode.config_hash, "git_sha": episode.git_sha},
            }
            return bundle

    @staticmethod
    def _record(record):
        if record is None:
            return None
        result = {}
        for column in record.__table__.columns:
            value = getattr(record, column.name)
            result[column.name] = value.isoformat() if isinstance(value, datetime) else str(value) if hasattr(value, "as_tuple") else value
        return result
