# LIMAN SALON REVIEW REPORT

**Subject:** Tenant-scoped FastAPI API foundation (Availability + Booking)  
**Repository:** `liman-salon`  
**Base commit on `main`:** `acf35a6` — *Implement booking service foundation*  
**Report date:** 2026-09-24  
**Commit / push for this work:** None (pending architect approval)

---

## 1. What was implemented

### API v1 (tenant-scoped)

- **`GET /api/v1/salons/{salon_id}/availability`** — returns free gaps via **`AvailabilityService.get_free_gaps`**, with **`as_of`** from injectable application clock (not client-controlled).
- **`POST /api/v1/salons/{salon_id}/bookings`** — creates bookings via **`BookingService.create_booking`**, with the same clock-derived **`as_of`**.

### Supporting layers

- **`app/api/deps.py`** — `SessionDep` (reuses `app.db.session.get_db`), `get_clock` / `get_as_of`, service factories for availability and booking.
- **`app/api/errors.py`** — maps booking domain errors to HTTP JSON; generic handler for unhandled **`SQLAlchemyError`** (no SQL leakage).
- **`app/api/schemas/`** — Pydantic request/response models for availability and bookings.
- **`app/api/v1/`** — modular routers wired into existing **`app/api/router.py`**; exception handlers registered in **`app/main.py`**.

### Minimal BookingService wiring change

- Renamed parameter **`notes` → `customer_notes`** and added optional **`internal_notes`** passthrough to the `Booking` ORM row (API request fields only; no change to booking business rules).

**Not implemented:** auth/RBAC, notifications, AI, payments, multi-staff availability, cancel/reschedule, frontend, live PostgreSQL API integration tests.

---

## 2. Files changed

### Modified (tracked)

| File | Change |
|------|--------|
| `backend/app/main.py` | Register `register_exception_handlers` |
| `backend/app/api/router.py` | Include `v1_router` |
| `backend/app/services/booking/service.py` | `customer_notes` / `internal_notes` parameters on `create_booking` |
| `backend/tests/booking/test_service.py` | `notes=` → `customer_notes=` |
| `backend/pyproject.toml` | `[project.optional-dependencies]` `dev`: `httpx>=0.27.0` (TestClient) |

### New (untracked)

| Path | Purpose |
|------|---------|
| `backend/app/api/deps.py` | Session, clock, `as_of`, service DI |
| `backend/app/api/errors.py` | HTTP error mapping |
| `backend/app/api/schemas/__init__.py` | Schema package |
| `backend/app/api/schemas/availability.py` | Gap response models |
| `backend/app/api/schemas/bookings.py` | Booking create request/response |
| `backend/app/api/v1/__init__.py` | v1 package |
| `backend/app/api/v1/router.py` | `/api/v1` aggregator |
| `backend/app/api/v1/availability.py` | Availability route |
| `backend/app/api/v1/bookings.py` | Booking create route |
| `backend/tests/api/__init__.py` | API test package |
| `backend/tests/api/conftest.py` | TestClient + clock overrides |
| `backend/tests/api/test_availability.py` | Availability API tests |
| `backend/tests/api/test_bookings.py` | Booking API tests |
| `docs/reviews/api-foundation-final-review.md` | This report |

### Unchanged by this task

- Database schema, Alembic migrations, SQLAlchemy models
- **`AvailabilityService`** interval/business logic (no rewrite)
- **`BookingService`** create flow rules (except note field wiring above)

---

## 3. Architecture decisions

### Exact API routes

| Method | Path | Status |
|--------|------|--------|
| `GET` | `/api/v1/salons/{salon_id}/availability` | 200 + `AvailabilityResponse` |
| `POST` | `/api/v1/salons/{salon_id}/bookings` | 201 + `BookingCreateResponse` |

Existing **`GET /health`** remains unchanged (no `/api/v1` prefix).

### Request / response schemas

**Availability query parameters**

- `staff_id` (UUID)
- `start_date`, `end_date` (date)
- `service_duration_minutes` (integer, `> 0`)

**`AvailabilityResponse`**

