# Production deployment runbook

Manual deployment for the Liman Salon MVP stack. There is **no continuous deployment (CD)** in this repository: operators pull a known Git revision on the host, rebuild affected Docker images, and restart services with Docker Compose.

**Related operations docs**

- [Health checks and smoke tests](./health-smoke.md)
- [Alembic migrations](./alembic-migrations.md)
- [Scheduled background jobs](./scheduled-jobs.md)

---

## 1. Scope and release context

### What this runbook covers

- Deploying the **production-like Docker Compose stack** defined in [`docker-compose.yml`](../../docker-compose.yml):
  - **`postgres`** — PostgreSQL 16 (omit or disable when using external Postgres; see `.env` / compose comments).
  - **`api`** — FastAPI + uvicorn ([`backend/Dockerfile`](../../backend/Dockerfile)), port 8000 inside the network.
  - **`web`** — static SPA + nginx ([`frontend/Dockerfile`](../../frontend/Dockerfile), [`deploy/nginx/default.conf`](../../deploy/nginx/default.conf)).
  - **`job-scheduler`** — supercronic workers ([`backend/Dockerfile.jobs`](../../backend/Dockerfile.jobs)); optional separate file [`docker-compose.jobs.yml`](../../docker-compose.jobs.yml) when Postgres is external.
- **Environment configuration** from repo-root [`.env.example`](../../.env.example) (secrets never committed).
- **Post-deploy verification**: HTTP health and an authenticated schedule **impact-preview** smoke (see §5).
- **Rollback** of the API image to a prior Git revision (see §6).

### Runbook on the deploy host

This file must be available on `<DEPLOY_HOST>` while you execute the procedure (typically at `<REPO_PATH>/docs/ops/production-deploy.md` in the Git checkout). Before deploy, ensure it is present either because it is **committed on the revision you check out**, or because operators copied it **out-of-band** to a known path. Checking out PR18 release SHA `59e718ab46af0962eea6c42d0de71ca70a75a039` **alone does not include this runbook** in the tree until a follow-up commit merges it to `main` and that newer revision is checked out on the host.

### What this runbook does not cover

- Provisioning hosts, TLS certificates, DNS, or firewall rules (use placeholders below).
- Automated CI deploy to production (GitHub Actions [`.github/workflows/backend-ci.yml`](../../.github/workflows/backend-ci.yml) runs tests only; it does not deploy).
- Database backups, restore drills, or architect-approved migration rollbacks (see [alembic-migrations.md](./alembic-migrations.md)).
- Destructive Docker maintenance (`docker system prune`, `volume rm`, etc.) — **do not** use those in production unless a separate disaster-recovery runbook explicitly authorizes them.

### Placeholders (replace per environment)

| Placeholder | Example | Purpose |
|-------------|---------|---------|
| `<DEPLOY_HOST>` | `prod.example.com` | SSH / bastion target |
| `<DEPLOY_USER>` | `deploy` | Unix account that owns the checkout |
| `<REPO_PATH>` | `/opt/liman-salon` | Git checkout on the server (same path style as [scheduled-jobs.md](./scheduled-jobs.md)) |
| `<PUBLIC_BASE_URL>` | `https://salon.example.com` | Browser/curl entry (nginx `web` or external reverse proxy) |
| `<WEB_PORT>` | `8080` | Host port mapped to nginx when not using 443 termination on `web` |
| `<PREVIOUS_GIT_SHA>` | prior release tag or commit | Rollback target |

### Release example: PR18 (backend-only, no migrations)

Use this subsection when the approved release matches **PR18**: application code changes in the **API only**, **no new Alembic revisions**, no required frontend or job-scheduler image changes.

| Item | Value |
|------|--------|
| Expected `main` revision | `59e718ab46af0962eea6c42d0de71ca70a75a039` |
| Services to rebuild/restart | **`api` only** (default for PR18) |
| Alembic | **Skip** `alembic upgrade` — schema unchanged |
| `web` / `job-scheduler` | Leave running unless the release notes say otherwise |
| Feature under test | `POST /api/v1/salons/{salon_id}/schedule/impact-preview` (owner/admin JWT; read-only preview with `session.rollback()`) |

