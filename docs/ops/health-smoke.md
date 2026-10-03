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

3. **First salon** (once per environment; production guard — see script help)

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

4. **Health via nginx**

   ```bash
   curl -fsS "http://localhost:${WEB_PORT:-8080}/health"
   ```

5. **Public salon metadata** (after bootstrap; replace slug)

   ```bash
   curl -fsS "http://localhost:${WEB_PORT:-8080}/api/v1/public/salons/my-salon"
   ```

6. **Background jobs** (scheduler container logs)

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
