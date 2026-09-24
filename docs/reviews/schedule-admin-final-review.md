# LIMAN SALON REVIEW REPORT

**Subject:** Schedule Admin API (working hours + blocked periods)  
**Repository:** `liman-salon`  
**Base commit on `main`:** `d36cbd9` — Services Catalog + Staff↔Service Admin API  
**Report date:** 2026-09-24  
**Commit / push for this work:** None (per task instructions)

---

## 1. Task

### What was implemented

Authenticated tenant-scoped **schedule administration** CRUD for **`working_hours`** and **`blocked_periods`** under `/api/v1/salons/{salon_id}/schedule`. Handlers follow the staff/services pattern: `get_current_user()` → `get_salon_context(salon_id, current_user)` → `require_roles(...)` → `ScheduleService` → `ScheduleRepository`.

#### Working hours endpoints

| Method | Path | Roles | Behavior |
|--------|------|-------|----------|
| `GET` | `/api/v1/salons/{salon_id}/schedule/working-hours` | owner, admin, staff, receptionist | List rows; optional `staff_id` filter; sort NULL `staff_id` first, then `staff_id`, `day_of_week`, `start_time`, `id` |
| `POST` | `/api/v1/salons/{salon_id}/schedule/working-hours` | owner, admin | Create row; multiple windows per weekday allowed |
| `GET` | `/api/v1/salons/{salon_id}/schedule/working-hours/{working_hours_id}` | owner, admin, staff, receptionist | Tenant-scoped detail |
| `PATCH` | `/api/v1/salons/{salon_id}/schedule/working-hours/{working_hours_id}` | owner, admin | Partial update with final-state validation |
| `DELETE` | `/api/v1/salons/{salon_id}/schedule/working-hours/{working_hours_id}` | owner, admin | Hard delete row (**204**); **404** if missing in tenant |

#### Blocked periods endpoints

| Method | Path | Roles | Behavior |
|--------|------|-------|----------|
| `GET` | `/api/v1/salons/{salon_id}/schedule/blocked-periods` | owner, admin, staff, receptionist | List with optional `staff_id`, `starts_from`, `ends_to`, `block_type`; sort `starts_at`, `ends_at`, `id` |
| `POST` | `/api/v1/salons/{salon_id}/schedule/blocked-periods` | owner, admin | Create; `created_by_user_id` from `SalonContext.user_id` |
| `GET` | `/api/v1/salons/{salon_id}/schedule/blocked-periods/{blocked_period_id}` | owner, admin, staff, receptionist | Tenant-scoped detail |
| `PATCH` | `/api/v1/salons/{salon_id}/schedule/blocked-periods/{blocked_period_id}` | owner, admin | Partial update; creator immutable |
| `DELETE` | `/api/v1/salons/{salon_id}/schedule/blocked-periods/{blocked_period_id}` | owner, admin | Hard delete block row only (**204**); **404** if missing |

#### Role matrix

| Action | owner | admin | staff | receptionist |
|--------|:-----:|:-----:|:-----:|:------------:|
| List / detail (both resources) | yes | yes | yes | yes |
| Create / update / delete | yes | yes | no | no |

#### Semantics

- **`staff_id` NULL** → salon-wide default hours or salon-wide block.
- **`staff_id` set** → staff-specific row; staff must exist in the same `salon_id`.
- **Working hours times** → `TIME` values (local salon/staff interpretation per `docs/database.md`); admin API stores as provided.
- **Effective dates** → optional `effective_from` / `effective_to` (`DATE`); validated `effective_to >= effective_from` when both set.
- **Blocked period instants** → timezone-aware datetimes required on input; normalized to **UTC** before persist; `starts_at < ends_at`.
- **`block_type`** → `manual` \| `holiday` \| `time_off` (aligned with DB CHECK).
- **`created_by_user_id`** → set on create from authenticated user only; not accepted on create/update requests.

#### Tenant isolation

- All reads/writes use **`salon_id` from `SalonContext`**, never from body.
- Repository queries always filter by `salon_id` + entity id (no bare `session.get` by id).
- Cross-tenant or unknown staff → **404** `not_found` (`staff not found`).
- No membership → **403** `salon_access_denied`; wrong write role → **403** `forbidden`.

#### Delete semantics

- **Hard DELETE** for both entities (no soft-delete columns on these tables).
- Deletes only the target schedule row; does not cascade-delete staff, users, salons, or bookings.

### Explicitly NOT implemented

- Changes to **`AvailabilityService`**, **`BookingService`**, auth, public availability/booking routes
- DB schema / Alembic migrations
- Schedule merge/override algorithms (owned by availability layer)
- Pagination, bulk import, calendar UI
- Commit / push

---

## 2. Files changed

### Modified

| File | Change |
|------|--------|
| `backend/app/api/deps.py` | `get_schedule_service`, `ScheduleServiceDep` |
| `backend/app/api/errors.py` | Handlers for `ScheduleNotFoundError`, `ScheduleValidationError`, `ScheduleError` |
| `backend/app/api/v1/router.py` | Include `schedule.router` |

