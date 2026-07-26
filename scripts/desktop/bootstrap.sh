#!/usr/bin/env bash
# First-run / packaged bootstrap for TradeMonke desktop.
# Usage:
#   bootstrap.sh --check                 # exit 0 if ready, 1 if bootstrap needed
#   bootstrap.sh [--package] [--skip-images] [--no-desktop-entry]
#   bootstrap.sh --user-only             # clone/venv/images only (Docker already present)
#   bootstrap.sh /path/to/checkout       # developer copy from local tree
#
# Privileged steps (apt/Docker/Node) require root. User steps run as SUDO_USER when elevated.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

PACKAGE_MODE=0
SKIP_IMAGES=0
NO_DESKTOP_ENTRY=0
USER_ONLY=0
CHECK_ONLY=0
SOURCE_ARG=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --check) CHECK_ONLY=1; shift ;;
    --package) PACKAGE_MODE=1; shift ;;
    --skip-images) SKIP_IMAGES=1; shift ;;
    --no-desktop-entry) NO_DESKTOP_ENTRY=1; shift ;;
    --user-only) USER_ONLY=1; shift ;;
    --source)
      SOURCE_ARG="${2:-}"
      shift 2
      ;;
    -*)
      echo "Unknown option: $1" >&2
      exit 2
      ;;
    *)
      SOURCE_ARG="$1"
      shift
      ;;
  esac
done

INSTALL_ROOT="${TRADEMONKE_INSTALL_ROOT:-$TRADEMONKE_DEFAULT_INSTALL_ROOT}"
USER_NAME="${SUDO_USER:-${TRADEMONKE_USER:-$USER}}"
if [[ "$PACKAGE_MODE" -eq 1 ]]; then
  REPO_URL="$(trademonke_repo_url require)"
else
  REPO_URL="$(trademonke_repo_url)"
fi

if [[ "$CHECK_ONLY" -eq 1 ]]; then
  if needs_bootstrap "$INSTALL_ROOT"; then
    exit 1
  fi
  exit 0
fi

run_privileged() {
  status_line "Installing prerequisites (Docker, Node.js, system packages)…"
  ensure_apt_packages
  ensure_docker
  ensure_nodejs
  ensure_docker_group "$USER_NAME"
}

run_user_stack() {
  if [[ -n "$SOURCE_ARG" ]]; then
    status_line "Installing from local source $SOURCE_ARG"
    SOURCE_ARG="$(cd "$SOURCE_ARG" && pwd)"
    mkdir -p "$(dirname "$INSTALL_ROOT")"
    if [[ "$SOURCE_ARG" != "$INSTALL_ROOT" ]]; then
      if [[ "$(id -u)" -eq 0 ]]; then
        rm -rf "$INSTALL_ROOT"
        cp -a "$SOURCE_ARG" "$INSTALL_ROOT"
        chown -R "$USER_NAME:$USER_NAME" "$INSTALL_ROOT"
      else
        rsync -a --delete --exclude '.venv' --exclude 'runtime' --exclude 'node_modules' \
          --exclude 'gui/node_modules' --exclude 'desktop/node_modules' \
          "$SOURCE_ARG/" "$INSTALL_ROOT/"
      fi
    fi
    if [[ "$PACKAGE_MODE" -eq 1 && ! -d "$INSTALL_ROOT/.git" ]]; then
      dialog_error "Package mode requires a git clone. Set TRADEMONKE_REPO_URL instead of --source."
      exit 2
    fi
  elif [[ -n "$REPO_URL" ]]; then
    ensure_clone "$INSTALL_ROOT" "$REPO_URL" "$USER_NAME" "$PACKAGE_MODE"
    if [[ "$(id -u)" -eq 0 ]]; then
      chown -R "$USER_NAME:$USER_NAME" "$INSTALL_ROOT"
    fi
  else
    # Dev fallback: rsync from the tree containing this script (non-package only).
    local here
    here="$(cd "$SCRIPT_DIR/../.." && pwd)"
    status_line "No TRADEMONKE_REPO_URL set; copying local tree (git updates disabled)"
    mkdir -p "$(dirname "$INSTALL_ROOT")"
    if [[ "$here" != "$INSTALL_ROOT" ]]; then
      if [[ "$(id -u)" -eq 0 ]]; then
        rsync -a --delete --exclude '.venv' --exclude 'runtime' --exclude 'node_modules' \
          --exclude 'gui/node_modules' --exclude 'desktop/node_modules' \
          "$here/" "$INSTALL_ROOT/"
        chown -R "$USER_NAME:$USER_NAME" "$INSTALL_ROOT"
      else
        rsync -a --delete --exclude '.venv' --exclude 'runtime' --exclude 'node_modules' \
          --exclude 'gui/node_modules' --exclude 'desktop/node_modules' \
          "$here/" "$INSTALL_ROOT/"
      fi
    fi
  fi

  ensure_venv "$INSTALL_ROOT" "$USER_NAME"
  ensure_electron_deps "$INSTALL_ROOT" "$USER_NAME" || true

  if [[ "$SKIP_IMAGES" -eq 0 ]]; then
    build_images "$INSTALL_ROOT" "$USER_NAME"
  else
    status_line "Skipping image build (will run on first launch)"
  fi

  if [[ "$NO_DESKTOP_ENTRY" -eq 0 ]]; then
    if [[ "$(id -u)" -eq 0 || -n "$USER_NAME" ]]; then
      install_user_desktop_entry "$INSTALL_ROOT" "$USER_NAME" || true
    fi
  fi
}

