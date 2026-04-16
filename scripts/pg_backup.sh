#!/bin/bash
# PostgreSQL backup for Cataclysm Hetzner deployment.
# Usage: pg_backup.sh <prod|staging>
# Called by cron twice daily (03:00 and 15:00 UTC).
set -euo pipefail

ENV="${1:?Usage: pg_backup.sh <prod|staging>}"
BACKUP_DIR="/opt/backups/$ENV"
CONTAINER="${ENV}_postgres"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
FILENAME="cataclysm_${ENV}_${TIMESTAMP}.dump"
RETENTION_DAYS=14

mkdir -p "$BACKUP_DIR"

echo "[$(date)] Starting $ENV PostgreSQL backup..."

docker exec "$CONTAINER" pg_dump -U cataclysm -Fc cataclysm \
    > "$BACKUP_DIR/$FILENAME"

# Verify dump is non-empty
if [ ! -s "$BACKUP_DIR/$FILENAME" ]; then
    echo "[$(date)] ERROR: Backup file is empty!" >&2
    rm -f "$BACKUP_DIR/$FILENAME"
    exit 1
fi

BACKUP_SIZE=$(du -h "$BACKUP_DIR/$FILENAME" | cut -f1)
echo "[$(date)] Backup complete: $FILENAME ($BACKUP_SIZE)"

# Rotate old backups
DELETED=$(find "$BACKUP_DIR" -name "cataclysm_${ENV}_*.dump" -mtime +"$RETENTION_DAYS" -delete -print | wc -l)
if [ "$DELETED" -gt 0 ]; then
    echo "[$(date)] Removed $DELETED backup(s) older than $RETENTION_DAYS days"
fi

# Offsite sync to Backblaze B2 (if rclone is configured)
if command -v rclone &>/dev/null && rclone listremotes | grep -q "^b2:"; then
    echo "[$(date)] Syncing to B2..."
    rclone sync "$BACKUP_DIR" "b2:cataclysm-backups/$ENV" \
        --transfers 1 \
        --log-level NOTICE
    echo "[$(date)] B2 sync complete"
else
    echo "[$(date)] WARN: rclone/B2 not configured, skipping offsite sync"
fi

# Touch metric file for Prometheus alerting
METRIC_DIR="/opt/cataclysm/metrics"
mkdir -p "$METRIC_DIR"
echo "# HELP backup_last_success_timestamp_seconds Last successful backup" > "$METRIC_DIR/backup_${ENV}.prom"
echo "backup_last_success_timestamp_seconds $(date +%s)" >> "$METRIC_DIR/backup_${ENV}.prom"
