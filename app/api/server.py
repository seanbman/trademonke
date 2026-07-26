"""Production ASGI entrypoint for Heroku and other PaaS hosts."""

from __future__ import annotations

import os

import uvicorn


def main() -> None:
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("app.api.main:app", host="0.0.0.0", port=port, log_level="info")


if __name__ == "__main__":
    main()
