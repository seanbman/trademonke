"""Rotate the local Compose PostgreSQL role and matching environment secret."""

from __future__ import annotations

import secrets
import subprocess
from pathlib import Path

from prepare_env import prepare_env


def main() -> None:
    password = secrets.token_urlsafe(32)
    command = "docker-compose exec -T postgres psql -U trading -d trading_platform"
    result = subprocess.run(
        ["sg", "docker", "-c", command],
        input=f"ALTER ROLE trading PASSWORD '{password}';\n",
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode:
        raise SystemExit(result.stderr.strip() or "PostgreSQL password rotation failed")
    prepare_env(
        Path(".env"),
        overrides={"POSTGRES_PASSWORD": password},
    )
    print("Rotated the local PostgreSQL password; Telegram settings were preserved.")


if __name__ == "__main__":
    main()
