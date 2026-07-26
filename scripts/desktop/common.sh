#!/usr/bin/env bash
# Shared helpers for TradeMonke desktop launchers and bootstrap.
set -euo pipefail

# Default install location for packaged / Ubuntu desktop installs.
TRADEMONKE_DEFAULT_INSTALL_ROOT="${TRADEMONKE_DEFAULT_INSTALL_ROOT:-/opt/trademonke}"

# Packaged Electron + bootstrap live here when installed from the .deb.
TRADEMONKE_PACKAGE_ROOT="${TRADEMONKE_PACKAGE_ROOT:-/usr/lib/trademonke}"

trademonke_root() {
  if [[ -n "${TRADEMONKE_ROOT:-}" ]]; then
    printf '%s\n' "$TRADEMONKE_ROOT"
    return
  fi
  if [[ -f "${TRADEMONKE_DEFAULT_INSTALL_ROOT}/docker-compose.yml" ]]; then
    printf '%s\n' "$TRADEMONKE_DEFAULT_INSTALL_ROOT"
    return
  fi
  local here
  here="$(cd "$(dirname "${BASH_SOURCE[1]}")/../.." && pwd)"
  if [[ -f "$here/docker-compose.yml" ]]; then
    printf '%s\n' "$here"
    return
  fi
  printf '%s\n' "$TRADEMONKE_DEFAULT_INSTALL_ROOT"
}

trademonke_repo_url() {
  # Optional second arg: "require" → use packaged repo.url fallback from app.json.
  local require="${1:-}"
  if [[ -n "${TRADEMONKE_REPO_URL:-}" ]]; then
    printf '%s\n' "$TRADEMONKE_REPO_URL"
    return
  fi
  local candidate
  for candidate in \
    /etc/trademonke/repo.url \
    "${TRADEMONKE_PACKAGE_ROOT}/repo.url" \
    "$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/packaging/deb/repo.url"
  do
    if [[ -f "$candidate" ]]; then
      local url
      url="$(tr -d '[:space:]' < "$candidate")"
      if [[ -n "$url" ]]; then
        printf '%s\n' "$url"
        return
      fi
    fi
  done
  if [[ "$require" == "require" ]]; then
    # Fallback from app.json repository field (packaged installs only).
    printf '%s\n' "https://github.com/seanbman/trademonke.git"
    return
  fi
  printf '%s\n' ""
}

compose_cmd() {
  if docker compose version >/dev/null 2>&1; then
    echo "docker compose"
  elif docker-compose version >/dev/null 2>&1; then
    echo "docker-compose"
  else
    return 1
  fi
}

trademonke_log_dir() {
  printf '%s\n' "${TRADEMONKE_LOG_DIR:-${XDG_DATA_HOME:-$HOME/.local/share}/trademonke/logs/desktop}"
}

trademonke_ensure_log_dir() {
  local dir
  dir="$(trademonke_log_dir)"
  mkdir -p "$dir/errors"
  printf '%s\n' "$dir"
}

trademonke_log() {
  local dir message ts
  dir="$(trademonke_ensure_log_dir)"
  ts="$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
  message="$*"
  # File only by default — keep stdout clean for callers that capture paths.
  printf '%s %s\n' "$ts" "$message" >>"$dir/trademonke-desktop.log"
  if [[ "${TRADEMONKE_LOG_STDOUT:-0}" == "1" ]]; then
    printf '%s %s\n' "$ts" "$message"
  fi
}

