# Scheduled background jobs

Two **one-shot** workers should run on a fixed interval in each environment:

| Job | Module | Suggested interval |
|-----|--------|--------------------|
| Expire stale pending booking holds | `app.jobs.expire_pending_holds` | Every **2** minutes |
| Process due notification outbox rows | `app.jobs.process_pending_notifications` | Every **1** minute |

Run from the **`backend/`** directory (or set `WORKDIR` / `cd` accordingly) so `python -m app.jobs.*` resolves the package.

**Required environment:** `DATABASE_URL` (PostgreSQL, `postgresql+psycopg://…` recommended). Other settings use defaults from `app.core.config` unless overridden.

Reference crontab (Docker-oriented paths): [deploy/cron/liman-jobs.crontab](../../deploy/cron/liman-jobs.crontab).

---

## Linux — cron

1. Install the backend package in a venv on the host (example):

   ```bash
   cd /opt/liman-salon/backend
   python3.11 -m venv .venv
   .venv/bin/pip install -e .
   ```

2. Install a crontab for the deploy user (adjust paths and log directory):

   ```cron
   SHELL=/bin/sh
   PATH=/opt/liman-salon/backend/.venv/bin:/usr/local/bin:/usr/bin:/bin
   DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/liman_salon

   * * * * * cd /opt/liman-salon/backend && python -m app.jobs.process_pending_notifications >> /var/log/liman/jobs-notifications.log 2>&1
   */2 * * * * cd /opt/liman-salon/backend && python -m app.jobs.expire_pending_holds >> /var/log/liman/jobs-holds.log 2>&1
   ```

   Prefer injecting `DATABASE_URL` via `/etc/default/liman-jobs` and sourcing it from a wrapper script if you do not want secrets in the crontab file.

3. Use **UTC** for cron unless you intentionally align with salon-local midnight logic (job logic uses UTC `as_of`).

Manual one-shot smoke:

```bash
cd backend
./scripts/run-all-jobs-once.sh
```

---

## Windows — Task Scheduler

Run the same modules with the project venv Python on a schedule.

1. Create `backend\.venv` and `pip install -e backend` from repo root (or install from `backend/`).
2. Set **`DATABASE_URL`** in the task environment (Task Scheduler → task → **Environment variables**, or a small wrapper `.cmd` that `set DATABASE_URL=…` then runs Python).
3. Create **two** tasks (or one task with two actions):

   | Task | Trigger | Program | Arguments |
   |------|---------|---------|-----------|
   | Liman — notifications | Repeat every **1 minute** indefinitely | `C:\path\to\liman-salon\backend\.venv\Scripts\python.exe` | `-m app.jobs.process_pending_notifications` |
   | Liman — expire holds | Repeat every **2 minutes** indefinitely | same Python | `-m app.jobs.expire_pending_holds` |

4. Set **Start in** to `C:\path\to\liman-salon\backend`.
5. Run whether user is logged on or not; use a service account with least privilege if the DB is remote.

PowerShell one-shot smoke (from `backend/`):

```powershell
$env:DATABASE_URL = "postgresql+psycopg://user:pass@localhost:5432/liman_salon"
python -m app.jobs.expire_pending_holds
python -m app.jobs.process_pending_notifications
```

---

## Docker Compose — supercronic (recommended for production-like ops)

The repo ships a **scheduler-only** compose file (no PostgreSQL service). The container runs [supercronic](https://github.com/aptible/supercronic) with the mounted crontab baked into the image.

```bash
# From repo root — DATABASE_URL must reach your Postgres (host.docker.internal, cloud URL, etc.)
export DATABASE_URL=postgresql+psycopg://user:pass@host.docker.internal:5432/liman_salon
docker compose -f docker-compose.jobs.yml up --build
```

- **Build:** `backend/Dockerfile.jobs` — Python 3.11 slim, `pip install -e .`, supercronic, crontab at `/etc/cron/liman-jobs.crontab`.
- **Logs:** job stdout/stderr appear in the `job-scheduler` container logs (`docker compose … logs -f job-scheduler`).

To change intervals, edit [deploy/cron/liman-jobs.crontab](../../deploy/cron/liman-jobs.crontab) and rebuild the image.

---

## Development-only — shell loop (not for production)

For local testing without cron or Docker, a simple loop is enough; **do not** use this in production (no overlap protection, drift, or restart policy):

```bash
cd backend
export DATABASE_URL=postgresql+psycopg://…
while true; do
  python -m app.jobs.process_pending_notifications || true
  python -m app.jobs.expire_pending_holds || true
  sleep 60
done
```

Note: this example wakes every 60s and runs **both** jobs; production uses **1 min** vs **2 min** intervals as in the crontab.

---

## Operations notes

- Jobs are **idempotent sweepers**; short overlap if a run exceeds the interval is acceptable but should be monitored.
- Failed runs exit non-zero; ensure cron / supercronic / Task Scheduler history or log shipping captures stderr.
- Tenant isolation is enforced inside application services; schedulers must not bypass the Python entrypoints.
