from app.runtime import (heroku_dyno_role, normalize_database_url,
                         should_embed_market_relay, should_run_standalone_market_relay)
from app.settings import Settings, get_settings


def test_normalize_database_url_converts_postgres_scheme(monkeypatch):
    monkeypatch.delenv("DYNO", raising=False)
    url = normalize_database_url("postgres://user:pass@host:5432/db")
    assert url == "postgresql+psycopg://user:pass@host:5432/db"


def test_normalize_database_url_adds_ssl_on_heroku(monkeypatch):
    monkeypatch.setenv("DYNO", "web.1")
    url = normalize_database_url("postgres://user:pass@host:5432/db")
    assert url.endswith("sslmode=require")


def test_settings_accepts_database_url_alias(monkeypatch):
    monkeypatch.delenv("DYNO", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgres://user:pass@host:5432/db")
    get_settings.cache_clear()
    settings = Settings()
    assert settings.database_url == "postgresql+psycopg://user:pass@host:5432/db"


def test_settings_accepts_source_version(monkeypatch):
    monkeypatch.setenv("SOURCE_VERSION", "deadbeef")
    get_settings.cache_clear()
    settings = Settings()
    assert settings.git_sha == "deadbeef"


def test_heroku_web_dyno_roles(monkeypatch):
    monkeypatch.setenv("DYNO", "web.1")
    assert heroku_dyno_role() == "web"
    assert should_embed_market_relay(False) is True
    assert should_run_standalone_market_relay(True) is False


def test_heroku_web_relay_mode_skips_embedded_relay(monkeypatch):
    monkeypatch.setenv("DYNO", "web.1")
    monkeypatch.setenv("PLATFORM_MODE", "relay")
    assert should_embed_market_relay(False) is False


def test_heroku_worker_dyno_roles(monkeypatch):
    monkeypatch.setenv("DYNO", "worker.1")
    assert heroku_dyno_role() == "worker"
    assert should_embed_market_relay(False) is False
    assert should_run_standalone_market_relay(True) is False


def test_compose_defaults_keep_standalone_relay(monkeypatch):
    monkeypatch.delenv("DYNO", raising=False)
    assert should_embed_market_relay(False) is False
    assert should_run_standalone_market_relay(True) is True


def test_heroku_web_enables_gui_serving(monkeypatch):
    monkeypatch.setenv("DYNO", "web.1")
    get_settings.cache_clear()
    settings = Settings()
    assert settings.serve_gui is True
