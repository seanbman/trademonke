import argparse
import hashlib
import json
from pathlib import Path

from app.settings import get_settings
from app.telemetry.db import SessionLocal

from .service import ResearchService


def main() -> None:
    parser = argparse.ArgumentParser(description="Reproducible research validation and review exports")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("baseline")
    review = sub.add_parser("review-bundle")
    review.add_argument("episode_id")
    review.add_argument("--output")
    args = parser.parse_args()
    settings = get_settings()
    lock = Path("requirements.lock").read_bytes()
    service = ResearchService(SessionLocal, settings.strategy_version, settings.config_hash,
                              settings.git_sha, hashlib.sha256(lock).hexdigest(),
                              Path("runtime/research"))
    if args.command == "baseline":
        manifest = service.baseline()
        print(json.dumps({"run_id": manifest.id, "artifacts": manifest.artifact_refs}))
    else:
        bundle = service.review_bundle(args.episode_id)
        output = Path(args.output or f"runtime/research/review_{args.episode_id}.json")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(bundle, indent=2, sort_keys=True), encoding="utf-8")
        print(json.dumps({"episode_id": args.episode_id, "artifact": str(output)}))


if __name__ == "__main__":
    main()
