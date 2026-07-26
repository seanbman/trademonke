from __future__ import annotations

import hashlib
from pathlib import Path

from sqlalchemy import text

from .db import engine


def migration_files(root: Path | None = None) -> list[Path]:
    directory = root or Path(__file__).resolve().parents[2] / "migrations" / "versions"
    return sorted(directory.glob("[0-9][0-9][0-9][0-9]_*.sql"))


def migrate(root: Path | None = None) -> list[str]:
    applied: list[str] = []
    with engine.begin() as connection:
        connection.execute(text(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "version VARCHAR(255) PRIMARY KEY, checksum VARCHAR(64) NOT NULL, "
            "applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP)"
        ))
        existing = dict(connection.execute(text(
            "SELECT version, checksum FROM schema_migrations"
        )).all())
        for path in migration_files(root):
            sql = path.read_text(encoding="utf-8")
            checksum = hashlib.sha256(sql.encode()).hexdigest()
            if path.name in existing:
                if existing[path.name] != checksum:
                    raise RuntimeError(f"applied migration checksum changed: {path.name}")
                continue
            connection.exec_driver_sql(sql)
            connection.execute(text(
                "INSERT INTO schema_migrations(version, checksum) VALUES (:version, :checksum)"
            ), {"version": path.name, "checksum": checksum})
            applied.append(path.name)
    return applied


def main() -> None:
    for version in migrate():
        print(f"applied {version}")


if __name__ == "__main__":
    main()