For releases that **include** schema changes, new frontend assets, or crontab changes, expand scope: run migrations ([§4](#4-database-migrations)), rebuild **`web`** and/or **`job-scheduler`**, and follow [health-smoke.md](./health-smoke.md) fully.

---

## 2. Preflight (read-only)

Complete these checks **before** changing running containers. All commands are read-only or non-mutating unless noted.

### 2.1 Confirm target revision

On `<DEPLOY_HOST>`:

```bash
cd <REPO_PATH>
git fetch origin
git rev-parse HEAD
git log -1 --oneline
```

For PR18, `HEAD` (or the checked-out tag) should match:

`59e718ab46af0962eea6c42d0de71ca70a75a039`

Record the current commit as `<PREVIOUS_GIT_SHA>` before checkout (rollback reference).

### 2.2 CI and local confidence (optional, off prod)

Backend CI on `main` runs install, `alembic upgrade head`, and `pytest` in [`backend/`](../../backend/). Green CI on the target SHA is recommended but does not replace on-host smoke tests.

### 2.3 Compose and environment sanity

```bash
cd <REPO_PATH>
docker compose config
```

Verify:

- `JWT_SECRET_KEY` and `BOOKING_MANAGE_TOKEN_PEPPER` are set (required by compose for `api` / `job-scheduler`). When `ENVIRONMENT` is **`production`** or **`staging`**, the API rejects development defaults and requires each value to be at least 32 characters ([`backend/app/core/config.py`](../../backend/app/core/config.py)).
- `POSTGRES_PASSWORD` is set if using the bundled `postgres` service.
- `DATABASE_URL` points at the intended database (internal `postgres:5432` or external URL).
- `WEB_PORT` matches how operators reach nginx (see [`.env.example`](../../.env.example)).

Do **not** commit or paste real secrets into tickets or chat.

### 2.4 Running stack state

```bash
docker compose ps
docker compose logs --tail=50 api
docker compose logs --tail=50 web
```

Optional health (does not expose Git SHA):

```bash
curl -fsS "http://127.0.0.1:<WEB_PORT>/health"
# Expected body: {"status":"ok"}
```

The API route is **`GET /health`** at the FastAPI app root ([`backend/app/api/routes/health.py`](../../backend/app/api/routes/health.py)). Nginx proxies `location = /health` to the API ([`deploy/nginx/default.conf`](../../deploy/nginx/default.conf)). The response does **not** include build or Git metadata.

### 2.5 Database revision (read-only)

When Postgres is reachable from a one-off API container:

```bash
docker compose run --rm api alembic current
```

For PR18, note the current revision; it should be unchanged after deploy. Details: [alembic-migrations.md](./alembic-migrations.md).

### 2.6 Background jobs

If `job-scheduler` runs in this environment, confirm recent logs (no deploy action yet):

```bash
docker compose logs --tail=30 job-scheduler
```

See [scheduled-jobs.md](./scheduled-jobs.md).

### 2.7 Maintenance window and comms

- Announce window if API restart causes brief nginx **502** while `api` healthcheck passes.
- Ensure a second operator or architect contact is available for rollback (§6).

---

## 3. Deploy (API-only — sufficient for PR18)

When the release is **backend-only** with **no migration** (PR18 pattern), update code and recycle only the **`api`** service.

### 3.1 Check out approved revision

```bash
cd <REPO_PATH>
git fetch origin
git checkout 59e718ab46af0962eea6c42d0de71ca70a75a039
git rev-parse HEAD
```

Confirm `git rev-parse HEAD` matches the **architect-approved SHA** exactly (for PR18: `59e718ab46af0962eea6c42d0de71ca70a75a039`). Prefer this explicit checkout over `git checkout main && git merge --ff-only origin/main` without a follow-up verify step: after `git fetch`, ff-only moves `main` to whatever tip `origin/main` is, which may be **newer** than the approved release.

### 3.2 Rebuild and restart API

```bash
docker compose build api
docker compose up -d api
```

Compose will wait for **`api`** health (`127.0.0.1:8000/health` inside the container) before dependent services consider it healthy. **`web`** may already be running; it depends on a healthy API at startup — if `web` was up, it should continue proxying once `api` is healthy.

### 3.3 When to also rebuild other services

| Change type | Action |
|-------------|--------|
| Frontend assets or nginx config | `docker compose build web && docker compose up -d web` |
| Crontab / job modules only | `docker compose build job-scheduler && docker compose up -d job-scheduler` |
| External Postgres, jobs on host cron | Use [docker-compose.jobs.yml](../../docker-compose.jobs.yml) or host cron per [scheduled-jobs.md](./scheduled-jobs.md) |

**PR18:** none of the above — **API only**.

### 3.4 First-time or full-stack deploy (reference)

Not required for PR18 on an already-live environment. For greenfield or disaster rebuild, see [health-smoke.md](./health-smoke.md): `docker compose up --build -d`, migrations, optional first-salon bootstrap.

---

## 4. Database migrations

### PR18: none

Do **not** run `alembic upgrade` for PR18. Preflight `alembic current` (§2.5) and post-deploy `alembic current` should match.

### Other releases

When the release includes new files under `backend/alembic/versions/`:

1. Take a backup (operator policy; not scripted here).
2. Apply:

   ```bash
   docker compose run --rm api alembic upgrade head
   docker compose run --rm api alembic current
   ```

3. Then rebuild/restart **`api`** (and any other affected services).

Full procedure: [alembic-migrations.md](./alembic-migrations.md).

---

## 5. Post-deploy verification

Run immediately after the API container is healthy.

### 5.1 Health (unauthenticated)

Via nginx (public entry):

```bash
curl -fsS "<PUBLIC_BASE_URL>/health"
# Or on-host: curl -fsS "http://127.0.0.1:<WEB_PORT>/health"
```

Expected: HTTP **200**, body **`{"status":"ok"}`**. No SHA or version field.

Direct to API (debug only; typically not exposed publicly):

```bash
docker compose exec api python -c \
  "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).read())"
```

See [health-smoke.md](./health-smoke.md).

### 5.2 Container health

```bash
docker compose ps
docker compose logs --tail=100 api
```

Confirm **`api`** state is **healthy** per compose healthcheck.

### 5.3 Schedule impact-preview smoke (authenticated)

Validates PR18 schedule impact preview wiring. This endpoint **does not mutate** booking data: the handler calls `session.rollback()` after preview ([`backend/app/api/v1/schedule.py`](../../backend/app/api/v1/schedule.py)).

| Item | Detail |
|------|--------|
| Method / path | `POST /api/v1/salons/{salon_id}/schedule/impact-preview` |
| Auth | `Authorization: Bearer <JWT>` for an **owner** or **admin** membership on `{salon_id}` |
| Denied roles | `staff`, `receptionist` → **403** |
| Path tenant | `{salon_id}` in the URL is authoritative; salon access comes from that path plus the user's **membership** (JWT identifies the user only). Use the same salon UUID in the path and in smoke placeholders. |

Replace placeholders:

- `<SALON_ID>` — UUID of the salon under test.
- `<OWNER_OR_ADMIN_JWT>` — access token for that salon (obtain via your production login flow or approved break-glass token issuance).
- `<WORKING_HOURS_ID>` — existing working-hours row UUID for a safe **delete preview**, or use another `change.kind` from [`ScheduleImpactPreviewRequest`](../../backend/app/api/schemas/schedule_impact.py).

Example (minimal delete preview body; adjust IDs):

```bash
curl -fsS -X POST \
  "<PUBLIC_BASE_URL>/api/v1/salons/<SALON_ID>/schedule/impact-preview" \
  -H "Authorization: Bearer <OWNER_OR_ADMIN_JWT>" \
  -H "Content-Type: application/json" \
  -d '{
    "change": {
      "kind": "working_hours.delete",
      "working_hours_id": "<WORKING_HOURS_ID>"
    }
  }'
```

Expected: HTTP **200**, JSON including at least:

- `impact_fingerprint` (64-char hex string in normal operation)
- `counts.total_impacted` (integer ≥ 0)
- `pagination` object
- `commit_policy` (preview allows commit policy metadata; preview itself does not commit schedule changes)

Optional pagination fields: `impact_offset`, `impact_limit` in the request body (see schema defaults).

**Failure triage**

| Symptom | Likely cause |
|---------|----------------|
| **401** | Missing/expired JWT |
| **403** | User is not owner/admin for salon |
| **502** / connection reset | API still starting or nginx upstream down |
| **422** | Invalid `change` body or unknown UUID format |
| **500** with path mismatch | Abnormal internal guard (`_assert_path_salon` in [`schedule.py`](../../backend/app/api/v1/schedule.py)); not typical operator misconfiguration. Wrong salon or role → **403**; missing/expired auth → **401**. |

Automated behavior reference: [`backend/tests/api/test_schedule_impact.py`](../../backend/tests/api/test_schedule_impact.py).

### 5.4 Regression spot-checks (optional)

- Public metadata: `GET <PUBLIC_BASE_URL>/api/v1/public/salons/<slug>` (if used in prod).
- Job scheduler logs unchanged if not redeployed: `docker compose logs --tail=20 job-scheduler`.

---

## 6. Rollback (API)

Use when post-deploy verification fails and restoring the previous API behavior is required. This runbook assumes **schema unchanged** (PR18); if migrations were applied in the failed release, stop and follow architect guidance in [alembic-migrations.md](./alembic-migrations.md).

### 6.1 Check out previous revision

```bash
cd <REPO_PATH>
git checkout <PREVIOUS_GIT_SHA>
```

### 6.2 Rebuild and restart API

```bash
docker compose build api
docker compose up -d api
```

### 6.3 Re-verify

Repeat §5.1 (health) and any critical authenticated smokes. Record incident and failed SHA; do not redeploy the bad revision without a fix.

**Note:** Rolling back Git and the API image does **not** revert PostgreSQL data. Impact-preview rollback testing only affected in-memory/session state when the failed version was live.

---

## 7. Operational checklist

Copy for each production deploy ticket.

### Before deploy

- [ ] Approved release SHA recorded (PR18: `59e718ab46af0962eea6c42d0de71ca70a75a039`)
- [ ] `<PREVIOUS_GIT_SHA>` recorded for rollback
- [ ] Scope confirmed: API-only / migrations yes-no / web / jobs
- [ ] `docker compose config` succeeds; secrets present (not logged)
- [ ] `docker compose ps` baseline; `/health` returns `{"status":"ok"}`
- [ ] `alembic current` noted (if applicable)
- [ ] Stakeholders notified if restart causes brief errors

### Deploy steps (PR18)

- [ ] `git checkout` approved SHA on `<REPO_PATH>`; `git rev-parse HEAD` matches ticket
- [ ] `docker compose build api`
- [ ] `docker compose up -d api`
- [ ] **Skipped:** `alembic upgrade` (no migration)

### After deploy

- [ ] `docker compose ps` — `api` healthy
- [ ] `curl` `/health` → 200, `{"status":"ok"}`
- [ ] Impact-preview smoke: owner/admin JWT, 200, plausible JSON (`impact_fingerprint`, `counts`)
- [ ] No unexpected errors in `docker compose logs api` (last 15 minutes)
- [ ] Job scheduler logs normal (if not redeployed)

### Rollback (if needed)

- [ ] `git checkout <PREVIOUS_GIT_SHA>`
- [ ] `docker compose build api && docker compose up -d api`
- [ ] Health + critical smokes pass
- [ ] Incident documented

### References

- Stack layout: [`docker-compose.yml`](../../docker-compose.yml)
- Nginx routing: [`deploy/nginx/default.conf`](../../deploy/nginx/default.conf)
- Env template: [`.env.example`](../../.env.example)
- Backend local env (dev only): [`backend/.env.example`](../../backend/.env.example)

---

## Document history

| Field | Value |
|-------|--------|
| Deployment model | Manual Docker Compose on operator host |
| CD | None in repo |
| PR18 example SHA | `59e718ab46af0962eea6c42d0de71ca70a75a039` |
