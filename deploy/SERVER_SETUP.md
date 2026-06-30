# Server Setup — Fresh Clone

Use this when setting up a new server or after a full wipe.
For routine code updates on an already-running server, see [Deploying Updates](#deploying-updates) below.

---

## 1 — SSH key for GitHub (run once on the server)

```bash
ssh-keygen -t ed25519 -C "ringo-deploy" -f ~/.ssh/id_ed25519 -N ""
cat ~/.ssh/id_ed25519.pub
```

Add the printed public key to GitHub:
- Go to GitHub → Settings → SSH and GPG keys → New SSH key
- Title: `ringo`
- Paste the key

Verify it works:
```bash
ssh -T git@github.com
# Hi ridvanzengin! You've authenticated...
```

---

## 2 — Clone all three repos

```bash
mkdir -p /opt/agritwin
git clone -b main git@github.com:ridvanzengin/agritwin.git /opt/agritwin
git clone -b main git@github.com:ridvanzengin/agriTwin-app.git /opt/agritwin/agriTwin-app
git clone -b main git@github.com:ridvanzengin/agriTwin-etl.git /opt/agritwin/agriTwin-etl
```

---

## 3 — Restore ETL Parquet data

The processed data files are NOT in git (too large). Restore from your local machine:

```bash
# From your LOCAL machine:
rsync -avz --progress -e "ssh -i ~/.ssh/id_ed25519_personal" \
  /Users/ridvan/personal/agritwin/agriTwin-etl/data/processed/ \
  root@<SERVER_IP>:/opt/agritwin-data/etl-processed/
```

---

## 4 — Create secret env files

```bash
# Infra secrets (PostgreSQL superuser password):
cp /opt/agritwin/deploy/infra/.env.example /opt/agritwin/deploy/infra/.env
nano /opt/agritwin/deploy/infra/.env

# App secrets (DB password + Flask secret key):
cp /opt/agritwin/deploy/agritwin/.env.prod.example /opt/agritwin/deploy/agritwin/.env.prod
nano /opt/agritwin/deploy/agritwin/.env.prod
# Generate FLASK_SECRET_KEY: python3 -c "import secrets; print(secrets.token_hex(32))"
```

---

## 5 — Create data directories

```bash
mkdir -p /opt/agritwin-data/{pgdata,etl-processed,backups}
chown -R 1000:1000 /opt/agritwin-data/pgdata  # timescaledb-ha runs as UID 1000
```

---

## 6 — Start infra and create the database

```bash
docker compose -p infra -f /opt/agritwin/deploy/infra/docker-compose.yml up -d

docker exec -it infra-db-1 psql -U postgres <<'SQL'
  CREATE DATABASE agritwin;
  CREATE USER agritwin WITH PASSWORD 'CHANGE_ME';  -- match .env.prod AGRITWIN_DB_PASSWORD
  GRANT ALL PRIVILEGES ON DATABASE agritwin TO agritwin;
  \c agritwin
  CREATE EXTENSION IF NOT EXISTS postgis;
  CREATE EXTENSION IF NOT EXISTS timescaledb;
SQL
```

---

## 7 — Build image, run migrations, load data

```bash
cd /opt/agritwin

# Build the app image
docker compose -p agritwin -f deploy/agritwin/docker-compose.prod.yml build

# Run both Alembic chains
docker compose -p agritwin -f deploy/agritwin/docker-compose.prod.yml run --rm migrate

# Load all ETL data + seed demo scenarios (~5–10 min)
docker compose -p agritwin -f deploy/agritwin/docker-compose.prod.yml run --rm loader
```

---

## 8 — Start app services

```bash
docker compose -p agritwin -f deploy/agritwin/docker-compose.prod.yml up -d web celery_worker
```

---

## 9 — SSL (if domain already has an A record pointing here)

```bash
apt-get install -y certbot

certbot certonly --webroot \
  -w /opt/agritwin/deploy/infra/certbot/webroot \
  -d agritwin.online -d www.agritwin.online \
  --non-interactive --agree-tos -m your@email.com

docker exec infra-nginx-1 nginx -s reload

# Add renewal cron:
(crontab -l 2>/dev/null; echo "0 3 * * * certbot renew --webroot -w /opt/agritwin/deploy/infra/certbot/webroot --quiet && docker exec infra-nginx-1 nginx -s reload") | crontab -
```

---

## 10 — Systemd auto-start

```bash
cp /opt/agritwin/deploy/systemd/agritwin-infra.service /etc/systemd/system/
cp /opt/agritwin/deploy/systemd/agritwin-app.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable agritwin-infra.service agritwin-app.service
```

---

## Deploying Updates

For every subsequent code change after initial setup:

```bash
# On the server — one command updates everything:
bash /opt/agritwin/deploy/scripts/deploy.sh
```

This pulls all three repos, rebuilds the image, runs migrations (idempotent no-op if nothing changed), and restarts web + celery_worker with zero infra downtime.