if [[ "$USER_ONLY" -eq 1 ]]; then
  if ! command -v docker >/dev/null 2>&1; then
    dialog_error "Docker is not installed. Re-run bootstrap without --user-only (requires sudo)."
    exit 2
  fi
  if ! docker info >/dev/null 2>&1; then
    dialog_error "Cannot access the Docker daemon. Start Docker and ensure your user is in the docker group (re-login after install)."
    exit 2
  fi
  run_user_stack
  status_line "Bootstrap complete"
  exit 0
fi

install_root_writable() {
  local root="$1"
  if [[ -d "$root" && -w "$root" ]]; then
    return 0
  fi
  local parent
  parent="$(dirname "$root")"
  [[ -d "$parent" && -w "$parent" ]]
}

# Full bootstrap: elevate for privileged steps when needed.
if [[ "$(id -u)" -ne 0 ]]; then
  NEED_ELEVATE=0
  if ! command -v docker >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
    NEED_ELEVATE=1
  fi
  if ! install_root_writable "$INSTALL_ROOT"; then
    NEED_ELEVATE=1
  fi
  if [[ "$NEED_ELEVATE" -eq 1 ]]; then
    status_line "Elevating to prepare /opt/trademonke and system dependencies…"
    EXTRA_ARGS=()
    [[ "$PACKAGE_MODE" -eq 1 ]] && EXTRA_ARGS+=(--package)
    [[ "$SKIP_IMAGES" -eq 1 ]] && EXTRA_ARGS+=(--skip-images)
    [[ "$NO_DESKTOP_ENTRY" -eq 1 ]] && EXTRA_ARGS+=(--no-desktop-entry)
    [[ -n "$SOURCE_ARG" ]] && EXTRA_ARGS+=(--source "$SOURCE_ARG")
    if command -v pkexec >/dev/null 2>&1; then
      exec pkexec env \
        TRADEMONKE_REPO_URL="${TRADEMONKE_REPO_URL:-}" \
        TRADEMONKE_INSTALL_ROOT="$INSTALL_ROOT" \
        TRADEMONKE_PACKAGE_ROOT="${TRADEMONKE_PACKAGE_ROOT:-/usr/lib/trademonke}" \
        TRADEMONKE_USER="$USER_NAME" \
        bash "$0" "${EXTRA_ARGS[@]}"
    fi
    exec sudo \
      TRADEMONKE_REPO_URL="${TRADEMONKE_REPO_URL:-}" \
      TRADEMONKE_INSTALL_ROOT="$INSTALL_ROOT" \
      TRADEMONKE_PACKAGE_ROOT="${TRADEMONKE_PACKAGE_ROOT:-/usr/lib/trademonke}" \
      TRADEMONKE_USER="$USER_NAME" \
      bash "$0" "${EXTRA_ARGS[@]}"
  fi
  run_user_stack
  status_line "Bootstrap complete"
  exit 0
fi

run_privileged
run_user_stack
status_line "Bootstrap complete"

cat <<EOF

TradeMonke installed at $INSTALL_ROOT

Next steps:
  1. Log out and back in (or run: newgrp docker) so Docker group membership applies.
  2. Open "TradeMonke" from the app menu, or run: trademonke
  3. GUI token is in $INSTALL_ROOT/.env (PLATFORM_GUI_ACCESS_TOKEN)

Data and secrets persist under $INSTALL_ROOT/.env and $INSTALL_ROOT/runtime/
Dry-run / spot only — this is not a live trading installer.

EOF