```json
{
  "gaps": [
    { "start": "<timezone-aware datetime>", "end": "<timezone-aware datetime>" }
  ]
}
```

Pydantic models: `AvailabilityGapOut`, `AvailabilityResponse`.

**`BookingCreateRequest` (JSON body)**

- `customer_id`, `staff_id`, `service_id` (UUID)
- `requested_service_start` (timezone-aware datetime)
- `source` (string)
- `status` (`"pending"` | `"confirmed"` only)
- `expires_at` (optional datetime)
- `customer_notes`, `internal_notes` (optional strings)

**Not accepted:** `as_of` (no client override).

**`BookingCreateResponse`**

- `booking_id`, `starts_at`, `ends_at`, `status`

### Dependency structure

```
HTTP request
  → SessionDep ← get_db() from app.db.session
  → AsOfDep ← get_as_of() ← get_clock() (default: datetime.now(UTC))
  → AvailabilityServiceDep / BookingServiceDep ← same Session
  → Application service method
```

Overrides in tests via `app.dependency_overrides[get_as_of]`, `get_availability_service`, `get_booking_service`.

### How `as_of` is generated and passed

1. **`get_clock()`** returns a callable (default: `datetime.now(timezone.utc)`).
2. **`get_as_of(clock)`** invokes it once per request.
3. Availability route passes **`as_of`** into **`get_free_gaps(..., as_of=as_of)`**.
4. Booking route passes **`as_of`** into **`create_booking(..., as_of=as_of)`** (also used for `confirmed_at` and hold validation inside BookingService).

Clients cannot supply `as_of` via query or body; extra fields are ignored by Pydantic schema.

### Error → HTTP mapping

| Exception | HTTP | JSON `code` |
|-----------|------|-------------|
| `BookingNotFoundError` | 404 | `not_found` |
| `BookingValidationError` | 422 | `validation_error` |
| `SlotNotAvailableError` | 409 | `slot_not_available` |
| `BookingOverlapError` | 409 | `booking_overlap` |
| Other `BookingError` | 422 | `booking_error` |
| `SQLAlchemyError` (unhandled) | 500 | `internal_error` (generic detail, no SQL) |

Body shape: `{ "detail": "<message>", "code": "<code>" }`.

FastAPI/Pydantic validation errors use default 422 (not custom body).

### Tenant isolation

- **`salon_id`** is always taken from the **path** `/salons/{salon_id}/...`.
- Passed explicitly into **`AvailabilityService`** / **`BookingService`**.
- Staff/customer/service IDs in query/body are **not** trusted alone; services enforce **`salon_id`** on all lookups (`BookingNotFoundError` → 404).

### Application-service reuse

- Routes **do not** query ORM models for business decisions.
- **No** duplicated availability math or overlap logic in routers.
- Booking status/source rules remain authoritative in **`BookingService`**.

### Buffer convention (unchanged — via BookingService)

- NET **`requested_service_start`** in API body.
- Occupied interval stored in **`starts_at` / `ends_at`** per existing booking service (buffers included in persisted bounds).

### Transaction boundary (unchanged)

- **`BookingService.create_booking`** still uses **`with self._session.begin():`** internally.
- API layer does not open a second transaction abstraction.

### Overlap / exclusion handling (unchanged)

- Pre-check → **`SlotNotAvailableError`** → HTTP 409.
- DB **`IntegrityError`** inside service → **`BookingOverlapError`** → HTTP 409.
- PostgreSQL exclusion constraint not modified.

---

## 4. DB changes

**NONE.**

- No migrations.
- No model/schema changes.
- API reads/writes only through existing services and session.

---

## 5. Tests added / run

### New API tests (14)

**`tests/api/test_availability.py` (3)**

- Returns gaps; passes salon/staff/duration/`as_of` to service
- Invalid duration → 422
- Client `as_of` query param does not override injected clock

**`tests/api/test_bookings.py` (11)**

