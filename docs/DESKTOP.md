# Desktop (Ubuntu)

TradeMonke can be launched like a normal Ubuntu app. Docker remains the runtime; the
desktop shell hides day-to-day Compose commands.

## Prerequisites

- Ubuntu 22.04 or 24.04 (amd64)
- ~8 GB RAM recommended
- Docker Engine + Compose plugin (installed on first launch / by the installer if missing)

## Install from `.deb` (recommended)

1. Download `trademonke_*_amd64.deb` from [GitHub Releases](https://github.com/seanbman/trademonke/releases),
   or build locally with `make deb` (or `bash scripts/desktop/build-deb.sh`).
2. Install:

```bash
sudo apt install ./trademonke_*_amd64.deb
```

3. Log out and back in (or `newgrp docker`) so your user can talk to Docker without sudo.
4. Open **TradeMonke** from the app menu (or run `trademonke`).

First launch finishes setup automatically:

1. Ensures Docker Engine + Node.js (for the Electron shell) when missing  
2. Clones the GitHub repo into `/opt/trademonke` (see `packaging/deb/repo.url`)  
3. Creates `.env` / venv and builds research images  
4. Starts Postgres, API, market data, and the GUI  
5. Opens the Electron window with the GUI token injected  

While that runs, the Electron **setup** window shows a status line plus a scrolling
verbose console (apt/git/docker/compose output). The same stream is appended to
`~/.local/share/trademonke/logs/desktop/trademonke-desktop.log`.

Telegram and Freqtrade are **not** started by the desktop icon.

The default clone URL is configured in `/etc/trademonke/repo.url` (copied from the package).
Override before first launch:

```bash
echo 'https://github.com/YOUR_ORG/YOUR_FORK.git' | sudo tee /etc/trademonke/repo.url
```

## Install from a checkout (developers)

```bash
# Preferred: clone onto the target machine from GitHub
export TRADEMONKE_REPO_URL=https://github.com/seanbman/trademonke.git
sudo -E ./scripts/desktop/install-ubuntu.sh

# Or install from the current local tree into /opt/trademonke (git updates disabled)
sudo ./scripts/desktop/install-ubuntu.sh .
```

## Launch / stop

- App menu: **TradeMonke**
- CLI: `trademonke` (`.deb` installs `/usr/bin/trademonke`; script installs also put wrappers in `~/.local/bin`)
- Stop: `trademonke-stop` or `/opt/trademonke/scripts/desktop/trademonke-stop.sh`

Default services: migrate → postgres → API → GUI → market-data.

## Updates (origin/main)

Packaged installs keep a **git clone** at `/opt/trademonke` tracking `origin/main`.
The `.deb` itself is a thin bootstrap; day-to-day app updates come from the GitHub remote
configured in `/etc/trademonke/repo.url` (must match [`packaging/deb/repo.url`](../packaging/deb/repo.url):
`https://github.com/seanbman/trademonke.git`).

**Every Electron launch** runs an update check (and `trademonke-start.sh` does the same unless
`--no-update-check`):

1. `git fetch origin main`  
2. If `HEAD` ≠ `origin/main`, prompt **Update** / **Later**  
3. **Update** runs `scripts/desktop/trademonke-update.sh`: ff-only merge when possible, otherwise
   reset the install clone to `origin/main`, then rebuild, migrate, restart  
4. If fetch/remote fails, show a warning (not treated as “already current”)  
5. Dirty **tracked** files block the update (lists paths). Discard with
   `TRADEMONKE_UPDATE_DISCARD=1` on the update script, or clean the tree manually  
6. `.env` and `runtime/` are never overwritten by git  

If the install still points at an old remote (for example `trading-bot.git`), it will never see
commits on `trademonke` `main`. Fix with:

```bash
sudo tee /etc/trademonke/repo.url >/dev/null <<'EOF'
https://github.com/seanbman/trademonke.git
EOF
git -C /opt/trademonke remote set-url origin "$(tr -d '[:space:]' </etc/trademonke/repo.url)"
git -C /opt/trademonke fetch origin main
```

Manual update:

```bash
/opt/trademonke/scripts/desktop/trademonke-update.sh
```

Private repos need fetch credentials on the machine (SSH key or credential helper).

## Building the `.deb`

```bash
make deb
# → dist/trademonke_<version>_amd64.deb
```

CI builds and attaches the package on `v*` tags. If `.github/workflows/` is not writable in
your checkout, sync the workflow from the packaging tree:

```bash
bash scripts/desktop/sync-ci-workflow.sh
```

Source workflow: [`packaging/deb/ci/desktop-deb.yml`](../packaging/deb/ci/desktop-deb.yml).

## GUI token

```bash
cd /opt/trademonke
.venv/bin/python scripts/prepare_env.py --print-gui-token
```

The Electron shell injects `PLATFORM_GUI_ACCESS_TOKEN` into `sessionStorage` so you usually
do not need to paste it. Browser fallback still uses the login form.

## Data locations

| Path | Purpose |
|------|---------|
| `/opt/trademonke/.env` | Secrets and ports |
| `~/.local/share/trademonke/data` | Persistent research data (Docker Desktop-safe bind mounts) |
| `~/.local/share/trademonke/logs` | Compose service logs (`platform/`, etc.) |
| `~/.local/share/trademonke/logs/desktop/` | Desktop/bootstrap session log + error reports |
| `/opt/trademonke/.trademonke-installed-sha` | Last applied update SHA |
| `/etc/trademonke/repo.url` | GitHub clone URL used by packaged installs |
| `/usr/lib/trademonke/` | Packaged Electron shell + bootstrap scripts |

Docker Desktop only shares paths under your home directory by default. Packaged
installs under `/opt/trademonke` therefore set `DATA_ROOT` / `LOG_ROOT` to
`~/.local/share/trademonke/...` automatically via `scripts/prepare_env.py`.

## Desktop error reports

When the Electron shell or start scripts fail, a full report is written for agent/debug review
(no need to copy dialog text):

| Path | Purpose |
|------|---------|
| `~/.local/share/trademonke/logs/desktop/latest-error.log` | Most recent failure (always overwritten) |
| `~/.local/share/trademonke/logs/desktop/errors/*-error.log` | Timestamped history |
| `~/.local/share/trademonke/logs/desktop/trademonke-desktop.log` | Append-only session/status stream |

Each error report includes the exception, command output, `docker ps`, compose status, and recent service logs.

```bash
# Quick view
less ~/.local/share/trademonke/logs/desktop/latest-error.log
# Or follow compose + show latest desktop error header
trademonke-logs
# /opt path:
/opt/trademonke/scripts/desktop/trademonke-logs.sh
# packaged:
/usr/lib/trademonke/scripts/desktop/trademonke-logs.sh
```

## Safety

This desktop package is **dry-run / spot research only**. It does not unlock live trading.
See [GUI.md](GUI.md) for the workstation reading model (three questions + pattern soft-labels).
