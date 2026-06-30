# AgriTwin — Production Deployment Roadmap
# Hetzner CX33 — Ubuntu 22.04 LTS (x86_64)
# Server: ringo — 167.233.143.105

## Server Details

| | |
|---|---|
| Provider | Hetzner Cloud |
| Name | ringo |
| Public IPv4 | 167.233.143.105 |
| IPv6 | 2a01:4f8:c015:eae0::/64 |
| Shape | CX33 — 4 vCPU / 8 GB RAM / 80 GB disk |
| OS | Ubuntu 22.04 LTS |
| SSH user | root |
| SSH key | ~/.ssh/id_ed25519_personal |

```bash
# Connect
ssh -i ~/.ssh/id_ed25519_personal root@167.233.143.105
```

---

## Architecture

```
Internet (80/443)
       |
  [Nginx container]  ← "infra" compose project; owns the shared Docker network
       |          \
[agritwin web]  [app2 web]  ← each in its own compose project
       |
[Shared PostgreSQL]  ← one DB per app
[Shared Redis]       ← one Redis DB index per app (agritwin=0, app2=1)
```

All services share a single external Docker network (`infra_proxy`). The infra project
owns that network. Each app project joins it as an external network.

---

## Phase 1 — Done ✅

Server is provisioned. Hetzner cloud firewall should allow:
- TCP 22 inbound (your IP only, for SSH)
- TCP 80 inbound (0.0.0.0/0, HTTP for certbot + redirect)
- TCP 443 inbound (0.0.0.0/0, HTTPS)

---

## Phase 2 — Done ✅ — VM Base Setup

```bash
ssh -i ~/.ssh/id_ed25519_personal root@167.233.143.105

# Update system
apt-get update && apt-get upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sh

# Install utilities
apt-get install -y git nano

# Create data directories (all on the single 80 GB disk — no separate volume on Hetzner CX33)
mkdir -p /opt/agritwin-data/{pgdata,etl-processed,backups}
# timescaledb-ha runs as UID 1000; pgdata must be owned by UID 1000
chown -R 1000:1000 /opt/agritwin-data/pgdata

# Clone the monorepo
git clone https://github.com/YOUR_ORG/agritwin.git /opt/agritwin
```

### Transfer ETL Parquet data (from your local machine, run once)

```bash
# From your LOCAL machine:
rsync -avz --progress -e "ssh -i ~/.ssh/id_ed25519_personal" \
  /Users/ridvan/personal/agritwin/agriTwin-etl/data/processed/ \
  root@167.233.143.105:/opt/agritwin-data/etl-processed/
```

---

## Phase 3 — Done ✅ — Infrastructure Compose (Nginx + PostgreSQL + Redis)

```bash
# On the server:
cd /opt/agritwin

# Set the PostgreSQL superuser password
cp deploy/infra/.env.example deploy/infra/.env
nano deploy/infra/.env  # set POSTGRES_SUPERUSER_PASSWORD

# Start infra (HTTP-only nginx first — HTTPS comes after certbot in Phase 7)
# The HTTPS block in deploy/infra/nginx/conf.d/agritwin.conf is already commented out
docker compose -p infra -f deploy/infra/docker-compose.yml up -d

# Verify all three are healthy
docker compose -p infra ps
```

### Create the agritwin database and user (run once)

```bash
docker exec -it infra-db-1 psql -U postgres <<'SQL'
  CREATE DATABASE agritwin;
  CREATE USER agritwin WITH PASSWORD 'CHANGE_ME';
  GRANT ALL PRIVILEGES ON DATABASE agritwin TO agritwin;
  \c agritwin
  CREATE EXTENSION IF NOT EXISTS postgis;
  CREATE EXTENSION IF NOT EXISTS timescaledb;
SQL
```

---

## Phase 4 — Done ✅ — Build App Image + Run Migrations

```bash
cd /opt/agritwin

# Set production secrets
cp deploy/agritwin/.env.prod.example deploy/agritwin/.env.prod
nano deploy/agritwin/.env.prod
# AGRITWIN_DB_PASSWORD — must match what you set in Phase 3
# FLASK_SECRET_KEY — generate with: python3 -c "import secrets; print(secrets.token_hex(32))"

# Build image (build context is the monorepo root)
docker compose -p agritwin -f deploy/agritwin/docker-compose.prod.yml build

# Run migrations (one-shot, exits when done)
docker compose -p agritwin -f deploy/agritwin/docker-compose.prod.yml run --rm migrate

# Verify both Alembic chains ran:
docker exec infra-db-1 psql -U agritwin -d agritwin \
  -c "SELECT 'etl', version_num FROM alembic_version \
      UNION ALL SELECT 'app', version_num FROM alembic_version_app;"
# Expect two rows
```

---

## Phase 5 — Done ✅ — ETL Data Load (one-time, ~5 min)

```bash
bash /opt/agritwin/deploy/scripts/loader.sh

# OR faster alternative — restore a pg_dump from your local machine instead:
# Local:  docker exec agritwin-db-1 pg_dump -U agritwin -Fc agritwin > agritwin_full.pgdump
# Ship:   rsync -avz -e "ssh -i ~/.ssh/id_ed25519_personal" agritwin_full.pgdump root@167.233.143.105:/opt/agritwin-data/
# Server: docker exec -i infra-db-1 pg_restore -U agritwin -d agritwin < /opt/agritwin-data/agritwin_full.pgdump
```

---

## Phase 6 — Done ✅ — Start App Services

