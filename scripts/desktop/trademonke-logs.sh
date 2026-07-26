#!/usr/bin/env bash
# Follow service logs and show where desktop error reports live.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"
ROOT="$(trademonke_root)"
cd "$ROOT"
LOG_DIR="$(trademonke_ensure_log_dir)"

echo "Desktop logs: $LOG_DIR"
echo "Latest error: $LOG_DIR/latest-error.log"
if [[ -f "$LOG_DIR/latest-error.log" ]]; then
  echo "---- latest-error.log (head) ----"
  head -n 40 "$LOG_DIR/latest-error.log" || true
  echo "--------------------------------"
fi

COMPOSE="$(compose_cmd)" || { dialog_error "Docker Compose is unavailable."; exit 2; }
exec $COMPOSE logs -f --tail=200 platform-api research-gui market-data
