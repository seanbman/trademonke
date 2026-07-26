#!/usr/bin/env bash
# Desktop entry entrypoint: prefer packaged/local Electron shell, else start + browser.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

ROOT="$(trademonke_root)"
export TRADEMONKE_ROOT="$ROOT"

PACKAGE_DESKTOP="${TRADEMONKE_PACKAGE_ROOT}/desktop"
LOCAL_ELECTRON="$ROOT/desktop/node_modules/.bin/electron"
PACKAGE_ELECTRON="$PACKAGE_DESKTOP/node_modules/.bin/electron"

# First-run bootstrap when the install tree is incomplete.
if needs_bootstrap "$ROOT"; then
  BOOTSTRAP="$SCRIPT_DIR/bootstrap.sh"
  if [[ ! -x "$BOOTSTRAP" && -x "${TRADEMONKE_PACKAGE_ROOT}/scripts/desktop/bootstrap.sh" ]]; then
    BOOTSTRAP="${TRADEMONKE_PACKAGE_ROOT}/scripts/desktop/bootstrap.sh"
  fi
  PACKAGE_FLAG=()
  if [[ -f /etc/trademonke/repo.url || -f "${TRADEMONKE_PACKAGE_ROOT}/repo.url" ]]; then
    PACKAGE_FLAG+=(--package)
  fi
  bash "$BOOTSTRAP" "${PACKAGE_FLAG[@]}"
  ROOT="$(trademonke_root)"
  export TRADEMONKE_ROOT="$ROOT"
fi

if [[ -x "$PACKAGE_ELECTRON" ]]; then
  cd "$PACKAGE_DESKTOP"
  exec env TRADEMONKE_ROOT="$ROOT" TRADEMONKE_PACKAGE_ROOT="$TRADEMONKE_PACKAGE_ROOT" \
    "$PACKAGE_ELECTRON" . --no-sandbox
fi

if [[ -x "$LOCAL_ELECTRON" ]]; then
  cd "$ROOT/desktop"
  exec env TRADEMONKE_ROOT="$ROOT" "$LOCAL_ELECTRON" . --no-sandbox
fi

exec "$SCRIPT_DIR/trademonke-start.sh"
