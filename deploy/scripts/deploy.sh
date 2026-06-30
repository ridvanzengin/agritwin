#!/usr/bin/env bash
# deploy.sh — pull latest code for all three repos, rebuild app image, run migrations, reload services.
# Does NOT restart the infra project (db/redis/nginx stay up during deploys).
# Run from: /opt/agritwin
set -euo pipefail

cd /opt/agritwin

echo "[deploy] Pulling latest code..."
git pull origin main
git -C agriTwin-app pull origin main
git -C agriTwin-etl pull origin main

echo "[deploy] Building app image..."
docker compose -p agritwin \
  -f deploy/agritwin/docker-compose.prod.yml \
  build web

echo "[deploy] Running migrations..."
docker compose -p agritwin \
  -f deploy/agritwin/docker-compose.prod.yml \
  run --rm migrate

echo "[deploy] Restarting web and celery_worker..."
docker compose -p agritwin \
  -f deploy/agritwin/docker-compose.prod.yml \
  up -d --no-deps web celery_worker

echo "[deploy] Done."
docker compose -p agritwin -f deploy/agritwin/docker-compose.prod.yml ps
