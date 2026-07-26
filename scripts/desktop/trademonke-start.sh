#!/usr/bin/env bash
# Start research stack (prepare_env → migrate → compose up → verify).
# Usage: trademonke-start.sh [--no-update-check] [--no-open] [--print-url]
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

NO_UPDATE_CHECK=0
NO_OPEN=0
PRINT_URL=0
for arg in "$@"; do
  case "$arg" in
    --no-update-check) NO_UPDATE_CHECK=1 ;;
    --no-open) NO_OPEN=1 ;;
    --print-url) PRINT_URL=1 ;;
  esac
done

ROOT="$(trademonke_root)"
cd "$ROOT"
trademonke_log "START begin root=$ROOT"
status_line "Starting research stack…"
trap 'code=$?; if [[ $code -ne 0 ]]; then trademonke_write_error_report "trademonke-start failed (exit $code)" "start script exited $code in $ROOT" >/dev/null; fi' EXIT

ensure_env "$ROOT"
export BUILDKIT_PROGRESS=plain COMPOSE_PROGRESS=plain PYTHONUNBUFFERED=1

ensure_docker_access "$0" "$@" || exit 2
COMPOSE="$(compose_cmd)" || { dialog_error "Docker Compose is unavailable."; exit 2; }

PY="$(python_bin "$ROOT")"
status_line "Preparing environment (.env / paths)…"
"$PY" scripts/prepare_env.py --quiet || "$PY" scripts/prepare_env.py

if [[ "$NO_UPDATE_CHECK" -eq 0 ]]; then
  status_line "Checking for updates on origin/main…"
  if "$SCRIPT_DIR/check-update.sh"; then
    if dialog_question "TradeMonke update available on origin/main. Update now?"; then
      "$SCRIPT_DIR/trademonke-update.sh"
    fi
  fi
fi

status_line "Validating docker compose config…"
$COMPOSE config >/dev/null
status_line "Running database migrations…"
$COMPOSE run --rm migrate
status_line "Starting Postgres, API, GUI, and market-data…"
$COMPOSE up -d postgres platform-api research-gui market-data
status_line "Verifying stack health…"
"$PY" scripts/verify_stack.py

port="$(gui_port "$ROOT")"
url="http://127.0.0.1:${port}/"
printf '%s\n' "$url" > "$ROOT/.trademonke-gui-url"
notify "TradeMonke" "Research workstation is running"
status_line "Research stack is running"
trademonke_log "START ready url=$url"

if [[ "$PRINT_URL" -eq 1 ]]; then
  echo "$url"
fi

if [[ "$NO_OPEN" -eq 1 ]]; then
  exit 0
fi

# Prefer Electron shell when installed; else browser.
PACKAGE_ELECTRON="${TRADEMONKE_PACKAGE_ROOT:-/usr/lib/trademonke}/desktop/node_modules/.bin/electron"
if [[ -x "$PACKAGE_ELECTRON" ]]; then
  (
    cd "$(dirname "$PACKAGE_ELECTRON")/../.."
    TRADEMONKE_ROOT="$ROOT" TRADEMONKE_SKIP_BOOT=1 TRADEMONKE_GUI_URL="$url" \
      TRADEMONKE_GUI_TOKEN="$(gui_token "$ROOT")" \
      "$PACKAGE_ELECTRON" . --no-sandbox
  ) &
elif [[ -x "$ROOT/desktop/node_modules/.bin/electron" ]]; then
  (
    cd "$ROOT/desktop"
    TRADEMONKE_ROOT="$ROOT" TRADEMONKE_SKIP_BOOT=1 TRADEMONKE_GUI_URL="$url" \
      TRADEMONKE_GUI_TOKEN="$(gui_token "$ROOT")" \
      ./node_modules/.bin/electron . --no-sandbox
  ) &
elif command -v xdg-open >/dev/null 2>&1; then
  xdg-open "$url" >/dev/null 2>&1 || true
fi
