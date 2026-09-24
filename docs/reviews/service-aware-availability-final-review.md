# LIMAN SALON REVIEW REPORT

**Subject:** Service-aware availability (Smart Gap Engine) — pre-architect correction pass  
**Repository:** `liman-salon`  
**Base commit on `main`:** `2c7b9e4` — Implement schedule admin API  
**Report date:** 2026-09-24  
**Commit / push for this work:** None (per task instructions)

---

## 1. Task

### What was implemented

**Service-aware availability** via `AvailabilityService.get_service_availability(salon_id, service_id, start_date, end_date, as_of, staff_id optional)` and a **public, unauthenticated** HTTP endpoint:

| Method | Path | Auth | Behavior |
|--------|------|------|----------|
| `GET` | `/api/v1/salons/{salon_id}/availability/service` | none | Query: `service_id`, `start_date`, `end_date`, optional `staff_id`; `as_of` from server `ClockDep` / `AsOfDep` only |

Existing **`GET /api/v1/salons/{salon_id}/availability`** (duration-based free gaps) is **unchanged** in contract and tests.

#### Service resolution (tenant-scoped)

1. **`AvailabilityRepository.get_service_for_availability(salon_id, service_id)`** — loads the service row when it belongs to the salon (active or inactive).
2. **Missing in salon** (wrong id or other tenant’s id with this `salon_id` path) → **`ServiceNotFoundError`** → HTTP **404** `code: not_found` (no cross-tenant existence leak when the salon is already validated on the public path).
3. **Exists but `is_active=false`** → HTTP **200** with **`service_id` preserved** and **empty `staff`** (no slot computation).
4. **Active service** — same algorithm as before:
   - Fixed `staff_id`: include only if staff is `is_active`, `is_bookable`, and linked via `staff_services`.
   - No `staff_id`: all eligible linked staff (`sort_order`, `display_name`, `id`).
   - Reuse `get_free_gaps` per staff; bookings block on persisted `starts_at` / `ends_at`; pending blocks only when `expires_at > as_of`.
   - Minimum gap = `buffer_before + duration + buffer_after`; response slots via **`net_service_slots_from_free_gaps`** (NET window semantics **unchanged**).

### Explicitly NOT implemented

- Alembic migrations or SQLAlchemy model / schema changes
- Changes to `BookingService` or public booking POST
- Auth on the new public endpoint
- Precomputed slot tables or discrete slot grid stepping
- Modifications to existing `get_free_gaps` signature or behavior
- Commit / push

---

## 2. Files Changed

### Modified

| File | Change |
|------|--------|
| `backend/app/services/availability/types.py` | `ServiceForAvailability.is_active`; result/slot types unchanged |
| `backend/app/services/availability/repository.py` | `get_service_for_availability`; `get_active_service_for_availability` delegates |
| `backend/app/services/availability/service.py` | Missing → `ServiceNotFoundError`; inactive → empty staff |
| `backend/app/services/availability/intervals.py` | `net_service_slots_from_free_gaps()` (unchanged semantics) |
| `backend/app/api/schemas/availability.py` | Service availability response models |
| `backend/app/api/v1/availability.py` | `GET .../availability/service` route |
| `backend/app/api/errors.py` | Handlers for `ServiceNotFoundError` / `AvailabilityError` |
| `backend/tests/availability/test_service_availability.py` | Missing vs inactive + high-risk service-layer cases |
| `backend/tests/api/test_service_availability.py` | 404 missing vs 200 inactive API tests |
| `docs/reviews/service-aware-availability-final-review.md` | This report |

### New

| File | Change |
|------|--------|
| `backend/app/services/availability/errors.py` | `ServiceNotFoundError`, `AvailabilityError` |
| `backend/tests/availability/test_net_slots.py` | Interval helper edge case |
| `backend/tests/api/test_service_availability.py` | (if untracked on branch) HTTP wiring tests |

