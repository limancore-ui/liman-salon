# Alembic migrations (operations runbook)

Schema changes ship as Alembic revisions under `backend/alembic/versions/`. The application reads **`DATABASE_URL`** at runtime (see `backend/app/core/config.py` and `backend/alembic/env.py`).

## Prerequisites

- PostgreSQL reachable from the host or a one-off container on the same Docker network as `postgres`.
- `DATABASE_URL` using the **psycopg v3** driver is recommended:  
  `postgresql+psycopg://USER:PASSWORD@HOST:5432/DBNAME`
- For **production** or **staging**, set strong `JWT_SECRET_KEY` and `BOOKING_MANAGE_TOKEN_PEPPER` (see `.env.example`); dev defaults are rejected when `ENVIRONMENT=production`.

## Apply migrations (bare metal / CI)

From the repository root:

```bash
cd backend
export DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/liman_salon
export ENVIRONMENT=production
export JWT_SECRET_KEY='use-at-least-32-random-characters'
export BOOKING_MANAGE_TOKEN_PEPPER='use-at-least-32-random-characters'

pip install -e .
alembic upgrade head
```

Check current revision:

```bash
alembic current
alembic history --verbose
```

## Apply migrations (Docker Compose stack)

1. Start PostgreSQL only (or the full stack):

   ```bash
   docker compose up -d postgres
   ```

2. Run a one-off API image command on the compose network (uses the same `DATABASE_URL` as services):

   ```bash
   docker compose run --rm api alembic upgrade head
   ```

   The API image working directory is `/app/backend`; Alembic is on the PATH via the installed package.

3. Verify:

   ```bash
   docker compose run --rm api alembic current
   ```

## External PostgreSQL

When Postgres is managed outside this repo:

- Point `DATABASE_URL` at the external instance in `.env`.
- Remove or disable the bundled `postgres` service in `docker-compose.yml` (or use Compose profiles).
- Run `alembic upgrade head` from a host or CI job with network access to the database.

## Rollback (use with care)

Downgrade one step:

```bash
cd backend
alembic downgrade -1
```

Production rollbacks should be planned with the architect; data-loss risk depends on the revision.

## Notes

- Do not edit committed migration files; add new revisions for schema changes.
- Migrations load all ORM models via `app.db.models` in `alembic/env.py` so autogenerate metadata stays complete.
