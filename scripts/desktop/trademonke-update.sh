#!/usr/bin/env bash
# Fast-forward to origin/main and rebuild research services. Preserves .env and runtime/.
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

COMPOSE="$(compose_cmd)" || { dialog_error "Docker Compose is unavailable."; exit 2; }
docker info >/dev/null 2>&1 || { dialog_error "Cannot access the Docker daemon. Start Docker and ensure your user is in the docker group."; exit 2; }

# Refuse dirty tracked files (ignore untracked runtime/.env).
if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
  dialog_error "Local tracked files have uncommitted changes. Resolve them before updating."
  exit 2
fi

export BUILDKIT_PROGRESS=plain COMPOSE_PROGRESS=plain PYTHONUNBUFFERED=1
status_line "Stopping research services for update…"
$COMPOSE stop platform-api research-gui market-data postgres 2>/dev/null || true
status_line "Fetching origin/main…"
git fetch origin main
status_line "Fast-forward merging origin/main…"
git merge --ff-only origin/main

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
