#!/usr/bin/env bash
# backup-pg.sh — nightly logical backup of the agritwin database.
# Keeps the last 7 dumps. Add to ubuntu's crontab:
#   0 2 * * * /opt/agritwin/deploy/scripts/backup-pg.sh >> /var/log/agritwin-backup.log 2>&1
set -euo pipefail

BACKUP_DIR=/opt/agritwin-data/backups
DATE=$(date +%Y%m%d_%H%M%S)
OUT="${BACKUP_DIR}/agritwin_${DATE}.pgdump"

echo "[backup] Dumping agritwin database..."
docker exec infra-db-1 pg_dump \
  -U agritwin \
  -Fc \
  agritwin > "$OUT"

SIZE=$(du -sh "$OUT" | cut -f1)
echo "[backup] Written: ${OUT} (${SIZE})"

# Prune: keep 7 most recent dumps
PRUNED=$(ls -1t "${BACKUP_DIR}"/agritwin_*.pgdump | tail -n +8)
if [ -n "$PRUNED" ]; then
  echo "$PRUNED" | xargs rm
  echo "[backup] Pruned old dumps."
fi

# Restore: docker exec -i infra-db-1 pg_restore -U agritwin -d agritwin < <dumpfile>
