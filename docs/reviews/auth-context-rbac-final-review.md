# LIMAN SALON REVIEW REPORT

**Subject:** Authentication, salon context, and RBAC foundation  
**Repository:** `liman-salon`  
**Base commit on `main`:** `f0e8a55` — *Tenant-scoped API foundation*  
**Report date:** 2026-09-24  
**Commit / push for this work:** None (pending architect approval)

---

## 1. What was implemented

### Authentication (email/password)

- **`POST /api/v1/auth/login`** — validates credentials against `users` (case-insensitive email via `lower(email)`), verifies Argon2id hash, returns short-lived JWT access token.
- Generic **401** `invalid_credentials` for wrong password, unknown email, inactive user, or missing hash (no account enumeration).

### Current user

- **`get_current_user()`** dependency — Bearer JWT → verify signature/exp/type → load **active** user from DB → **`AuthenticatedUser`** (no `password_hash`).

### Salon context

- **`get_salon_context(salon_id, current_user)`** — active salon + active `salon_users` row → **`SalonContext`** (`user_id`, `salon_id`, `role`, salon name/slug).
- **`GET /api/v1/auth/me`** — authenticated user profile.
- **`GET /api/v1/auth/salons/{salon_id}/context`** — membership context for route `salon_id`.

### RBAC foundation

- **`ensure_role_allowed(context, *roles)`** and **`require_roles(*roles)`** FastAPI dependency factory — role from **DB-resolved** `SalonContext`, not from token.

### Unchanged public booking API

- **`GET /api/v1/salons/{salon_id}/availability`** and **`POST /api/v1/salons/{salon_id}/bookings`** remain **unauthenticated** (future public booking foundation); tenant checks stay in application services.

**Not implemented:** refresh tokens, user_sessions table, customer login/registration, platform-admin tenant bypass, protecting booking/availability routes, notifications/AI/payments, frontend.

---

## 2. Files changed

### Modified (tracked)

| File | Change |
|------|--------|
| `backend/pyproject.toml` | Runtime: `argon2-cffi`, `pyjwt`, `email-validator` |
| `backend/app/core/config.py` | `jwt_secret_key`, `jwt_algorithm`, `access_token_expire_seconds` |
| `backend/app/api/errors.py` | Auth exception → HTTP JSON handlers |
| `backend/app/api/v1/router.py` | Include `auth_routes.router` |
| `backend/tests/conftest.py` | Test `JWT_SECRET_KEY`, `get_settings.cache_clear()` |

### New (untracked)

| Path | Purpose |
|------|---------|
| `backend/app/core/security.py` | Argon2id + JWT create/decode |
| `backend/app/auth/__init__.py` | Auth package |
| `backend/app/auth/errors.py` | Domain auth errors |
| `backend/app/auth/principals.py` | `AuthenticatedUser`, `SalonContext` |
| `backend/app/auth/repository.py` | User/salon/membership reads |
| `backend/app/auth/deps.py` | `get_current_user`, `get_salon_context`, `require_roles` |
| `backend/app/auth/rbac.py` | `ensure_role_allowed` |
| `backend/app/api/schemas/auth.py` | Login/me/context Pydantic models |
| `backend/app/api/v1/auth_routes.py` | Auth HTTP routes |
| `backend/tests/api/test_auth_context_rbac.py` | Auth/context/RBAC API tests |
| `docs/reviews/auth-context-rbac-final-review.md` | This report |

### Not modified

- SQLAlchemy models, Alembic migrations, schema
- `AvailabilityService`, `BookingService` business logic
- `backend/app/api/v1/availability.py`, `bookings.py` (no auth guards added)

---

## 3. Architecture decisions

### Authentication mechanism

- **JWT** (HS256) signed with **`JWT_SECRET_KEY`** from settings (`pyjwt`).
- **Access token only** — no refresh persistence.

### Token contents (claims)

| Claim | Value |
|-------|--------|
| `sub` | `user_id` (UUID string) |
| `typ` | `"access"` |
| `iat` | issued-at (Unix seconds) |
| `exp` | expiration (Unix seconds) |

**Not in token:** `salon_id`, `role`, or any authorization claims.

### Token lifetime

- **`access_token_expire_seconds`** default **900** (15 minutes), configurable via env.

### Password hashing

- **Argon2id** via **`argon2-cffi`** (`PasswordHasher`).
- Login uses **`func.lower(User.email) == normalize_email(input)`** aligned with DB unique index on `lower(email)`.

### Routes

| Method | Path |
|--------|------|
| `POST` | `/api/v1/auth/login` |
| `GET` | `/api/v1/auth/me` |
| `GET` | `/api/v1/auth/salons/{salon_id}/context` |

### SalonContext structure

```text
SalonContext(
  user_id: UUID,
  salon_id: UUID,
  role: str,          # owner | admin | staff | receptionist
  salon_name: str,
  salon_slug: str,
)
```

### RBAC guard behavior

- **`require_roles("owner", "admin")`** → dependency runs after `get_salon_context`.
- Allowed role → return context; else **`ForbiddenRoleError`** → **403** `forbidden`.
- Missing/inactive membership → **403** `salon_access_denied` (in `get_salon_context`).

### DB membership revalidation

Every protected request:

