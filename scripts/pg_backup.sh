#!/bin/bash
set -euo pipefail

BACKUP_DIR=/opt/backups
COMPOSE_FILE=/opt/cataclysm/docker-compose.prod.yml
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=7

mkdir -p "$BACKUP_DIR"

echo "[$(date)] Starting PostgreSQL backup..."

docker compose -f "$COMPOSE_FILE" exec -T postgres \
    pg_dump -U cataclysm -Fc cataclysm > "$BACKUP_DIR/cataclysm_$TIMESTAMP.dump"

# Verify backup isn't empty
if [ ! -s "$BACKUP_DIR/cataclysm_$TIMESTAMP.dump" ]; then
    echo "[$(date)] ERROR: Backup file is empty!"
    rm -f "$BACKUP_DIR/cataclysm_$TIMESTAMP.dump"
    exit 1
fi

BACKUP_SIZE=$(du -h "$BACKUP_DIR/cataclysm_$TIMESTAMP.dump" | cut -f1)
echo "[$(date)] Backup complete: cataclysm_$TIMESTAMP.dump ($BACKUP_SIZE)"

# Rotate old backups
DELETED=$(find "$BACKUP_DIR" -name "cataclysm_*.dump" -mtime +"$RETENTION_DAYS" -delete -print | wc -l)
echo "[$(date)] Removed $DELETED backup(s) older than $RETENTION_DAYS days"
