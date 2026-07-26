from pathlib import Path

from scripts.prepare_env import ensure_docker_desktop_paths, prepare_env


def test_prepare_env_preserves_telegram_and_fills_only_startup_secrets(tmp_path: Path):
    env = tmp_path / ".env"
    original = (
        "PLATFORM_GUI_ACCESS_TOKEN=REPLACE_WITH_A_LONG_RANDOM_TOKEN\n"
        "TELEGRAM_BOT_TOKEN=telegram-secret\n"
        "POSTGRES_PASSWORD=GENERATE_A_LONG_RANDOM_PASSWORD\n"
        "PLATFORM_GUI_ACCESS_TOKEN=\n"
        "PLATFORM_FEEDER_TOKEN=\n"
        "TELEGRAM_CHAT_ID=123\n"
    )
    env.write_text(original)

    generated, backup = prepare_env(env)

    result = env.read_text()
    assert generated.keys() == {
        "POSTGRES_PASSWORD",
        "PLATFORM_GUI_ACCESS_TOKEN",
        "PLATFORM_FEEDER_TOKEN",
    }
    assert "TELEGRAM_BOT_TOKEN=telegram-secret\n" in result
    assert "TELEGRAM_CHAT_ID=123\n" in result
    assert result.count("PLATFORM_GUI_ACCESS_TOKEN=") == 1
    assert result.count("PLATFORM_FEEDER_TOKEN=") == 1
    assert "GENERATE_A_LONG_RANDOM_PASSWORD" not in result
    assert backup is not None and backup.read_text() == original


def test_prepare_env_does_not_rotate_configured_values(tmp_path: Path):
    env = tmp_path / ".env"
    original = (
        "TELEGRAM_BOT_TOKEN=tg\n"
        "POSTGRES_PASSWORD=db\n"
        "PLATFORM_GUI_ACCESS_TOKEN=gui\n"
        "PLATFORM_FEEDER_TOKEN=feeder\n"
    )
    env.write_text(original)

    generated, backup = prepare_env(env)

    assert generated == {}
    assert backup is None
    assert env.read_text() == original


def test_prepare_env_rotates_only_requested_gui_token(tmp_path: Path):
    env = tmp_path / ".env"
    env.write_text(
        "TELEGRAM_BOT_TOKEN=tg\n"
        "POSTGRES_PASSWORD=db\n"
        "PLATFORM_GUI_ACCESS_TOKEN=old\n"
        "PLATFORM_FEEDER_TOKEN=feeder\n"
    )

    generated, _ = prepare_env(env, rotate=frozenset({"PLATFORM_GUI_ACCESS_TOKEN"}))

    result = env.read_text()
    assert generated.keys() == {"PLATFORM_GUI_ACCESS_TOKEN"}
    assert "TELEGRAM_BOT_TOKEN=tg\n" in result
    assert "POSTGRES_PASSWORD=db\n" in result
    assert "PLATFORM_FEEDER_TOKEN=feeder\n" in result
    assert "PLATFORM_GUI_ACCESS_TOKEN=old\n" not in result


def test_ensure_docker_desktop_paths_relocates_opt_install(tmp_path: Path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    project = tmp_path / "opt" / "trademonke"
    project.mkdir(parents=True)
    env = project / ".env"
    env.write_text("DATA_ROOT=./runtime/data\nLOG_ROOT=./runtime/logs\nPLATFORM_FEEDER_TOKEN=x\n")

    assert ensure_docker_desktop_paths(env) is True
    text = env.read_text()
    assert f"DATA_ROOT={home / '.local' / 'share' / 'trademonke' / 'data'}" in text
    assert f"LOG_ROOT={home / '.local' / 'share' / 'trademonke' / 'logs'}" in text
    assert (home / ".local" / "share" / "trademonke" / "data").is_dir()
