#!/usr/bin/env bash
# Install TradeMonke on Ubuntu: Docker, git clone to /opt/trademonke, desktop entry.
# Usage:
#   TRADEMONKE_REPO_URL=https://github.com/ORG/trademonke.git ./scripts/desktop/install-ubuntu.sh
#   ./scripts/desktop/install-ubuntu.sh /path/to/existing/checkout   # developer copy
#   TRADEMONKE_PACKAGE_MODE=1 ./scripts/desktop/install-ubuntu.sh    # packaged: require git clone
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PACKAGE_ARGS=()
if [[ "${TRADEMONKE_PACKAGE_MODE:-0}" == "1" ]]; then
  PACKAGE_ARGS+=(--package)
fi

# Full install including image build (developer / script path).
exec bash "$SCRIPT_DIR/bootstrap.sh" "${PACKAGE_ARGS[@]}" "$@"
