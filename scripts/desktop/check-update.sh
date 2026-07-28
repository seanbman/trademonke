#!/usr/bin/env bash
# Exit 0 if origin/main is ahead of HEAD; exit 1 if current; exit 2 on error.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"
ROOT="$(trademonke_root)"
cd "$ROOT"

if [[ ! -d .git ]]; then
  echo "not-a-git-clone"
  exit 2
fi

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "not-a-git-clone"
  exit 2
fi

origin_url="$(git remote get-url origin 2>/dev/null || true)"
if [[ -z "$origin_url" ]]; then
  echo "no-origin-remote"
  exit 2
fi

timeout_secs="${TRADEMONKE_UPDATE_TIMEOUT:-10}"
if ! timeout "$timeout_secs" git fetch origin main --quiet 2>/dev/null; then
  echo "fetch-failed origin=${origin_url}"
  exit 2
fi

local_sha="$(git rev-parse HEAD)"
remote_sha="$(git rev-parse origin/main 2>/dev/null || true)"
if [[ -z "$remote_sha" ]]; then
  echo "no-origin-main origin=${origin_url}"
  exit 2
fi

if [[ "$local_sha" == "$remote_sha" ]]; then
  echo "current $local_sha"
  exit 1
fi

echo "available local=$local_sha remote=$remote_sha origin=${origin_url}"
exit 0