```bash
docker compose -p agritwin -f deploy/agritwin/docker-compose.prod.yml up -d web celery_worker

# Verify
docker compose -p agritwin ps
docker logs agritwin-web-1
docker logs agritwin-celery_worker-1
```

> **Gotcha (2026-06-30):** First deploy accidentally used the dev `agriTwin-app/docker-compose.yml`
> instead of `deploy/agritwin/docker-compose.prod.yml`. The dev compose puts containers on an
> isolated `agritwin_default` network — nginx (on `infra_proxy`) cannot reach them → 502.
> Fix: always run the app from the prod compose file above. One-time recovery:
> `docker network connect infra_proxy agritwin-web-1` (immediate) then switch to prod compose.

---

## Phase 7 — Done ✅ — SSL with Let's Encrypt

```bash
# Install certbot
apt-get install -y certbot

# Issue cert (nginx serves /.well-known/acme-challenge/ via the webroot volume)
certbot certonly --webroot \
  -w /opt/agritwin/deploy/infra/certbot/webroot \
  -d agritwin.yourdomain.com \
  --non-interactive --agree-tos -m you@yourdomain.com

# Uncomment the HTTPS server block in deploy/infra/nginx/conf.d/agritwin.conf
# Update the domain name, then reload nginx (zero downtime):
nano /opt/agritwin/deploy/infra/nginx/conf.d/agritwin.conf
docker exec infra-nginx-1 nginx -s reload

# Verify
curl -I https://agritwin.yourdomain.com

# Auto-renewal (add to root's crontab: crontab -e)
# 0 3 * * * certbot renew --quiet && docker exec infra-nginx-1 nginx -s reload
```

---

## Phase 8 — Done ✅ — Systemd Auto-Start on Reboot

```bash
cp /opt/agritwin/deploy/systemd/agritwin-infra.service /etc/systemd/system/
cp /opt/agritwin/deploy/systemd/agritwin-app.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable agritwin-infra.service agritwin-app.service

# Test
reboot
# After reboot:
ssh -i ~/.ssh/id_ed25519_personal root@167.233.143.105
systemctl status agritwin-infra agritwin-app
docker compose -p agritwin -f /opt/agritwin/deploy/agritwin/docker-compose.prod.yml ps
```

---

## Phase 9 — Skipped — Backups and Hardening

```bash
# Nightly pg_dump (add to crontab -e):
# 0 2 * * * /opt/agritwin/deploy/scripts/backup-pg.sh >> /var/log/agritwin-backup.log 2>&1

# Test first:
bash /opt/agritwin/deploy/scripts/backup-pg.sh
ls -lh /opt/agritwin-data/backups/

# Docker log rotation
tee /etc/docker/daemon.json <<'EOF'
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "50m",
    "max-file": "3"
  }
}
EOF
systemctl restart docker
docker compose -p infra -f /opt/agritwin/deploy/infra/docker-compose.yml up -d
docker compose -p agritwin -f /opt/agritwin/deploy/agritwin/docker-compose.prod.yml up -d web celery_worker
```

---

## Adding a Second App

1. Add `deploy/infra/nginx/conf.d/app2.conf` (copy `app2.conf.example`, fill domain + container name)
2. `docker exec infra-db-1 psql -U postgres -c "CREATE DATABASE app2;"`
3. App2's compose: `CELERY_BROKER_URL=redis://infra-redis-1:6379/1`
4. App2's compose: `networks: infra_proxy: external: true`
5. `certbot certonly --webroot ... -d app2.yourdomain.com`
6. Add `deploy/systemd/app2.service`

---

## Resource Budget (4 vCPU / 8 GB RAM)

| Service | Memory Limit |
|---|---|
| PostgreSQL | 2,048 MB |
| Redis | 300 MB |
| Nginx | 128 MB |
| agritwin web (Gunicorn, 9 workers on 4 vCPU) | 1,024 MB |
| agritwin celery_worker | 1,024 MB |
| OS + Docker daemon | ~500 MB |
| **Headroom for second app** | ~3,000 MB |

With 4 vCPUs, Gunicorn runs `(2 × 4) + 1 = 9` workers automatically via `gunicorn.conf.py`.

---

## Verification Checklist

- [x] `curl -I https://agritwin.online` → 200, HTTPS
- [x] HTTP → HTTPS redirect active (bare IP returns 444)
- [x] SSL auto-renewal cron set (certbot + nginx reload at 03:00 daily)
- [x] `/` map page loads; cells appear after pan
- [x] `/suitability` → confirmed working
- [x] `/scenarios` lists 4 demo scenarios
- [x] `/yield-profit` → confirmed working (required shm_size: 256mb on db)
- [x] Reboot → both systemd services auto-start (verified 2026-06-30)
- [ ] Create scenario → Celery completes → `status: completed`  *(not yet verified on prod)*

---

## Gotchas

| Issue | Fix |
|---|---|
| pgdata not writable at container start | `chown -R 1000:1000 /opt/agritwin-data/pgdata` |
| Docker iptables conflicts with UFW | Don't use UFW — use Hetzner cloud firewall instead |
| `h3>=4.0` pip build fails | Add `RUN apt-get install -y build-essential cmake` to Dockerfile (unlikely on x86) |
| nginx 502 after starting app | Using `agriTwin-app/docker-compose.yml` (dev) instead of `deploy/agritwin/docker-compose.prod.yml` puts containers on `agritwin_default` instead of `infra_proxy` — nginx can't reach them. Always use the prod compose file. |
