from pathlib import Path
import os
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
DESKTOP_SCRIPTS = ROOT / "scripts" / "desktop"
PACKAGING = ROOT / "packaging" / "deb"


def test_desktop_launcher_scripts_exist_and_are_executable():
    required = [
        "common.sh",
        "bootstrap.sh",
        "trademonke-start.sh",
        "trademonke-stop.sh",
        "trademonke-logs.sh",
        "trademonke-update.sh",
        "trademonke-launch.sh",
        "check-update.sh",
        "install-ubuntu.sh",
        "build-deb.sh",
        "sync-ci-workflow.sh",
    ]
    for name in required:
        path = DESKTOP_SCRIPTS / name
        assert path.is_file(), name
        assert path.stat().st_mode & 0o111, f"{name} should be executable"


def test_desktop_electron_shell_and_docs_exist():
    assert (ROOT / "desktop" / "main.js").is_file()
    assert (ROOT / "desktop" / "package.json").is_file()
    assert (ROOT / "desktop" / "trademonke.desktop").is_file()
    assert (ROOT / "desktop" / "assets" / "trade-monke-icon.png").is_file()
    assert (ROOT / "desktop" / "assets" / "trademonke.png").is_file()
    main = (ROOT / "desktop" / "main.js").read_text(encoding="utf-8")
    assert "trade-monke-icon.png" in main
    assert "resolveAppIcon" in main
    nfpm = (PACKAGING / "nfpm.yaml").read_text(encoding="utf-8")
    assert "trade-monke-icon.png" in nfpm
    assert (ROOT / "docs" / "DESKTOP.md").is_file()
    assert (ROOT / "docs" / "GUI.md").is_file()


def test_packaging_deb_assets_exist():
    assert (PACKAGING / "nfpm.yaml").is_file()
    assert (PACKAGING / "repo.url").is_file()
    assert (PACKAGING / "bin" / "trademonke").is_file()
    assert (PACKAGING / "trademonke.desktop").is_file()
    assert (PACKAGING / "scripts" / "postinst").is_file()
    assert (PACKAGING / "ci" / "desktop-deb.yml").is_file()
    repo_url = (PACKAGING / "repo.url").read_text(encoding="utf-8").strip()
    assert repo_url.startswith("https://")
    assert repo_url.endswith(".git")
    assert "trademonke.git" in repo_url


def test_desktop_entry_template_has_placeholders():
    template = (ROOT / "desktop" / "trademonke.desktop").read_text(encoding="utf-8")
    assert "@TRADEMONKE_ROOT@" in template
    assert "@ICON@" in template
    assert "@LAUNCH@" in template


def test_common_sh_package_mode_repo_url_and_needs_bootstrap():
    script = r"""
set -euo pipefail
source scripts/desktop/common.sh
url="$(trademonke_repo_url require)"
test -n "$url"
test "$url" = "$(tr -d '[:space:]' < packaging/deb/repo.url)"
tmp="$(mktemp -d)"
# Missing compose → needs bootstrap (exit 0 from helper)
if needs_bootstrap "$tmp"; then
  echo missing_needs_bootstrap
else
  echo "unexpected ready" >&2
  exit 1
fi
rm -rf "$tmp"
echo OK
"""
    result = subprocess.run(
        ["bash", "-lc", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "OK" in result.stdout
    assert "missing_needs_bootstrap" in result.stdout


def test_update_script_refuses_non_git_install(tmp_path: Path):
    # trademonke-update.sh must exit when install dir is not a git clone.
    fake_root = tmp_path / "opt"
    fake_root.mkdir()
    (fake_root / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")
    env = {
        **os.environ,
        "TRADEMONKE_ROOT": str(fake_root),
        "TRADEMONKE_NONINTERACTIVE": "1",
    }
    result = subprocess.run(
        ["bash", str(DESKTOP_SCRIPTS / "trademonke-update.sh")],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode != 0
    combined = (result.stdout or "") + (result.stderr or "")
    assert "git clone" in combined.lower() or "not a git" in combined.lower()


def test_desktop_entry_sed_substitution():
    template = (ROOT / "desktop" / "trademonke.desktop").read_text(encoding="utf-8")
    rendered = (
        template.replace("@TRADEMONKE_ROOT@", "/opt/trademonke")
        .replace("@ICON@", "/usr/share/icons/trademonke.png")
        .replace("@LAUNCH@", "/usr/bin/trademonke")
    )
    assert "@" not in rendered
    assert "Exec=env TRADEMONKE_ROOT=/opt/trademonke /usr/bin/trademonke" in rendered


def test_bootstrap_check_mode_exits_nonzero_when_missing():
    with tempfile.TemporaryDirectory() as tmp:
        result = subprocess.run(
            ["bash", str(DESKTOP_SCRIPTS / "bootstrap.sh"), "--check"],
            env={**os.environ, "TRADEMONKE_INSTALL_ROOT": tmp, "TRADEMONKE_NONINTERACTIVE": "1"},
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 1


def test_docs_describe_deb_install():
    text = (ROOT / "docs" / "DESKTOP.md").read_text(encoding="utf-8")
    assert ".deb" in text
    assert "make deb" in text
    assert "/opt/trademonke" in text
    assert "origin/main" in text
    assert "Every Electron launch" in text
    assert "trademonke.git" in text


def test_check_update_not_git_clone_exits_2(tmp_path: Path):
    env = {**os.environ, "TRADEMONKE_ROOT": str(tmp_path)}
    result = subprocess.run(
        ["bash", str(DESKTOP_SCRIPTS / "check-update.sh")],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 2
    assert "not-a-git-clone" in (result.stdout or "")


def test_main_js_surfaces_update_check_failures():
    main = (ROOT / "desktop" / "main.js").read_text(encoding="utf-8")
    assert "UPDATE_CHECK_FAILED" in main
    assert "Already up to date with origin/main" in main
    assert "Could not check origin/main for updates" in main


def test_main_js_has_first_run_bootstrap():
    main = (ROOT / "desktop" / "main.js").read_text(encoding="utf-8")
    assert "maybeBootstrap" in main
    assert "bootstrap.sh" in main
    assert "STATUS:" in main
    assert "writeErrorReport" in main
    assert "latest-error.log" in main
    assert "appendBootLog" in main
    assert "boot-log" in main


def test_splash_shows_verbose_console():
    splash = (ROOT / "desktop" / "splash.html").read_text(encoding="utf-8")
    preload = (ROOT / "desktop" / "preload.js").read_text(encoding="utf-8")
    assert 'id="log"' in splash
    assert "Verbose output" in splash
    assert "onBootLog" in splash
    assert "onBootLog" in preload
    assert "getBootLog" in preload


def test_common_sh_writes_error_report(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("TRADEMONKE_LOG_DIR", str(tmp_path / "desktop-logs"))
    monkeypatch.setenv("TRADEMONKE_NONINTERACTIVE", "1")
    script = r"""
set -euo pipefail
source scripts/desktop/common.sh
report="$(trademonke_write_error_report "unit test" "hello from test")"
test -f "$report"
test -f "$(trademonke_log_dir)/latest-error.log"
grep -q "hello from test" "$report"
echo OK
"""
    result = subprocess.run(
        ["bash", "-lc", script],
        cwd=ROOT,
        env={**os.environ, "TRADEMONKE_LOG_DIR": str(tmp_path / "desktop-logs"), "TRADEMONKE_NONINTERACTIVE": "1"},
        check=True,
        capture_output=True,
        text=True,
    )
    assert "OK" in result.stdout
    assert (tmp_path / "desktop-logs" / "latest-error.log").is_file()
