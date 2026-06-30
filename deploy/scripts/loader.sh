#!/usr/bin/env bash
# loader.sh — run the 6-stage ETL data load into PostgreSQL.
# Safe to re-run: load.sh skips tables that already have rows.
# Run after migrations complete and before starting the web service for the first time.
# Run from: /opt/agritwin
set -euo pipefail

cd /opt/agritwin

# Load .env.prod to get AGRITWIN_DB_PASSWORD
set -o allexport
source deploy/agritwin/.env.prod
set +o allexport

echo "[loader] Starting 6-stage ETL load (~10 min)..."
echo "[loader] Map page live after Stage 3, suitability after Stage 4, full detail after Stage 5."

docker run --rm \
  --network infra_proxy \
  --env-file deploy/agritwin/.env.prod \
  -e DATABASE_URL="postgresql+psycopg://agritwin:${AGRITWIN_DB_PASSWORD}@infra-db-1:5432/agritwin" \
  -e CELERY_BROKER_URL="redis://infra-redis-1:6379/0" \
  -e CELERY_RESULT_BACKEND="redis://infra-redis-1:6379/0" \
  -v /opt/agritwin-data/etl-processed:/agritwin-etl/data/processed \
  agritwin-app:latest \
  /app/load.sh

echo "[loader] Done."
