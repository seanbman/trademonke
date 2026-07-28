#!/usr/bin/env bash
# Sync install to origin/main and rebuild research services. Preserves .env and runtime/.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"
ROOT="$(trademonke_root)"
cd "$ROOT"

if [[ ! -d .git ]]; then
  dialog_error "Install directory is not a git clone; cannot update from origin/main."
  exit 2
fi

ensure_docker_access "$0" "$@" || exit 2
COMPOSE="$(compose_cmd)" || { dialog_error "Docker Compose is unavailable."; exit 2; }

# Refuse dirty tracked files (ignore untracked runtime/.env).
# Packaged installs can discard with TRADEMONKE_UPDATE_DISCARD=1.
dirty="$(git status --porcelain --untracked-files=no || true)"
if [[ -n "$dirty" ]]; then
  if [[ "${TRADEMONKE_UPDATE_DISCARD:-0}" == "1" ]]; then
    status_line "Discarding local tracked changes (TRADEMONKE_UPDATE_DISCARD=1)…"
    git reset --hard HEAD
  else
    detail="$(printf '%s\n' "$dirty" | head -20)"
    dialog_error "Local tracked files have uncommitted changes. Resolve them before updating.

$detail

To discard install-local edits and continue:
  TRADEMONKE_UPDATE_DISCARD=1 $0"
    exit 2
  fi
fi

export BUILDKIT_PROGRESS=plain COMPOSE_PROGRESS=plain PYTHONUNBUFFERED=1
status_line "Stopping research services for update…"
$COMPOSE stop platform-api research-gui market-data postgres 2>/dev/null || true
status_line "Fetching origin/main…"
git fetch origin main

# Prefer ff-only; if history diverged (e.g. old remote), reset install to origin/main.
# Untracked paths that collide with incoming files are removed; .env/runtime stay ignored.
if git merge-base --is-ancestor HEAD origin/main 2>/dev/null; then
  status_line "Fast-forward merging origin/main…"
  git merge --ff-only origin/main
else
  status_line "Install history diverged from origin/main; resetting to remote…"
  git clean -fd
  git reset --hard origin/main
fi

status_line "Rebuilding Docker images…"
if docker compose version >/dev/null 2>&1; then
  $COMPOSE --progress=plain build
else
  $COMPOSE build
fi
status_line "Running migrations…"
$COMPOSE run --rm migrate
status_line "Restarting research services…"
$COMPOSE up -d postgres platform-api research-gui market-data

sha="$(git rev-parse --short HEAD)"
printf '%s\n' "$(git rev-parse HEAD)" > .trademonke-installed-sha
notify "TradeMonke" "Updated to $sha"
status_line "Update complete ($sha)"
echo "Updated to $sha"