### Deleted

None.

---

## 3. Implementation Summary

- **`get_service_for_availability`:** tenant-scoped by `salon_id` + `service_id`; returns duration/buffers and `is_active`.
- **`get_service_availability`:** raises **`ServiceNotFoundError("service not found")`** when row absent; returns **`ServiceAvailabilityResult(service_id=..., staff=())`** when inactive; otherwise orchestrates staff list and NET slots.
- **HTTP:** exception handler maps **`ServiceNotFoundError`** → **404** / **`not_found`**; inactive path returns normal **200** JSON with empty `staff`.
- **Tenant isolation:** cross-tenant service ids under a validated salon path are indistinguishable from unknown ids (**404**). Inactive services in the same salon do not 404 (**200** empty).
- **`net_service_slots_from_free_gaps`:** not modified in this pass.

---

## 4. Database / Architecture Details

- **No** new tables, indexes, FKs, CHECK constraints, or migrations.
- Uses existing models: `Service`, `Staff`, `StaffService`, `WorkingHour`, `BlockedPeriod`, `Booking`, `Salon`.
- **Booking buffer convention:** persisted booking occupied bounds; availability read path does not re-apply buffers to booking rows.
- **Architecture boundary:** extended `app/services/availability/` and API error mapping only.
- **`BookingService`:** not modified.

---

## 5. Migration

**None.**

---

## 6. Validation

| Check | Result |
|-------|--------|
| `cd backend && python -m pytest tests/booking tests/availability tests/api -v --tb=short` | **PASS** — **197 passed**, 47 warnings (pre-existing Starlette/SQLAlchemy warnings) |
| `get_free_gaps` regression (`tests/availability/test_service.py`) | **PASS** — included in run |
| Existing `tests/api/test_availability.py` | **PASS** — included in run |
| App import without `DATABASE_URL` | **BLOCKED** — `Settings.database_url` required (tests use dependency overrides) |
| Formatter / static analysis | **Not run** |

### New / expanded test coverage (service-aware)

**Service layer** (`tests/availability/test_service_availability.py`): missing → `ServiceNotFoundError`; inactive → empty staff; fixed staff eligibility; any-staff list; salon-wide block; staff-specific block; confirmed booking; live pending; stale pending; buffers; exact-fit vs too-short gap; salon timezone on working day; NET buffer trim.

**API** (`tests/api/test_service_availability.py`): net slots wiring; `as_of` injection; missing service **404**; inactive **200** empty with `service_id`; no-auth smoke.

**Intervals** (`tests/availability/test_net_slots.py`): gap too short for buffers+duration.

---

## 7. Scope Verification

- Missing vs inactive distinction (404 vs 200 empty): **completed**
- Focused high-risk service-layer tests: **completed**
- NET-window semantics: **unchanged**
- `BookingService`, schema, migrations, public booking POST: **not modified**
- Commit / push: **not performed**

---

## 8. Git Status

- **Branch:** `main` (tracking `origin/main` at conversation start)
- **Commit:** none for this work
- **Push:** none
- **Modified (unstaged):** availability service/repository/types, API route/schemas, `errors.py`, tests, this doc
- **New (untracked):** `backend/app/services/availability/errors.py`, review doc and test files as applicable
- **Staged:** none

---

## 9. Issues / Limitations

- **Slot shape:** each qualifying gap yields one NET window (earliest start / latest end), not a discrete start-time grid.
- **Integration tests** against PostgreSQL not added; coverage uses mocked-repository and HTTP override patterns consistent with existing availability tests.
- **Salon existence** on the public path is not validated by availability service itself; 404 for service assumes caller uses a salon id already known to exist (same as other public catalog patterns).

---

## 10. Final Status

**READY FOR ARCHITECT REVIEW**

**Recommended next step:** architect approval of missing-vs-inactive HTTP contract; optional DB-backed integration tests for multi-staff service availability.
