#!/usr/bin/env bash
# Stop research containers without wiping volumes.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"
ROOT="$(trademonke_root)"
cd "$ROOT"
COMPOSE="$(compose_cmd)" || { dialog_error "Docker Compose is unavailable."; exit 2; }
$COMPOSE stop platform-api research-gui market-data postgres 2>/dev/null || true
notify "TradeMonke" "Research workstation stopped"
