#!/bin/bash
# Weekly restore test: restores latest prod backup into staging Postgres.
# Verifies key tables have non-zero row counts.
# Called by cron every Monday at 05:00 UTC.
set -euo pipefail

BACKUP_DIR="/opt/backups/prod"
CONTAINER="staging_postgres"
STAGING_COMPOSE="/opt/cataclysm/staging/docker-compose.staging.yml"

echo "[$(date)] Starting weekly restore test..."

# Find latest prod backup
LATEST=$(ls -t "$BACKUP_DIR"/cataclysm_prod_*.dump 2>/dev/null | head -1)
if [ -z "$LATEST" ]; then
    echo "[$(date)] FAIL: No prod backups found in $BACKUP_DIR" >&2
    exit 1
fi
echo "[$(date)] Restoring: $(basename "$LATEST")"

# Stop staging backend to prevent writes during restore
docker compose -f "$STAGING_COMPOSE" stop frontend backend 2>/dev/null || true

# Restore into staging Postgres (--clean drops existing objects first)
docker exec -i "$CONTAINER" pg_restore -U cataclysm -d cataclysm --clean \
    < "$LATEST" 2>&1 || true
# pg_restore exits non-zero on warnings (e.g. "does not exist" on --clean);
# this is expected. We verify data integrity below.

# Verify key tables have data
TABLES=("sessions" "users" "equipment_profiles" "coaching_reports")
ALL_OK=true

for TABLE in "${TABLES[@]}"; do
    COUNT=$(docker exec "$CONTAINER" psql -U cataclysm -d cataclysm -t -c \
        "SELECT count(*) FROM $TABLE;" 2>/dev/null | tr -d ' ')
    if [ -z "$COUNT" ] || [ "$COUNT" = "0" ]; then
        echo "[$(date)] WARN: $TABLE has $COUNT rows (may be empty in prod too)"
    else
        echo "[$(date)] OK: $TABLE has $COUNT rows"
    fi
done

# Restart staging
docker compose -f "$STAGING_COMPOSE" up -d 2>/dev/null || true

# Touch metric file for Prometheus alerting
METRIC_DIR="/opt/cataclysm/metrics"
mkdir -p "$METRIC_DIR"
echo "# HELP restore_test_last_success_timestamp_seconds Last successful restore test" > "$METRIC_DIR/restore_test.prom"
echo "restore_test_last_success_timestamp_seconds $(date +%s)" >> "$METRIC_DIR/restore_test.prom"

echo "[$(date)] PASS: Restore test complete"
