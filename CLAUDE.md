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

**Phase 5/6 complete** (`agriTwin-app/`). ETL is stable. See each sub-repo's `CLAUDE.md` for full architecture details, conventions, and phase definitions.

---

## Development workflow

Follow this pipeline for every change. Never skip or reorder steps.

### 1 — Branch first

Before writing any code, create a feature branch in the relevant repo(s):

| Repo | Default branch | Branch command |
|---|---|---|
| `agriTwin-app/` | `main` | `git -C agriTwin-app checkout -b feature/<slug>` |
| `agriTwin-etl/` | `main` | `git -C agriTwin-etl checkout -b feature/<slug>` |
| monorepo root | `master` | `git checkout -b feature/<slug>` |

Use a short, lowercase, hyphenated slug that describes the change (e.g. `feature/scenario-export`, `feature/fix-mobile-layout`).
Skip branch creation only if the user explicitly says to work directly on main/master.

### 2 — Make changes and test locally

- For UI/template changes: verify the page looks correct in the browser before declaring done.
- For API/backend changes: run `pytest` inside the Docker container or venv.
- For ETL changes: spot-check Parquet output or DB row counts.

### 3 — Ask for approval before committing

Show a concise diff summary (files changed, what changed and why), then ask:
**"Commit these changes? (yes / no)"**

Do not commit until the user confirms.

### 4 — Ask for approval before pushing

After committing, show the commit(s) that will be pushed and ask:
**"Push to origin? (yes / no)"**

Do not push until the user confirms.

### 5 — Ask for approval before deploying

After the branch is merged to main, ask:
**"Deploy to production? (yes / no)"**

If yes, use the `/deploy` skill — it handles SSH, streaming output, and error reporting.
Never deploy a feature branch directly; only deploy from main.

### Rules

- **Never commit, push, or deploy without explicit user approval for each step.**
- **Never force-push.**
- **Never commit secret files** (`.env`, `.env.prod`, `.claude/deploy.config`, etc.).
- One logical change per commit; write the commit message in imperative mood (`fix:`, `feat:`, `docs:`).
