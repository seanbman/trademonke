"""Safely fill local startup secrets without replacing existing configuration."""

from __future__ import annotations

import argparse
import secrets
from pathlib import Path


MANAGED_KEYS = ("POSTGRES_PASSWORD", "PLATFORM_GUI_ACCESS_TOKEN", "PLATFORM_FEEDER_TOKEN")
PLACEHOLDER_PREFIXES = ("GENERATE_", "REPLACE_", "CHANGE_ME")
PATH_KEYS = ("DATA_ROOT", "LOG_ROOT")


def _is_unconfigured(value: str | None) -> bool:
    return value is None or not value.strip() or value.strip().startswith(PLACEHOLDER_PREFIXES)


def _env_map(lines: list[str]) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in lines:
        key, separator, value = line.partition("=")
        if separator:
            values[key] = value
    return values


def ensure_docker_desktop_paths(path: Path) -> bool:
    """Point DATA_ROOT/LOG_ROOT under $HOME when the project is outside Docker Desktop shares.

    Docker Desktop (Linux/Mac) only bind-mounts shared host paths. /opt/trademonke is not
    shared by default, so relative ./runtime/* mounts fail with "mounts denied".
    """
    project = path.resolve().parent
    home = Path.home().resolve()
    try:
        project.relative_to(home)
        return False
    except ValueError:
        pass

    lines = path.read_text().splitlines()
    values = _env_map(lines)
    if "DATA_ROOT" not in values and "LOG_ROOT" not in values:
        return False

    def needs_relocation(raw: str | None) -> bool:
        if raw is None:
            return False
        raw = raw.strip()
        if not raw or raw.startswith("./") or raw.startswith("../"):
            return True
        candidate = Path(raw).expanduser()
        if not candidate.is_absolute():
            return True
        try:
            candidate.resolve().relative_to(home)
            return False
        except ValueError:
            return True

    if not needs_relocation(values.get("DATA_ROOT")) and not needs_relocation(values.get("LOG_ROOT")):
        return False

    base = home / ".local" / "share" / "trademonke"
    new_data = base / "data"
    new_logs = base / "logs"
    new_data.mkdir(parents=True, exist_ok=True)
    new_logs.mkdir(parents=True, exist_ok=True)

    updated: list[str] = []
    seen = {key: False for key in PATH_KEYS}
    for line in lines:
        key, separator, _value = line.partition("=")
        if separator and key == "DATA_ROOT":
            updated.append(f"DATA_ROOT={new_data}")
            seen["DATA_ROOT"] = True
        elif separator and key == "LOG_ROOT":
            updated.append(f"LOG_ROOT={new_logs}")
            seen["LOG_ROOT"] = True
        else:
            updated.append(line)
    if "DATA_ROOT" in values and not seen["DATA_ROOT"]:
        updated.append(f"DATA_ROOT={new_data}")
    if "LOG_ROOT" in values and not seen["LOG_ROOT"]:
        updated.append(f"LOG_ROOT={new_logs}")
    path.write_text("\n".join(updated) + "\n")
    return True


def prepare_env(
    path: Path,
    rotate: frozenset[str] = frozenset(),
    overrides: dict[str, str] | None = None,
) -> tuple[dict[str, str], Path | None]:
    original = path.read_text()
    lines = original.splitlines()
    effective: dict[str, str] = {}
    for line in lines:
        key, separator, value = line.partition("=")
        if separator and key in MANAGED_KEYS:
            effective[key] = value

    overrides = overrides or {}
    generated = {
        key: overrides.get(key, secrets.token_urlsafe(32))
        for key in MANAGED_KEYS
        if key in rotate or key in overrides or _is_unconfigured(effective.get(key))
    }
    if not generated and all(sum(line.startswith(f"{key}=") for line in lines) == 1 for key in MANAGED_KEYS):
        ensure_docker_desktop_paths(path)
        return {}, None

    backup = path.with_name(".env.backup")
    if not backup.exists():
        backup.write_text(original)

    retained = [line for line in lines if not any(line.startswith(f"{key}=") for key in MANAGED_KEYS)]
    resolved = {key: generated.get(key, effective[key]) for key in MANAGED_KEYS}
    retained.extend(f"{key}={resolved[key]}" for key in MANAGED_KEYS)
    path.write_text("\n".join(retained) + "\n")
    ensure_docker_desktop_paths(path)
    return generated, backup


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rotate-gui-token", action="store_true")
    parser.add_argument("--print-gui-token", action="store_true")
    parser.add_argument("--print-gui-url", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    path = Path(".env")
    if not path.is_file():
        raise SystemExit("missing .env; restore or create it without overwriting existing secrets")
    rotate = frozenset({"PLATFORM_GUI_ACCESS_TOKEN"}) if args.rotate_gui_token else frozenset()
    generated, backup = prepare_env(path, rotate=rotate)
    if backup is not None and not args.quiet:
        print(f"Preserved the original environment in {backup}")
    if generated and not args.quiet:
        print("Generated missing local startup secrets; existing Telegram settings were preserved.")
    if "PLATFORM_GUI_ACCESS_TOKEN" in generated and not args.quiet:
        print(f"GUI login token: {generated['PLATFORM_GUI_ACCESS_TOKEN']}")
    elif args.print_gui_token:
        values = dict(
            line.partition("=")[::2]
            for line in path.read_text().splitlines()
            if "=" in line
        )
        print(values["PLATFORM_GUI_ACCESS_TOKEN"])
    if args.print_gui_url:
        values = dict(
            line.partition("=")[::2]
            for line in path.read_text().splitlines()
            if "=" in line
        )
        print(f"http://127.0.0.1:{values.get('PLATFORM_GUI_PORT') or '3000'}")


if __name__ == "__main__":
    main()
