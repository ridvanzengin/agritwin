#!/usr/bin/env bash
# deploy.sh — pull latest code for all three repos, rebuild app image, run migrations, reload services.
# Does NOT restart the infra project (db/redis/nginx stay up during deploys).
# Run from: /opt/agritwin
set -euo pipefail

cd /opt/agritwin

# Shorthand so every compose command gets the same env-file, project, and compose file.
# --env-file is required for ${AGRITWIN_DB_PASSWORD} to be interpolated in docker-compose.prod.yml.
COMPOSE="docker compose -p agritwin --env-file deploy/agritwin/.env.prod -f deploy/agritwin/docker-compose.prod.yml"

echo "[deploy] Pulling latest code..."
git pull origin master
git -C agriTwin-app pull origin main
git -C agriTwin-etl pull origin main

echo "[deploy] Building app image..."
$COMPOSE build migrate

echo "[deploy] Running migrations..."
$COMPOSE run --rm migrate

echo "[deploy] Restarting web and celery_worker..."
$COMPOSE up -d --no-deps web celery_worker

echo "[deploy] Done."
$COMPOSE ps
