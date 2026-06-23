# CLAUDE.md — agritwin monorepo root

This is the root of the agritwin monorepo. All prompts are written here. Read this file first, then read the relevant sub-repo's CLAUDE.md before touching any code.

## Repo map

| Directory | What it is |
|---|---|
| `agriTwin-etl/` | ETL pipeline — downloads, processes, and loads agricultural data into PostgreSQL |
| `agriTwin-app/` | Web application — Flask + MapLibre UI that reads from the same PostgreSQL database |

Both repos share a single PostgreSQL database (populated by ETL, read by app).

## Routing: which repo to work in

**ETL work** — touches `agriTwin-etl/`:
- Adding or fixing a data source (NDVI, weather, soil, crop stats, prices)
- Parquet processing, schema changes, or loader fixes
- `agritwin_etl/` Python package — parsers, store, db/load.py
- ETL Alembic migrations (writes to `alembic_version`, never `alembic_version_app`)

**App work** — touches `agriTwin-app/`:
- Flask routes, API endpoints, Jinja2 templates
- MapLibre JS, frontend interactivity
- App Alembic migrations (writes to `alembic_version_app`, never `alembic_version`)
- Suitability scoring engine, background tasks
- pytest tests in `agriTwin-app/tests/`

**Inter-repo work** — touches both:
- Database schema changes that both repos must agree on (e.g. adding a column ETL writes and app reads)
- Docker Compose changes (lives in `agriTwin-app/docker-compose.yml` but covers both services)
- Shared environment variable or connection string changes
- Phase transitions that require ETL to produce new data that the app then displays

## Key shared facts

- **Database:** PostgreSQL + PostGIS + TimescaleDB on port 5433 (Docker) or 5432 (host)
- **Docker Compose:** lives in `agriTwin-app/docker-compose.yml`; always run from the `agriTwin-app/` subdirectory. Build context is `..` (this monorepo root), so both repos are in scope for every Docker build.
- **`.dockerignore`:** lives at the **monorepo root** (this directory), not inside `agriTwin-app/`. Docker reads `.dockerignore` from the build context root. The file excludes `agriTwin-etl/data/`, `.pgdata/`, `.venv/`, and other large directories that must not be sent to the Docker daemon.
- **ETL tables** (owned by ETL Alembic): `data_source`, `spatial_cell`, `feature`, `observation`, `crop`, `crop_requirement`, `commodity_price`, `production_cost`, `ingestion_run`, `crop_statistics`
- **App tables** (owned by app Alembic): `scenario`, `scenario_override`, `suitability_score`, `yield_prediction`, `profit_projection`
- App reads ETL tables but never migrates them. ETL never touches app tables.

## Current phase

**Phase 3 — Suitability scoring** (in progress in `agriTwin-app/`). ETL is stable; no active ETL work unless a new data source is needed.

See each sub-repo's `CLAUDE.md` for full architecture details, conventions, and phase definitions.
