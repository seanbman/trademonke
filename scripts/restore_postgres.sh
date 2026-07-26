#!/usr/bin/env bash
set -euo pipefail
if [[ $# -ne 1 ]]; then echo "usage: $0 BACKUP.dump" >&2; exit 2; fi
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}"
docker compose exec -T postgres pg_restore --clean --if-exists --no-owner -U "${POSTGRES_USER:-trading}" -d "${POSTGRES_DB:-trading_platform}" < "$1"

