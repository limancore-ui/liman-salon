# LIMAN SALON REVIEW REPORT

**Subject:** Availability timezone-boundary fix + BookingService foundation (final working-tree state)  
**Repository:** `liman-salon`  
**Base commit on `main`:** `6847f7b` — *Implement availability service foundation*  
**Report date:** 2026-09-24  
**Commit / push for this work:** None (pending architect approval)

---

## 1. What was implemented

### Availability layer (committed at `6847f7b`, plus local fix)

- **`AvailabilityService`** under `backend/app/services/availability/` computes free bookable gaps for one `(salon_id, staff_id)` from `working_hours`, `blocked_periods`, and blocking `bookings`.
- Pure helpers: working-window construction (salon IANA timezone → UTC), merge/subtract busy intervals, pending-hold blocking rules with explicit `as_of`.
- **`AvailabilityRepository`:** tenant-scoped SQLAlchemy reads; booking load uses bound `as_of` (no `now()` in SQL predicates).

### Architect fix (local, not yet committed)

- **`AvailabilityService.is_occupied_interval_available`** — added for booking slot checks; **timezone-boundary fix** so the date range passed to `get_free_gaps` is derived from **salon-local calendar dates**, not UTC `.date()` on occupied bounds.

### BookingService foundation (local, not yet committed)

- **`BookingService.create_booking(...)`** — single-transaction create flow for **`pending`** (public holds) and **`confirmed`** (trusted callers).
- **`BookingRepository`** — tenant-scoped entity loads, `staff_services` eligibility check, stale pending expiry update, booking insert + flush.
- **Domain types** (`ServiceSnapshot`, `OccupiedInterval`, `CreateBookingResult`) and **application errors** (`BookingValidationError`, `BookingNotFoundError`, `SlotNotAvailableError`, `BookingOverlapError`).

**Not implemented in this slice:** HTTP/API routes, auth, notifications, AI, reschedule/cancel/list, multi-staff search, service-layer buffers in availability reads (availability still filters by occupied span minutes at booking time), PostgreSQL integration tests, commit/push.

---

## 2. Files changed

### Modified (tracked, unstaged)

| File | Change |
|------|--------|
| `backend/app/services/availability/service.py` | Added `is_occupied_interval_available`; salon-local date derivation for gap query (timezone fix) |
| `backend/tests/availability/test_service.py` | Tests for occupied-interval helper + three timezone-boundary regressions |

### New (untracked)

**`backend/app/services/booking/`**

- `__init__.py`
- `errors.py`
- `repository.py`
- `service.py`
- `types.py`

**`backend/tests/booking/`**

- `__init__.py`
- `test_service.py`
- `test_types.py`

### Pre-existing from availability foundation (committed `6847f7b`, unchanged in this diff)

**`backend/app/services/`**

- `__init__.py`
- `availability/__init__.py`
- `availability/booking_block.py`
- `availability/intervals.py`
- `availability/repository.py`
- `availability/types.py`

**`backend/tests/`**

- `__init__.py`
- `conftest.py`
- `availability/__init__.py`
- `availability/test_booking_block.py`
- `availability/test_intervals.py`

### Database / migrations

- **No files** under `backend/alembic/` or `backend/app/db/models/` changed for this work.

### This review artifact

- `docs/reviews/booking-service-final-review.md` (this file)

---

## 3. Architecture decisions

### Layering

- **Application services** live under `backend/app/services/` with explicit repositories per domain (`availability`, `booking`).
- **BookingService** depends on **AvailabilityService** for pre-insert validation; it does not duplicate interval math.
- **SQLAlchemy `Session`** is injected; booking creation uses **`with self._session.begin():`** for one transaction boundary.

### Buffer convention (BookingService — explicit MVP choice)

Documented in `backend/app/services/booking/types.py` (`OccupiedInterval` docstring) and tested in `tests/booking/test_types.py`:

- **`requested_service_start`** = customer **NET** service start (the time the customer selected).
- **`occupied_start`** = `requested_service_start - buffer_before_minutes`
- **`occupied_end`** = `requested_service_start + duration_minutes + buffer_after_minutes`
- **Persisted on the booking row:** `bookings.starts_at = occupied_start`, `bookings.ends_at = occupied_end` (full occupied calendar interval including buffers).

Snapshots at create time: `price_cents`, `duration_minutes`, `currency_code` from salon + service; buffers affect stored `starts_at`/`ends_at` only via `compute_occupied_interval`.

### Mapping requested time → `starts_at` / `ends_at`

1. Load active service → `duration_minutes`, `buffer_before_minutes`, `buffer_after_minutes`, `price_cents`.
2. Load salon → `currency_code`.
3. `compute_occupied_interval(requested_service_start, …)` → `OccupiedInterval`.
4. Insert `Booking` with `starts_at=occupied.occupied_start`, `ends_at=occupied.occupied_end`, `duration_minutes=snapshot.duration_minutes` (net duration column, not including buffers in the integer field).

### Stale pending expiration