### New

| File | Change |
|------|--------|
| `backend/app/services/schedule/__init__.py` | Lazy export of `ScheduleService` |
| `backend/app/services/schedule/errors.py` | Domain errors |
| `backend/app/services/schedule/repository.py` | Tenant-scoped CRUD queries |
| `backend/app/services/schedule/service.py` | Validation, staff checks, UTC normalization, orchestration |
| `backend/app/api/schemas/schedule.py` | Pydantic request/response models (`extra=forbid` on writes) |
| `backend/app/api/v1/schedule.py` | HTTP routes |
| `backend/tests/api/test_schedule_admin.py` | API + service validation tests (sections 21–22) |
| `docs/reviews/schedule-admin-final-review.md` | This report |

### Deleted

None.

---

## 3. Implementation summary

- **`ScheduleRepository`**: `list_working_hours`, `get_working_hour_by_id`, `add_working_hour`, `delete_working_hour`; `list_blocked_periods` with overlap-friendly range filters (`ends_at > starts_from`, `starts_at < ends_to`), `get_blocked_period_by_id`, `add_blocked_period`, `delete_blocked_period`.
- **`ScheduleService`**: Validates day/time/effective ranges and block intervals; verifies staff via existing **`StaffRepository`**; assigns **`created_by_user_id`** on blocked-period create; re-loads after insert for consistent responses.
- **`schedule.py` router**: Separate read/write `SalonContext` dependencies; maps Pydantic bodies to frozen dataclasses; passes `context.user_id` into create blocked period.
- **Pydantic**: Create schemas reject extra fields (`salon_id`, `id`, timestamps, `created_by_user_id`); blocked-period datetimes must be timezone-aware at the HTTP boundary.

---

## 4. Database / architecture details

- Uses existing SQLAlchemy models **`WorkingHour`** and **`BlockedPeriod`** (no model edits).
- Composite FK `(salon_id, staff_id) → staff` enforced by existing schema when `staff_id` is non-null.
- **No** new indexes, CHECK constraints, or migration files.
- **Architecture boundary:** new `app/services/schedule/` module; HTTP → Pydantic → service → repository → ORM only.
- **`AvailabilityService` / `BookingService`:** not modified (confirmed by working tree — no changes under `backend/app/services/availability/` or `backend/app/services/booking/`).

---

## 5. Migration

**None.** No Alembic revisions created or altered.

---

## 6. Validation

| Check | Result |
|-------|--------|
| `python -m pytest tests/booking tests/availability tests/api -v --tb=short` | **PASS** — **177 passed** (baseline **123** + **54** new schedule tests), 47 warnings (pre-existing SQLAlchemy relationship overlap warnings) |
| `python -m pytest tests/api/test_schedule_admin.py -v --tb=short` | **PASS** — **54 passed** |
| App import with `create_app()` without `DATABASE_URL` | **BLOCKED** — `Settings.database_url` required (same as prior API tasks; tests use FastAPI dependency overrides) |
| Availability / booking test regression | **PASS** — included in combined run above |
| Formatter / static analysis | **Not run** |

---

## 7. Scope verification

- Requested schedule admin CRUD for working hours and blocked periods: **completed**
- Unrelated refactors, auth redesign, public routes, availability/booking behavior: **not performed**
- DB schema / migrations: **not changed**
- Commit / push: **not performed**

---

## 8. Git status

- **Branch:** `main`
- **Commit:** none for this work
- **Push:** none
- **Modified (unstaged):** `backend/app/api/deps.py`, `backend/app/api/errors.py`, `backend/app/api/v1/router.py`
- **Untracked:** `backend/app/api/schemas/schedule.py`, `backend/app/api/v1/schedule.py`, `backend/app/services/schedule/`, `backend/tests/api/test_schedule_admin.py`, `docs/reviews/schedule-admin-final-review.md`

---

## 9. Issues / limitations

- **List filters for blocked periods** use interval overlap with optional bounds (not full iCal recurrence); sufficient for admin listing, not a calendar export API.
- **Working-hour PATCH** final-state validation runs in the service layer; partial PATCH with only one of `start_time`/`end_time` can fail if the unchanged field leaves an invalid pair until both are updated (consistent with strict final-state rule).
- **Integration tests** against PostgreSQL are not added; coverage is mocked HTTP tests plus lightweight `ScheduleService` validation unit checks (same pattern as staff/services catalog).
- **Blocked period list** with `staff_id` filter returns only rows with that exact `staff_id` (salon-wide blocks with `staff_id` NULL are excluded when filter is set — matches column filter semantics).

---

## 10. Final status

**READY FOR ARCHITECT REVIEW**

**Recommended next step:** Service-aware availability reads (multi-staff / catalog-aware admin availability) or thin **repository integration tests** for `ScheduleRepository` against a test database to complement mocked API tests.
