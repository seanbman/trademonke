#!/usr/bin/env bash
set -euo pipefail
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}"
BACKUP_ROOT="${BACKUP_ROOT:-./runtime/backups}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"
mkdir -p "$BACKUP_ROOT"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
docker compose exec -T postgres pg_dump -U "${POSTGRES_USER:-trading}" -d "${POSTGRES_DB:-trading_platform}" -Fc > "$BACKUP_ROOT/platform-$stamp.dump"
find "$BACKUP_ROOT" -type f -name 'platform-*.dump' -mtime "+$RETENTION_DAYS" -delete