Before availability check and insert, **`BookingRepository.expire_stale_pending_holds`** runs in the **same transaction**:

- **Filter:** `salon_id`, `staff_id`, `status = 'pending'`, `expires_at IS NOT NULL`, **`expires_at <= as_of`**, overlaps occupied window (`starts_at < window_end AND ends_at > window_start`).
- **Action:** `UPDATE … SET status = 'expired'`.
- **Clock:** caller-supplied **`as_of`** only — no `now()` in SQL.

Stale definition: `expires_at <= as_of`.

### Explicit `as_of` usage

| Location | Role |
|----------|------|
| `create_booking(..., as_of=…)` | Public hold validation (`expires_at > as_of`); confirmed `confirmed_at = as_of` |
| `expire_stale_pending_holds(…, as_of=…)` | Expire stale pending holds |
| `AvailabilityService.get_free_gaps(…, as_of=…)` | Pending blocks only if `expires_at > as_of` |
| `AvailabilityService.is_occupied_interval_available(…, as_of=…)` | Forwarded to `get_free_gaps` |
| `booking_block.booking_blocks_availability` | Pure duplicate guard when converting bookings to busy intervals |

### Tenant isolation

Every booking-path lookup includes **`salon_id`**:

- `get_customer(salon_id, customer_id)`
- `get_staff(salon_id, staff_id)`
- `get_service(salon_id, service_id)`
- `staff_performs_service(salon_id, staff_id, service_id)` on **`staff_services`**
- `get_salon_currency(salon_id)` — missing salon → `BookingNotFoundError`

Cross-salon IDs are rejected as “not found for salon” or validation failures. **`staff_id` is never used without `salon_id`.**

### `staff_services` eligibility

`BookingRepository.staff_performs_service` requires a row:

```text
StaffService.salon_id = salon_id
AND StaffService.staff_id = staff_id
AND StaffService.service_id = service_id
```

Missing link → `BookingValidationError("staff does not perform this service")`.

Additional gates: `service.is_active`, `staff.is_active`, `staff.is_bookable`.

### AvailabilityService reuse

- `BookingService.__init__` constructs **`AvailabilityService(session)`** sharing the same session/repository stack.
- Pre-insert check: **`is_occupied_interval_available(salon_id, staff_id, occupied_start, occupied_end, as_of)`**.
- That method calls **`get_free_gaps`** with minimum gap length = occupied span in whole minutes, then tests half-open containment: `gap.start <= occupied_start and gap.end >= occupied_end`.

### Timezone-boundary fix (`availability/service.py` modified: **yes**)

**Problem (pre-fix):** `is_occupied_interval_available` used `occupied_start.date()` / `occupied_end.date()` in **UTC**, which could omit the correct **salon-local calendar day** near midnight.

**Fix (current code):**

1. Load salon IANA timezone via `self._repo.get_salon_timezone(salon_id)` (same as `get_free_gaps`).
2. `tz = ZoneInfo(tz_name)`.
3. `start_date = occupied_start.astimezone(tz).date()`
4. `end_date = occupied_end.astimezone(tz).date()`
5. Pass inclusive local `start_date` / `end_date` into `get_free_gaps`, which already converts salon-local dates to UTC bounds via `salon_local_date_range_to_utc_bounds`.

**Preserved:** explicit `as_of`, half-open `[occupied_start, occupied_end)` semantics, existing pending/confirmed blocking rules inside `get_free_gaps`.

### Transaction boundary

```text
create_booking
  → _validate_status_and_hold (outside begin — hold rules)
  → with session.begin():
       validate entities + snapshot + occupied interval
       expire_stale_pending_holds
       is_occupied_interval_available
       insert Booking + flush
```

### Overlap / exclusion conflict handling

- Application pre-check → **`SlotNotAvailableError`** if no containing free gap.
- **`IntegrityError`** on flush (PostgreSQL exclusion / overlap constraint) → **`BookingOverlapError`** with message *"booking overlaps an existing appointment"*.
- **No change** to DB exclusion constraint or migrations; app check is friendly validation only.

### Working hours (availability, unchanged in booking task)

Staff-specific rows **override** salon defaults for a weekday when any staff row applies (not merged with salon for that day). Documented behavior from availability foundation.

---

## 4. DB changes

**NONE.**

- No Alembic migrations created or modified.
- No SQLAlchemy model changes.
- No schema edits.
- BookingService reads/writes existing **`bookings`** table columns only through the ORM.

---

## 5. Tests added / run

### Booking tests (11) — `backend/tests/booking/`

| Test | Coverage |
|------|----------|
| `test_buffer_convention_occupied_bounds_persisted_on_booking_row` | Buffer convention / occupied bounds |
| `test_create_confirmed_persists_occupied_and_snapshots` | Confirmed create, snapshots, occupied persistence |
| `test_public_pending_requires_expires_at_after_as_of` | Public pending validation |
| `test_confirmed_rejects_expires_at` | Confirmed must not set expires_at |
| `test_expire_stale_pending_called_with_occupied_window` | Stale expiry invoked with occupied window |
| `test_tenant_isolation_unknown_staff` | Tenant mismatch |
| `test_inactive_service_rejected` | Inactive service |
| `test_staff_service_link_required` | staff_services link |
| `test_slot_not_available` | Availability rejection |
| `test_integrity_error_becomes_overlap_error` | Overlap mapping |
| `test_public_pending_success_sets_expires_at` | Successful public pending |