1. Decode JWT → `user_id` only.
2. **`get_active_user_by_id`** — must be `is_active`.
3. **`get_active_salon(salon_id)`** — must exist and `salons.is_active`.
4. **`get_active_membership(salon_id, user_id)`** — must exist and `salon_users.is_active`.

**Platform `is_platform_admin` does not bypass** tenant checks in this foundation.

### Tenant isolation preserved

- Authorization never uses client-supplied `salon_id` alone; it requires **matching active membership** for the authenticated user.
- Changing URL `salon_id` to another tenant without membership → **403**.
- Public booking routes still pass explicit `salon_id` into services (unchanged).

### Error → HTTP mapping

| Condition | HTTP | `code` |
|-----------|------|--------|
| Invalid login | 401 | `invalid_credentials` |
| Bad/missing/expired token, inactive user | 401 | `unauthorized` |
| No active membership | 403 | `salon_access_denied` |
| Wrong role | 403 | `forbidden` |
| Salon missing/inactive | 404 | `not_found` |

### Why public booking routes unchanged

Architect scope: current availability/booking endpoints support **future public customer booking**; admin auth is introduced separately via `SalonContext` + `require_roles` on **future** admin routes.

---

## 4. DB changes

**NONE.**

- No migrations.
- No model/schema changes.
- Auth reads existing `users`, `salons`, `salon_users` via SQLAlchemy only.

---

## 5. Tests added / run

### New: `tests/api/test_auth_context_rbac.py` (**18** tests)

- Login success, wrong password, unknown email, inactive user, no password in response
- Token expiration, wrong `typ`, malformed token
- `/me` with valid token; inactive user rejected
- Salon context: active membership, missing membership, inactive salon, other user's salon
- Role from DB (token has no role claim)
- RBAC unit tests: owner/admin allowed; staff/receptionist denied

### Existing suites (unchanged behavior)

- **11** booking service tests  
- **22** availability tests  
- **14** API booking/availability tests  

### Exact test command

```bash
cd backend
export DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/liman_salon
python -m pytest tests/booking tests/availability tests/api -v
```

### Exact test results (final working tree)

```text
65 passed, 47 warnings in 1.41s
```

- **65 passed**, **0 failed** (47 prior + **18** new auth tests)
- Warnings: SQLAlchemy relationship overlap (booking tests); Starlette/httpx deprecation notice

---

## 6. Validation performed

| Check | Result |
|-------|--------|
| `pytest tests/booking tests/availability tests/api` | **PASS** — 65/65 |
| Schema/migrations | **NONE** |
| Live PostgreSQL integration | **Not run** (mocked auth repository in API tests) |
| Linter / formatter | **Not run** |
| Commit / push | **Not performed** |

---

## 7. Risks / edge cases

- **JWT secret** must be set to a strong value in production (`JWT_SECRET_KEY` env); dev default is for local use only.
- **No refresh tokens** — clients must re-login after access token expiry.
- **OAuth-only users** (`password_hash` NULL) cannot password-login until a separate flow exists.
- **Email casing in API responses** — Pydantic `EmailStr` may normalize domain; stored email casing may differ.
- **Public booking endpoints** remain open — must not expose sensitive data via responses (current responses are gaps/booking ids only).
- **`is_platform_admin`** not wired to admin bypass (intentional for this slice).

---

## 8. Anything intentionally not implemented

- Refresh tokens / session persistence / `user_sessions`
- Customer registration/login
- Auth on availability/booking routes
- Permission matrix beyond role names
- Platform-admin cross-tenant access
- `last_login_at` update on login
- Commit and push

---

## 9. Git status

**Branch:** `main` (up to date with `origin/main`)

**Latest commit:**

```text
f0e8a55 (tenant-scoped API foundation — per task brief)
```

**Working tree:**

```text
Changes not staged for commit:
	modified:   backend/app/api/errors.py
	modified:   backend/app/api/v1/router.py
	modified:   backend/app/core/config.py
	modified:   backend/pyproject.toml
	modified:   backend/tests/conftest.py

Untracked files:
	backend/app/api/schemas/auth.py
	backend/app/api/v1/auth_routes.py
	backend/app/auth/
	backend/app/core/security.py
	backend/tests/api/test_auth_context_rbac.py
	docs/reviews/auth-context-rbac-final-review.md

no changes added to commit
```

**Diff stat (tracked only):**

```text
 backend/app/api/errors.py    | 60 +++++++++++++++++++++++++++++++++
 backend/app/api/v1/router.py |  3 ++-
 backend/app/core/config.py  |  3 +++
 backend/pyproject.toml       |  3 +++
 backend/tests/conftest.py    |  8 +++++
 5 files changed, 76 insertions(+), 1 deletion(-)
```

**Commit:** None  
**Push:** None

---

## 10. Recommended next step

1. Architect review → commit auth module + tests; document required env vars (`JWT_SECRET_KEY`, `DATABASE_URL`).
2. Add **admin-protected** routes using `require_roles(...)` (e.g. staff management).
3. Decide when to protect vs keep public **booking/availability** endpoints for customer UX.
4. Optional: refresh-token strategy, `last_login_at` update, email verification gate on login.
5. CI: `pip install -e ".[dev]"` plus runtime deps; run full `pytest tests/booking tests/availability tests/api`.

---

## Final status

**READY FOR ARCHITECT REVIEW**
