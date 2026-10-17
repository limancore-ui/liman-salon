# Health checks and smoke tests (operations)

## HTTP health endpoints

| Target | URL | Expected |
|--------|-----|----------|
| API (direct) | `http://api:8000/health` inside the stack | `{"status":"ok"}` |
| Via nginx | `http://localhost:${WEB_PORT:-8080}/health` | `{"status":"ok"}` |
| Public API prefix | `http://localhost:${WEB_PORT}/api/v1/...` | route-specific |

The FastAPI route is registered at **`/health`** (not under `/api/v1`). Nginx proxies `/health` to the API service; `/api/` is proxied for all versioned routes.

Docker Compose defines a healthcheck on the **`api`** service (Python `urllib` against `127.0.0.1:8000/health`). The **`web`** service waits for a healthy API before starting.

## Stack smoke (Docker Compose)

From the repo root after `cp .env.example .env` and filling secrets:

```bash
docker compose config
docker compose up --build -d
docker compose ps
```

1. **Database**

   ```bash
   docker compose exec postgres pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"
   ```

2. **Migrations** (first deploy)

   ```bash
   docker compose run --rm api alembic upgrade head
   ```

3. **First salon** (once per environment; production/staging guard — see script help)

   Requires `ALLOW_FIRST_SALON_BOOTSTRAP=1` when `ENVIRONMENT` is `production` or
   `staging`. On **staging**, the script also refuses unless the database name
   parsed from `DATABASE_URL` is exactly **`liman_salon_staging`** (not
   `liman_salon`, not `liman_salon_test`). Confirm before running:

   ```bash
   # Example staging project — expect ENVIRONMENT=staging and DB name liman_salon_staging
   docker compose -p liman-staging --env-file .env exec api printenv ENVIRONMENT POSTGRES_DB
   ```

   ```bash
   docker compose run --rm \
     -e ALLOW_FIRST_SALON_BOOTSTRAP=1 \
     api python scripts/bootstrap_first_salon.py \
       --email owner@example.com \
       --password '…' \
       --full-name 'Salon Owner' \
       --salon-name 'My Salon' \
       --timezone Asia/Bishkek \
       --currency KGS
   ```

   On staging, prefer `docker compose -p liman-staging --env-file .env run --rm --no-deps`
   from `/opt/liman-salon-staging` (not the production checkout).

4. **Health via nginx**

   ```bash
   curl -fsS "http://localhost:${WEB_PORT:-8080}/health"
   ```

5. **Public salon metadata** (after bootstrap; replace slug)

   ```bash
   curl -fsS "http://localhost:${WEB_PORT:-8080}/api/v1/public/salons/my-salon"
   ```

6. **Staging demo catalog** (staging only — fictional public-booking data)

   Use only against Compose project / checkout that targets database
   **`liman_salon_staging`** with `ENVIRONMENT=staging`. The script refuses any
   other environment or database name and requires an explicit allow flag.
   It does **not** create users, passwords, customers, or bookings.

   **Before running:** rebuild the staging API image so it contains
   `scripts/seed_staging_demo.py` (`docker compose run` uses that image), then
   confirm the target database. `POSTGRES_DB` is only a secondary hint; the
   database the app actually writes to comes from `DATABASE_URL`. Check its name
   without printing the full DSN, which contains credentials:

   ```bash
   # From /opt/liman-salon-staging (never the production checkout)
   docker compose -p liman-staging --env-file .env build api

   # Secondary hint — expect staging / liman_salon_staging
   docker compose -p liman-staging --env-file .env run --rm --no-deps api \
     printenv ENVIRONMENT POSTGRES_DB

   # Authoritative — prints only the database name parsed from DATABASE_URL
   docker compose -p liman-staging --env-file .env run --rm --no-deps api \
     python -c "from urllib.parse import urlparse, unquote; from app.core.config import get_settings; print(unquote(urlparse(get_settings().database_url).path).lstrip('/'))"
   ```

   **Owner/admin (optional, separate):** if you need admin UI login, run
   first-salon bootstrap (step 3 above) **first** with the same slug, then seed.
   Bootstrap on staging requires `ENVIRONMENT=staging`, DB name
   `liman_salon_staging`, and `ALLOW_FIRST_SALON_BOOTSTRAP=1`.

   ```bash
   docker compose -p liman-staging --env-file .env run --rm --no-deps \
     -e ALLOW_FIRST_SALON_BOOTSTRAP=1 \
     api python scripts/bootstrap_first_salon.py \
       --email owner.demo.staging@example.com \
       --password '…' \
       --full-name 'Demo Owner' \
       --salon-name 'Malina Beauty Test' \
       --salon-slug malina-beauty-test \
       --timezone Asia/Bishkek \
       --currency KGS

   docker compose -p liman-staging --env-file .env run --rm --no-deps \
     -e ALLOW_STAGING_DEMO_SEED=1 \
     api python scripts/seed_staging_demo.py
   ```

   **Catalog only (no owner):** omit bootstrap and run only `seed_staging_demo.py`
   with `ALLOW_STAGING_DEMO_SEED=1` — enough for `/s/malina-beauty-test` public
   booking smoke (staff, services, Mon–Sat 10:00–19:00 hours).

   > **Warning:** catalog-only mode takes the slug `malina-beauty-test`. A later
   > `bootstrap_first_salon.py --salon-slug malina-beauty-test` refuses because the
   > slug is already taken, so it can neither create that salon nor attach an
   > owner to it. If admin access may be needed later, run bootstrap first.

   Verify:

   ```bash
   curl -fsS "http://127.0.0.1:8090/api/v1/public/salons/malina-beauty-test"
   # Browser (via SSH tunnel to staging): http://127.0.0.1:8090/s/malina-beauty-test
   ```

   Local test DB seeding remains
   `scripts/seed_public_booking_test.py` (hard-gated to `liman_salon_test` only).

7. **Background jobs** (scheduler container logs)

   ```bash
   docker compose logs -f job-scheduler
   ```

   Manual one-shot inside the scheduler image:

   ```bash
   docker compose run --rm job-scheduler python -m app.jobs.expire_pending_holds
   docker compose run --rm job-scheduler python -m app.jobs.process_pending_notifications
   ```

   See also [scheduled-jobs.md](./scheduled-jobs.md).

## Local development smoke (no Docker)

```bash
cd backend
export DATABASE_URL=postgresql+psycopg://localhost:5432/liman_salon_test
uvicorn app.main:app --reload &
curl -fsS http://127.0.0.1:8000/health
```

Frontend dev server proxies `/api` to port 8000 (`frontend/vite.config.ts`).

## Failure triage

- **API unhealthy:** check `docker compose logs api`, verify `DATABASE_URL`, migrations at head, and production secret env vars.
- **502 from nginx:** API not healthy or wrong upstream name (`api:8000` on the compose network).
- **Static 404 on deep links:** ensure nginx `try_files` fallback to `index.html` (SPA).
