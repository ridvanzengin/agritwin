---
name: deploy
description: Deploy AgriTwin to production (https://agritwin.online) on the shared Hetzner VM "ringo" — routine updates, fresh-server setup, or health-checking/troubleshooting the live deployment. Use whenever asked to deploy, redeploy, ship to production, update the live site, or check on agritwin.online's health.
---

AgriTwin runs in production on the same Hetzner VM as IoTOps, via a shared
`infra` Compose project (nginx, PostgreSQL+PostGIS+TimescaleDB, Redis) that
both apps join as `infra_proxy` external-network members — see
`deploy/ROADMAP.md` for the full phase-by-phase history and
`deploy/SERVER_SETUP.md`/`.claude/deploy.config` for connection details.
This skill covers *operating* the live deployment: routine updates, and the
troubleshooting playbook for failure modes actually hit on this box
(some by AgriTwin's own history, some by IoTOps's deploy sharing the same
shared infra).

SSH: `ssh -i ~/.ssh/id_ed25519_personal root@167.233.143.105` (also in
`.claude/deploy.config`). Every command below runs on that VM unless noted.

## This repo's approval gate — read CLAUDE.md's workflow section first

Per this repo's own `CLAUDE.md`: **never commit, push, or deploy without
explicit user approval for each step**, asked separately ("Commit these
changes? (yes/no)", "Push to origin? (yes/no)", "Deploy to production?
(yes/no)"). Only deploy from `main`/`master`, never a feature branch. This
skill assumes those approvals already happened by the time deploy.sh runs
— it does not replace asking.

## Routine update (the common case)

```bash
bash /opt/agritwin/deploy/scripts/deploy.sh
```

Pulls all **three** repos (monorepo root on `master`, `agriTwin-app` and
`agriTwin-etl` both on `main` — hardcoded branch names are intentional
here, unlike a bug fixed in IoTOps's own deploy.sh, since this repo's
workflow explicitly forbids deploying anything but main/master), rebuilds
the app image, runs Alembic migrations (`migrate` service, one-shot, exits
when done), and restarts `web`+`celery_worker`. Does **not** restart the
shared `infra` project (db/redis/nginx stay up).

Restart just one service after a targeted fix:
```bash
cd /opt/agritwin
COMPOSE="docker compose -p agritwin --env-file deploy/agritwin/.env.prod -f deploy/agritwin/docker-compose.prod.yml"
$COMPOSE build <service> && $COMPOSE up -d --no-deps <service>
```

## Fresh server / disaster recovery

Follow `deploy/ROADMAP.md`'s phases 1-8 in order — provisioning, VM base
setup, infra compose, app image + migrations, ETL data load, start app
services, TLS, systemd. Don't improvise a different order; migrations must
run before `web` starts (compose's `depends_on: migrate: condition:
service_completed_successfully` already encodes this, but manual
step-by-step recovery needs the same order). Phase 9 (backups/hardening)
is marked skipped as of the last update — check its current status before
assuming it's still not done.

## Verifying a deployment actually worked

Don't stop at "containers are Up":

```bash
# Public reachability
curl -sI https://agritwin.online/ | head -3

# IoTOps unaffected -- check this after ANY shared-nginx touch
curl -sI https://iotops.online/ | head -3

# Container health
docker ps -a --format 'table {{.Names}}\t{{.Status}}' | grep agritwin

# Both Alembic chains landed (ETL's and app's are separate tables)
docker exec infra-db-1 psql -U agritwin -d agritwin \
  -c "SELECT 'etl', version_num FROM alembic_version UNION ALL SELECT 'app', version_num FROM alembic_version_app;"
# Expect two rows

# Functional smoke test
curl -s https://agritwin.online/scenarios | head -c 200   # lists demo scenarios
```

## Known failure modes

**nginx 502 from using the wrong compose file** (hit for real on
2026-06-30, per `deploy/ROADMAP.md`'s Phase 6 gotcha): running
`agriTwin-app/docker-compose.yml` (the *dev* compose) instead of
`deploy/agritwin/docker-compose.prod.yml` puts `web`/`celery_worker` on an
isolated `agritwin_default` network instead of the shared `infra_proxy` —
nginx can't reach them at all. Always use the prod compose file with
`-p agritwin -f deploy/agritwin/docker-compose.prod.yml`. One-time
recovery without a full redeploy: `docker network connect infra_proxy
agritwin-web-1`, then switch to the prod compose file properly.

**Shared `infra-nginx-1` silently stops listening on 80/443** (found while
deploying IoTOps on this same box, 2026-07-16: master + worker processes
alive per `docker exec infra-nginx-1 ps aux`, but `docker exec
infra-nginx-1 ss -tlnp` shows nothing bound) after several new containers
join `infra_proxy` in quick succession — e.g. a *different* app's deploy,
not necessarily AgriTwin's own. `nginx -s reload` does **not** fix this,
it needs an actual restart:
```bash
docker exec infra-nginx-1 ss -tlnp   # confirm: nothing on 80/443 despite ps showing workers
docker restart infra-nginx-1
curl -sI https://agritwin.online/    # confirm recovery
curl -sI https://iotops.online/      # this affects both apps -- check both
```
This is shared infra another app's Claude session might also touch — get
explicit confirmation before restarting it, naming the action exactly,
regardless of which app's deploy triggered the problem.

**`agritwin.conf`'s `proxy_pass` already uses the safe pattern** —
`set $upstream http://agritwin-web-1:5000; proxy_pass $upstream;`, not a
bare static hostname. This is *correct*: a bare `proxy_pass
http://host:port` resolves once at nginx startup/reload and caches
forever, so it would 502 after any redeploy that recreates `agritwin-web-1`
(new container = new IP). Confirmed 2026-07-16 while fixing exactly this
bug in IoTOps's own vhost, which had copied the wrong (static) form. If
`agritwin.conf` is ever edited, keep the `set $upstream` form — don't
"simplify" it back to a bare `proxy_pass`.

**Shared `infra-db-1` connection limit is only 25** (`max_connections=25`,
~22 non-superuser slots), now split between AgriTwin and IoTOps. AgriTwin's
own `agritwin_app/db/session.py` calls `create_engine(database_url,
pool_pre_ping=True)` with **no explicit `pool_size`/`max_overflow`** —
SQLAlchemy's defaults (5 + 10 = 15) apply *per Gunicorn worker process*.
`gunicorn.conf.py` runs `(2 × vCPU) + 1` workers (9 on this VM's 4 vCPUs),
so the theoretical worst case is 9 × 15 = 135 connections from `web` alone
— far more than the shared instance can serve, though real-world usage has
stayed low (~13 connections observed in practice, per
`pg_stat_activity`). This hasn't caused an incident yet, but it's a real
structural risk if traffic ever increases — worth capping `pool_size`/
`max_overflow` explicitly in `create_engine()` rather than relying on
headroom staying comfortable by chance. Check current usage before
assuming it's fine:
```bash
docker exec infra-db-1 psql -U postgres -c "SELECT count(*), usename FROM pg_stat_activity GROUP BY usename;"
```

**`pgdata` not writable at container start** — `timescaledb-ha` runs as
UID 1000; fix with `chown -R 1000:1000 /opt/agritwin-data/pgdata`. Don't
use UFW on this box (conflicts with Docker's own iptables rules) — use
Hetzner's cloud firewall instead.

## Safety rules (non-negotiable, not just style)

- `infra-nginx-1`, `infra-db-1`, `infra-redis-1` are **shared with
  IoTOps, live**. Any direct mutation (restart, exec into to run scripts,
  raw SQL deletes) needs explicit confirmation naming the exact action —
  a general "yes" earlier in the conversation does not carry forward to a
  new specific risky action.
- Follow this repo's own commit/push/deploy approval gate (see above) —
  this skill does not bypass it.
- `nginx -t` gates every `nginx -s reload`, no exceptions. Check
  `iotops.online` before and after any shared-nginx touch, the same way
  AgriTwin's own checks should be checked from the other app's session.
- Prefer read-only diagnosis (`docker ps`, `docker logs`, `psql SELECT`)
  before any write/restart — establish what's actually broken before
  acting on it.
- Never force-push, never commit secret files (`.env`, `.env.prod`,
  `.claude/deploy.config`).
