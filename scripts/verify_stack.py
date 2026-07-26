"""Wait for the loopback API and GUI endpoints to become reachable."""

from __future__ import annotations

import time
import urllib.request
from pathlib import Path


def endpoint_urls(env_text: str) -> tuple[str, str]:
    values = dict(
        line.partition("=")[::2]
        for line in env_text.splitlines()
        if "=" in line
    )
    api_port = values.get("PLATFORM_API_PORT") or "8000"
    gui_port = values.get("PLATFORM_GUI_PORT") or "3000"
    return f"http://127.0.0.1:{api_port}/health", f"http://127.0.0.1:{gui_port}/"


def main() -> None:
    endpoints = endpoint_urls(Path(".env").read_text())
    deadline = time.monotonic() + 45
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            for endpoint in endpoints:
                with urllib.request.urlopen(endpoint, timeout=3) as response:
                    if response.status != 200:
                        raise RuntimeError(f"{endpoint} returned HTTP {response.status}")
            print(f"Verified API and GUI. Research workstation: {endpoints[1]}")
            return
        except (OSError, RuntimeError) as error:
            last_error = error
            time.sleep(1)
    raise SystemExit(f"stack did not become ready: {last_error}")


if __name__ == "__main__":
    main()
