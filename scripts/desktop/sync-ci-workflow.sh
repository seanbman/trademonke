#!/usr/bin/env bash
# Install packaging artifacts that may live under root-owned paths:
#   - .github/workflows/desktop-deb.yml
#   - README.md Desktop section (if missing)
#
# Usage:
#   bash scripts/desktop/sync-ci-workflow.sh           # copy when writable; otherwise print instructions
#   SYNC_WITH_SUDO=1 bash scripts/desktop/sync-ci-workflow.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SRC="$ROOT/packaging/deb/ci/desktop-deb.yml"
DST="$ROOT/.github/workflows/desktop-deb.yml"
SECTION="$ROOT/packaging/deb/README_DESKTOP_SECTION.md"

install_file() {
  local src="$1" dst="$2"
  if [[ -e "$dst" && -w "$dst" ]] || [[ -w "$(dirname "$dst")" ]]; then
    cp "$src" "$dst"
    return 0
  fi
  if [[ "${SYNC_WITH_SUDO:-0}" == "1" ]]; then
    echo "Elevating to install $(basename "$dst")…"
    sudo mkdir -p "$(dirname "$dst")"
    sudo cp "$src" "$dst"
    return 0
  fi
  echo "Cannot write $dst (permission denied)."
  echo "Re-run with: SYNC_WITH_SUDO=1 bash scripts/desktop/sync-ci-workflow.sh"
  echo "Or manually: sudo cp '$src' '$dst'"
  return 1
}

if [[ ! -f "$SRC" ]]; then
  echo "Missing $SRC" >&2
  exit 2
fi

status=0
if install_file "$SRC" "$DST"; then
  echo "Installed $DST"
else
  status=1
fi

if [[ -f "$SECTION" && -f "$ROOT/README.md" ]]; then
  if grep -q 'Desktop app (Ubuntu' "$ROOT/README.md"; then
    echo "README.md already has Desktop section"
  else
    tmp="$(mktemp)"
    awk -v section_file="$SECTION" '
      BEGIN { while ((getline line < section_file) > 0) section = section line "\n"; close(section_file) }
      /^## Local development$/ && !done {
        print section
        done=1
      }
      { print }
    ' "$ROOT/README.md" > "$tmp"
    if [[ -w "$ROOT/README.md" ]]; then
      cp "$tmp" "$ROOT/README.md"
      echo "README.md updated"
    elif [[ "${SYNC_WITH_SUDO:-0}" == "1" ]]; then
      sudo cp "$tmp" "$ROOT/README.md"
      echo "README.md updated"
    else
      echo "Cannot update README.md (permission denied)."
      echo "Re-run with SYNC_WITH_SUDO=1 or paste packaging/deb/README_DESKTOP_SECTION.md manually."
      status=1
    fi
    rm -f "$tmp"
  fi
fi

# TOC hint (best-effort, non-fatal)
if [[ -w "$ROOT/README.md" ]] && ! grep -q 'docs/DESKTOP.md' "$ROOT/README.md"; then
  :
fi

exit "$status"