- Delegates to BookingService; salon_id from path
- 404 / 422 / 409 mappings (not found, validation, slot, overlap)
- Invalid body → 422
- Client cannot override `as_of` in JSON body
- Unhandled SQLAlchemyError → 500 without SQL text in response
- Public pending expiry delegation

### Existing suites (unchanged count)

- **11** booking service tests
- **22** availability tests

### Exact test command

```bash
cd backend
export DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/liman_salon
python -m pytest tests/booking tests/availability tests/api -v
```

### Exact test results (final working tree)

```text
47 passed, 47 warnings in 0.71s
```

- **47 passed**, **0 failed**
- **14** API + **33** booking/availability = **47 total**
- Warnings: existing SQLAlchemy relationship overlap warnings on ORM mapper configure in booking tests

**Dependencies:** `httpx>=0.27.0` is declared under **`[project.optional-dependencies] dev`** in `backend/pyproject.toml`. Install for API tests with `pip install -e ".[dev]"` from `backend/` (Starlette `TestClient` requires httpx).

---

## 6. Validation performed

| Check | Result |
|-------|--------|
| `pytest tests/booking tests/availability tests/api` | **PASS** — 47/47 |
| OpenAPI / router inclusion | **PASS** — `v1_router` included from `create_app()` |
| Schema/migration diff | **NONE** |
| Live PostgreSQL API integration | **Not run** (mocked services) |
| Linter / formatter | **Not run** |
| Commit / push | **Not performed** |

---

## 7. Risks / edge cases

- **`BookingService` nested `session.begin()`** when the route also uses `get_db` session — callers should use one session per request (standard FastAPI pattern); nested begins may need review when wiring real DB integration tests.
- **Unhandled non-SQL exceptions** still use FastAPI default 500 (may expose detail if `debug=True` in settings).
- **Clean env:** install **`pip install -e ".[dev]"`** (or equivalent) so `httpx` is present before running `tests/api`.
- **No auth** — any client knowing `salon_id` can hit endpoints (expected for this foundation slice).
- **Minute-level availability check** for booking unchanged from booking service (integer minute spans).

---

## 8. Anything intentionally not implemented

- Authentication / authorization / RBAC
- Public vs admin route separation
- Customer registration/login
- Booking cancel/reschedule/list
- Notifications, WhatsApp, AI, payments
- Multi-staff / service-aware availability expansion
- Service buffers in general availability queries (only via booking occupied interval)
- Commit and push

---

## 9. Git status

**Branch:** `main` (up to date with `origin/main`)

**Latest commit:**

```text
acf35a6 Implement booking service foundation
```

**Working tree:**

```text
On branch main
Your branch is up to date with 'origin/main'.

Changes not staged for commit:
	modified:   backend/app/api/router.py
	modified:   backend/app/main.py
	modified:   backend/app/services/booking/service.py
	modified:   backend/pyproject.toml
	modified:   backend/tests/booking/test_service.py

Untracked files:
	backend/app/api/deps.py
	backend/app/api/errors.py
	backend/app/api/schemas/
	backend/app/api/v1/
	backend/tests/api/
	docs/reviews/api-foundation-final-review.md

no changes added to commit
```

**Diff stat (tracked files only):**

```text
 backend/app/api/router.py               |  2 ++
 backend/app/main.py                     |  2 ++
 backend/app/services/booking/service.py | 12 ++++++++----
 backend/pyproject.toml                  |  5 +++++
 backend/tests/booking/test_service.py   |  2 +-
 5 files changed, 18 insertions(+), 5 deletions(-)
```

**Commit:** None  
**Push:** None

---

## 10. Recommended next step

1. Architect review → commit API layer + tests (install with **`pip install -e ".[dev]"`** for CI).
2. Consider declaring **`pytest`** in the same optional `dev` group if CI lacks it.
3. Add auth middleware and salon context resolution (slug → `salon_id`) before public exposure.
4. PostgreSQL integration tests for end-to-end booking + exclusion constraint.
5. Optional: align session/transaction boundaries (`get_db` vs `BookingService.begin()`) for production FastAPI wiring.

---

## Final status

**READY FOR ARCHITECT REVIEW**
