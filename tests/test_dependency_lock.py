from pathlib import Path
import tomllib

from sqlalchemy import Uuid

from app.telemetry.models import CandleRecord


def test_runtime_and_ci_use_exact_dependency_constraints():
    root = Path(__file__).resolve().parents[1]
    lock = (root / "requirements.lock").read_text()
    assert "ccxt==" in lock and "fastapi==" in lock and "SQLAlchemy==" in lock
    assert "pip install --no-cache-dir -c requirements.lock ." in (root / "Dockerfile").read_text()
    workflow = (root / ".github" / "workflows" / "quality.yml").read_text()
    assert workflow.count("-c requirements.lock") == 2


def test_application_image_context_excludes_runtime_data_and_secrets():
    root = Path(__file__).resolve().parents[1]
    dockerignore = (root / ".dockerignore").read_text().splitlines()
    assert dockerignore[0] == "*"
    assert "!app/**" in dockerignore
    assert "!migrations/**" in dockerignore
    assert not any(line.startswith("!runtime") for line in dockerignore)
    assert not any(line.startswith("!.env") for line in dockerignore)


def test_runtime_includes_telegram_http_client_and_postgres_uuid_mapping():
    root = Path(__file__).resolve().parents[1]
    project = tomllib.loads((root / "pyproject.toml").read_text())["project"]
    assert any(dependency.startswith("httpx") for dependency in project["dependencies"])
    assert isinstance(CandleRecord.__table__.c.id.type, Uuid)
    assert CandleRecord.__table__.c.id.type.as_uuid is False
