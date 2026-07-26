from pathlib import Path

import yaml


def test_gui_is_loopback_published_without_exposing_postgres():
    root = Path(__file__).resolve().parents[1]
    compose = yaml.safe_load((root / "docker-compose.yml").read_text())
    services = compose["services"]

    assert services["postgres"].get("ports") is None
    assert services["postgres"]["networks"] == ["backend"]
    assert compose["networks"]["backend"]["internal"] is True
    assert services["platform-api"]["networks"] == ["backend", "frontend"]
    assert services["research-gui"]["networks"] == ["frontend"]
    assert services["research-gui"]["ports"] == [
        "127.0.0.1:${PLATFORM_GUI_PORT:-3000}:8080"
    ]
    assert services["relay-agent"]["networks"] == ["backend", "outbound"]
    nginx = (root / "gui" / "nginx.conf").read_text()
    assert "root /usr/share/nginx/html;" in nginx