trademonke_write_error_report() {
  # Args: title, then optional body on stdin or remaining args.
  local title="${1:-TradeMonke error}"
  shift || true
  local dir report stamp body
  dir="$(trademonke_ensure_log_dir)"
  stamp="$(date -u +'%Y%m%d-%H%M%S')"
  report="$dir/errors/${stamp}-error.log"
  {
    echo "=== TradeMonke error report ==="
    echo "utc: $(date -u +'%Y-%m-%dT%H:%M:%SZ')"
    echo "title: $title"
    echo "user: ${USER:-unknown}"
    echo "host: $(hostname 2>/dev/null || true)"
    echo "pwd: $(pwd 2>/dev/null || true)"
    echo "TRADEMONKE_ROOT: ${TRADEMONKE_ROOT:-}"
    echo "TRADEMONKE_PACKAGE_ROOT: ${TRADEMONKE_PACKAGE_ROOT:-}"
    echo "uname: $(uname -a 2>/dev/null || true)"
    echo
    echo "=== message ==="
    if [[ $# -gt 0 ]]; then
      printf '%s\n' "$*"
    else
      cat
    fi
    echo
    echo "=== docker context ==="
    timeout 5 docker context show 2>&1 || true
    echo
    echo "=== docker ps ==="
    timeout 8 docker ps -a --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' 2>&1 | head -40 || true
    echo
    if command -v docker >/dev/null 2>&1; then
      local root compose
      root="$(trademonke_root 2>/dev/null || true)"
      if [[ -n "$root" && -f "$root/docker-compose.yml" ]]; then
        compose="$(compose_cmd 2>/dev/null || true)"
        if [[ -n "$compose" ]]; then
          echo "=== compose ps ($root) ==="
          (cd "$root" && timeout 10 $compose ps -a) 2>&1 || true
          echo
          echo "=== compose logs (tail) ==="
          (cd "$root" && timeout 15 $compose logs --no-color --tail=80 platform-api research-gui market-data postgres migrate) 2>&1 || true
        fi
      fi
    fi
    echo
    echo "=== recent desktop log ==="
    tail -n 80 "$dir/trademonke-desktop.log" 2>/dev/null || true
  } >"$report"
  cp -f "$report" "$dir/latest-error.log"
  trademonke_log "ERROR_REPORT $report"
  # stdout is only the report path (for capture by Electron/tests/scripts).
  printf '%s\n' "$report"
}

notify() {
  local title="$1" body="$2"
  if command -v notify-send >/dev/null 2>&1; then
    notify-send --app-name=TradeMonke "$title" "$body" || true
  fi
  trademonke_log "NOTIFY $title: $body"
  printf '%s: %s\n' "$title" "$body"
}

dialog_error() {
  local message="$1"
  local report
  report="$(trademonke_write_error_report "dialog_error" "$message" 2>/dev/null || true)"
  if [[ "${TRADEMONKE_NONINTERACTIVE:-0}" != "1" && -n "${DISPLAY:-}" ]] && command -v zenity >/dev/null 2>&1; then
    if [[ -n "$report" ]]; then
      zenity --error --title="TradeMonke" --text="$message

Details saved to:
$report" || true
    else
      zenity --error --title="TradeMonke" --text="$message" || true
    fi
  elif [[ "${TRADEMONKE_NONINTERACTIVE:-0}" != "1" ]] && command -v notify-send >/dev/null 2>&1; then
    notify-send --urgency=critical --app-name=TradeMonke "TradeMonke" "$message" || true
  fi
  printf 'ERROR: %s\n' "$message" >&2
  if [[ -n "${report:-}" ]]; then
    printf 'ERROR_REPORT: %s\n' "$report" >&2
  fi
}

dialog_question() {
  local message="$1"
  if [[ "${TRADEMONKE_NONINTERACTIVE:-0}" != "1" && -n "${DISPLAY:-}" ]] && command -v zenity >/dev/null 2>&1; then
    zenity --question --title="TradeMonke" --text="$message" --ok-label="Update" --cancel-label="Later"
    return $?
  fi
  # Non-interactive / no zenity: Later.
  return 1
}

status_line() {
  # Electron bootstrap parses lines prefixed with STATUS:
  trademonke_log "STATUS $1" >/dev/null || true
  printf 'STATUS: %s\n' "$1"
}

ensure_env() {
  local root="$1"
  if [[ ! -f "$root/.env" ]]; then
    if [[ -f "$root/.env.example" ]]; then
      cp "$root/.env.example" "$root/.env"
      notify "TradeMonke" "Created .env from .env.example"
    else
      dialog_error "Missing .env and .env.example in $root"
      return 1
    fi
  fi
}

python_bin() {
  local root="$1"
  if [[ -x "$root/.venv/bin/python" ]]; then
    printf '%s\n' "$root/.venv/bin/python"
  else
    printf '%s\n' "python3"
  fi
}

gui_port() {
  local root="$1"
  local port
  port="$(grep -E '^PLATFORM_GUI_PORT=' "$root/.env" 2>/dev/null | head -1 | cut -d= -f2- || true)"
  printf '%s\n' "${port:-3000}"
}

gui_token() {
  local root="$1"
  grep -E '^PLATFORM_GUI_ACCESS_TOKEN=' "$root/.env" 2>/dev/null | head -1 | cut -d= -f2- || true
}

needs_bootstrap() {
  local root="${1:-$(trademonke_root)}"
  if [[ ! -f "$root/docker-compose.yml" ]]; then
    return 0
  fi
  if [[ ! -d "$root/.git" ]]; then
    return 0
  fi
  if ! command -v docker >/dev/null 2>&1; then
    return 0
  fi
  if ! docker info >/dev/null 2>&1; then
    return 0
  fi
  if [[ ! -f "$root/.env" ]]; then
    return 0
  fi
  return 1
}

ensure_apt_packages() {
  status_line "Installing system packages…"
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get install -y -qq ca-certificates curl git zenity libnotify-bin python3 python3-venv rsync
}

ensure_docker() {
  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    status_line "Docker Engine already installed"
    return 0
  fi
  status_line "Installing Docker Engine…"
  install -m 0755 -d /etc/apt/keyrings
  if [[ ! -f /etc/apt/keyrings/docker.asc ]]; then
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    chmod a+r /etc/apt/keyrings/docker.asc
  fi
  # shellcheck disable=SC1091
  . /etc/os-release
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -qq
  apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-compose-plugin
  systemctl enable --now docker 2>/dev/null || true
}

ensure_nodejs() {
  if command -v npm >/dev/null 2>&1; then
    local major
    major="$(node -v 2>/dev/null | sed 's/^v//' | cut -d. -f1 || echo 0)"
    if [[ "${major:-0}" -ge 18 ]]; then
      status_line "Node.js already installed (v$(node -v | sed 's/^v//'))"
      return 0
    fi
  fi
  status_line "Installing Node.js 20…"
  # shellcheck disable=SC1091
  . /etc/os-release
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
  apt-get install -y -qq nodejs
}

ensure_docker_group() {
  local user_name="${1:-}"
  if [[ -z "$user_name" || "$user_name" == "root" ]]; then
    return 0
  fi
  status_line "Adding $user_name to the docker group…"
  usermod -aG docker "$user_name" || true
}

ensure_clone() {
  local install_root="$1"
  local repo_url="$2"
  local user_name="${3:-}"
  local package_mode="${4:-0}"

  if [[ -z "$repo_url" ]]; then
    dialog_error "TRADEMONKE_REPO_URL is required for packaged installs (set env or /etc/trademonke/repo.url)."
    return 2
  fi

  if [[ -d "$install_root/.git" && -f "$install_root/docker-compose.yml" ]]; then
    status_line "Existing clone found; fetching origin/main"
    if [[ -n "$user_name" && "$(id -u)" -eq 0 && "$user_name" != "root" ]]; then
      sudo -u "$user_name" git -C "$install_root" fetch origin main || true
    else
      git -C "$install_root" fetch origin main || true
    fi
    return 0
  fi

  status_line "Cloning $repo_url → $install_root"
  # Keep the directory inode when it already exists (e.g. postinst created
  # /opt/trademonke owned by the user). Removing it would require write access
  # on /opt to recreate, which normal users do not have.
  if [[ -d "$install_root" ]]; then
    if [[ -d "$install_root/.git" ]]; then
      :
    elif [[ -n "$(ls -A "$install_root" 2>/dev/null || true)" ]]; then
      if [[ "$package_mode" == "1" ]]; then
        status_line "Clearing non-git contents in $install_root"
        if [[ -n "$user_name" && "$(id -u)" -eq 0 && "$user_name" != "root" ]]; then
          sudo -u "$user_name" bash -lc "find '$install_root' -mindepth 1 -maxdepth 1 -exec rm -rf {} +"
        else
          find "$install_root" -mindepth 1 -maxdepth 1 -exec rm -rf {} +
        fi
      else
        dialog_error "$install_root exists and is not empty/git. Choose another path or remove it."
        return 2
      fi
    fi
  else
    mkdir -p "$install_root"
    if [[ -n "$user_name" && "$(id -u)" -eq 0 && "$user_name" != "root" ]]; then
      chown "$user_name:$user_name" "$install_root"
    fi
  fi

  if [[ -n "$user_name" && "$(id -u)" -eq 0 && "$user_name" != "root" ]]; then
    sudo -u "$user_name" git clone --branch main "$repo_url" "$install_root"
  else
    git clone --branch main "$repo_url" "$install_root"
  fi
}

ensure_venv() {
  local install_root="$1"
  local user_name="${2:-}"
  status_line "Preparing Python venv + .env…"
  local runner=(bash -lc)
  if [[ -n "$user_name" && "$user_name" != "root" && "$(id -u)" -eq 0 ]]; then
    runner=(sudo -u "$user_name" bash -lc)
  fi
  # Keep pip output visible in the Electron progress window (no -q).
  "${runner[@]}" "
    set -e
    cd '$install_root'
    export PYTHONUNBUFFERED=1
    if [[ ! -f .env ]]; then cp .env.example .env; fi
    if [[ ! -d .venv ]]; then
      echo 'Creating Python virtualenv…'
      python3 -m venv .venv
    fi
    echo 'Upgrading pip…'
    .venv/bin/pip install -U pip
    if [[ -f requirements.txt ]]; then
      echo 'Installing Python requirements…'
      .venv/bin/pip install -r requirements.txt
    fi
    echo 'Preparing .env / Docker Desktop paths…'
    .venv/bin/python scripts/prepare_env.py --quiet || .venv/bin/python scripts/prepare_env.py
  "
  status_line "Python environment ready"
}

build_images() {
  local install_root="$1"
  local user_name="${2:-}"
  status_line "Building Docker images (research stack)…"
  local runner=(bash -lc)
  if [[ -n "$user_name" && "$user_name" != "root" && "$(id -u)" -eq 0 ]]; then
    runner=(sudo -u "$user_name" bash -lc)
  fi
  # BUILDKIT_PROGRESS=plain keeps layer output readable in the Electron console
  # (TTY progress bars do not stream cleanly over pipes).
  "${runner[@]}" "
    set -e
    cd '$install_root'
    export BUILDKIT_PROGRESS=plain COMPOSE_PROGRESS=plain PYTHONUNBUFFERED=1
    if docker compose version >/dev/null 2>&1; then
      docker compose --progress=plain build postgres platform-api research-gui market-data \
        || docker compose --progress=plain build
    else
      docker-compose build postgres platform-api research-gui market-data || docker-compose build
    fi
  "
  status_line "Docker images ready"
}

install_user_desktop_entry() {
  local install_root="$1"
  local user_name="$2"
  local user_home
  user_home="$(getent passwd "$user_name" | cut -d: -f6)"
  status_line "Installing per-user desktop entry…"
  local app_dir="$user_home/.local/share/applications"
  local icon_dir="$user_home/.local/share/icons"
  local bin_dir="$user_home/.local/bin"
  mkdir -p "$app_dir" "$icon_dir" "$bin_dir"
  local icon_src=""
  for candidate in \
    "$install_root/desktop/assets/trade-monke-icon.png" \
    "${TRADEMONKE_PACKAGE_ROOT}/desktop/assets/trade-monke-icon.png" \
    "$install_root/desktop/assets/trademonke.png" \
    "${TRADEMONKE_PACKAGE_ROOT}/desktop/assets/trademonke.png"
  do
    if [[ -f "$candidate" ]]; then
      icon_src="$candidate"
      break
    fi
  done
  if [[ -z "$icon_src" ]]; then
    dialog_error "TradeMonke icon missing under desktop/assets/"
    return 1
  fi
  cp "$icon_src" "$icon_dir/trademonke.png"
  local desktop_src="$install_root/desktop/trademonke.desktop"
  if [[ ! -f "$desktop_src" ]]; then
    desktop_src="${TRADEMONKE_PACKAGE_ROOT}/desktop/trademonke.desktop"
  fi
  local launch="$install_root/scripts/desktop/trademonke-launch.sh"
  if [[ -x /usr/bin/trademonke ]]; then
    launch=/usr/bin/trademonke
  elif [[ -x "${TRADEMONKE_PACKAGE_ROOT}/bin/trademonke" ]]; then
    launch="${TRADEMONKE_PACKAGE_ROOT}/bin/trademonke"
  fi
  sed "s|@TRADEMONKE_ROOT@|$install_root|g; s|@ICON@|$icon_dir/trademonke.png|g; s|@LAUNCH@|$launch|g" \
    "$desktop_src" > "$app_dir/trademonke.desktop"
  chmod +x "$app_dir/trademonke.desktop"
  ln -sfn "$install_root/scripts/desktop/trademonke-start.sh" "$bin_dir/trademonke"
  ln -sfn "$install_root/scripts/desktop/trademonke-stop.sh" "$bin_dir/trademonke-stop"
  chmod +x "$install_root/scripts/desktop/"*.sh 2>/dev/null || true
  chown -R "$user_name:$user_name" "$app_dir/trademonke.desktop" "$icon_dir/trademonke.png" \
    "$bin_dir/trademonke" "$bin_dir/trademonke-stop"
  update-desktop-database "$app_dir" 2>/dev/null || true
}

ensure_electron_deps() {
  local install_root="$1"
  local user_name="${2:-}"
  if ! command -v npm >/dev/null 2>&1; then
    dialog_error "npm is required for the Electron desktop shell."
    return 2
  fi
  # Prefer packaged Electron under /usr/lib/trademonke/desktop when present.
  if [[ -x "${TRADEMONKE_PACKAGE_ROOT}/desktop/node_modules/.bin/electron" ]]; then
    status_line "Using packaged Electron shell"
    return 0
  fi
  status_line "Installing Electron shell dependencies…"
  local runner=(bash -lc)
  if [[ -n "$user_name" && "$user_name" != "root" && "$(id -u)" -eq 0 ]]; then
    runner=(sudo -u "$user_name" bash -lc)
  fi
  "${runner[@]}" "cd '$install_root/desktop' && npm install --omit=dev"
}
