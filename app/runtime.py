"""Process-role helpers for PaaS deployments such as Heroku."""

from __future__ import annotations

import os


def heroku_dyno_role() -> str | None:
    """Return web, worker, or release when running on a Heroku dyno."""
    dyno = os.environ.get("DYNO", "")
    for role in ("web", "worker", "release"):
        if dyno.startswith(f"{role}."):
            return role
    return None


def running_on_heroku() -> bool:
    return heroku_dyno_role() is not None


def should_embed_market_relay(explicit: bool) -> bool:
    """Run the Kraken relay inside the web process on Heroku web dynos (full mode only)."""
    if os.environ.get("PLATFORM_MODE") == "relay":
        return False
    if heroku_dyno_role() == "web":
        return True
    return explicit


def should_run_standalone_market_relay(explicit: bool) -> bool:
    """Run the relay in market-data unless the web dyno already embeds it."""
    role = heroku_dyno_role()
    if role in {"web", "worker"}:
        return False
    return explicit


def normalize_database_url(url: str) -> str:
    """Convert Heroku DATABASE_URL values into SQLAlchemy/psycopg URLs."""
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url[len("postgres://"):]
    if running_on_heroku() and "sslmode=" not in url:
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}sslmode=require"
    return url