### Availability tests (22) — `backend/tests/availability/`

Includes original 19 plus **3 timezone regressions** on `is_occupied_interval_available`:

- `test_is_occupied_uses_salon_local_dates_ahead_of_utc`
- `test_is_occupied_uses_salon_local_dates_behind_utc`
- `test_is_occupied_available_when_utc_date_differs_from_salon_local`

Plus booking-block, interval, and service tests from availability foundation.

### Exact test command

```bash
cd backend
# Requires DATABASE_URL (see tests/conftest.py), e.g.:
# set DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/liman_salon
python -m pytest tests/booking tests/availability -v
```

### Exact test results (executed on final working tree)

```text
======================= 33 passed, 46 warnings in 0.84s =======================
```

- **33 passed**, **0 failed**
- **46 warnings** — SQLAlchemy `SAWarning` relationship overlap warnings when booking tests instantiate ORM models (pre-existing model relationship pattern, not introduced by booking logic)

**Breakdown:** 11 booking + 22 availability = **33 total**.

---

## 6. Validation performed

| Check | Result |
|-------|--------|
| `python -m pytest tests/booking tests/availability -v` | **PASS** — 33 passed |
| Schema / Alembic diff | **NONE** — no migration files touched |
| Live PostgreSQL integration | **Not run** — booking/availability service tests use mocks |
| Linter / formatter (ruff, mypy) | **Not run** |
| Commit / push | **Not performed** |

**Environment note:** Importing application modules loads `app.db.session`, which requires **`DATABASE_URL`**. Tests set this in `backend/tests/conftest.py`. Use `postgresql+psycopg://` when psycopg3 is installed; bare `postgresql://` may attempt psycopg2.

---

## 7. Risks / edge cases

- **Minute truncation:** Occupied span and gap filtering use integer `// 60` minutes; sub-minute buffers/durations truncate.
- **Pending without `expires_at`:** Never blocks availability reads; public create rejects missing/invalid expiry; DB exclusion may still see raw `pending` until write-path expiry — aligned with `docs/database.md` (expire before overlap-safe write).
- **Staff vs salon working hours:** Full-day override per weekday may differ if product expects merge/intersection semantics.
- **No live DB tests:** Overlap constraint behavior verified only via mocked `IntegrityError` in unit tests.
- **`create_booking` status surface:** Only `pending` and `confirmed` creation supported in this foundation (not full lifecycle).
- **Session nesting:** Callers must supply a Session compatible with `session.begin()` (same pattern as future FastAPI `get_db`).

---

## 8. Anything intentionally not implemented

- FastAPI routes / Pydantic request schemas
- Authentication / authorization
- Notifications, payments checkout, AI providers
- Booking reschedule, cancel, list, status transitions beyond create + stale expiry
- Multi-staff / `service_id`-driven candidate search in availability
- Applying service buffers inside `get_free_gaps` for general queries (buffers applied at booking via occupied interval only)
- Global pending sweeper (only window-scoped expiry on create path)
- PostgreSQL integration test harness
- Git commit and push

---

## 9. Git status

**Branch:** `main` (up to date with `origin/main`)

**Latest commit on branch:**

```text
6847f7b Implement availability service foundation
```

**Working tree (final state for this review):**

```text
On branch main
Your branch is up to date with 'origin/main'.

Changes not staged for commit:
	modified:   backend/app/services/availability/service.py
	modified:   backend/tests/availability/test_service.py

Untracked files:
	backend/app/services/booking/
	backend/tests/booking/
	docs/reviews/booking-service-final-review.md

no changes added to commit
```

**Diff stat vs HEAD (tracked files only):**

```text
 backend/app/services/availability/service.py | 43 +++++++++++++++++
 backend/tests/availability/test_service.py   | 71 +++++++++++++++++++++++++++-
 2 files changed, 113 insertions(+), 1 deletion(-)
```

**Commit:** None  
**Push:** None

---

## 10. Recommended next step

1. **Architect sign-off** on buffer convention vs `docs/database.md` Smart Gap occupied-interval wording (booking path is consistent internally).
2. **Single commit** (or two: booking service + TZ fix) including `backend/app/services/booking/`, modified availability service/tests, and `backend/tests/booking/`.
3. Wire **`BookingService`** into tenant-scoped API with explicit **`as_of`** from request/clock policy.
4. Add PostgreSQL integration tests for exclusion constraint + expiry + availability alignment.
5. Optional: extend availability for multi-staff search and service buffers on read path when product requires it.

---

## Final status

**READY FOR ARCHITECT REVIEW** (post timezone-boundary fix; BookingService foundation complete in working tree; tests green)
