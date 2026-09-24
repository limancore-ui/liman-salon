# LIMAN SALON REVIEW REPORT

**Subject:** Public Booking Flow 2.0 — public checkout hold endpoint  
**Repository:** `liman-salon`  
**Base commit on `main`:** `258f27f` — Implement service-aware availability engine  
**Report date:** 2026-09-24  
**Commit / push for this work:** None (per task instructions)

---

## 1. Task

### What was implemented

**Public booking hold** via orchestrated application service and a **public, unauthenticated** HTTP endpoint:

| Method | Path | Auth | Behavior |
|--------|------|------|----------|
| `POST` | `/api/v1/salons/{salon_id}/bookings/public` | none | Body: `customer_id`, `service_id`, `staff_id`, `service_start` (tz-aware NET), optional `customer_notes`; `extra=forbid` |

**Server-controlled fields (not client-supplied):**

- `source` = `"public"`
- `status` = `"pending"`
- `as_of` = `AsOfDep` / `ClockDep` only
- `expires_at` (hold) = `as_of + PUBLIC_BOOKING_HOLD_SECONDS` from settings (env `PUBLIC_BOOKING_HOLD_SECONDS`)

**Orchestration:** `PublicBookingService.create_public_booking` → optional pre-check `AvailabilityService.is_service_slot_available(...)` (active services only) → **`BookingService.create_booking(...)`** as the sole write authority.

**Pre-check:** Not final; concurrent booking still surfaces as `SlotNotAvailableError` or `BookingOverlapError` → HTTP **409**.

**Errors:**

- Missing service in salon → `ServiceNotFoundError` → **404** `not_found`
- Inactive service → `BookingValidationError` from `BookingService` → **422** (same as admin create)
- Slot taken / race → **409** `slot_not_available` or `booking_overlap`

**Response (NET only, no occupied bounds leak):** `booking_id`, `status`, `service_id`, `staff_id`, `service_start`, `service_end` (NET end from service duration at create time), `hold_expires_at`.

### Explicitly NOT implemented

- Alembic migrations or SQLAlchemy model / schema changes
- Changes to `POST /salons/{salon_id}/bookings` contract or auth
- Changes to `GET .../availability/service` contract
- Auth on the new public endpoint
- Commit / push

---

## 2. Files Changed

### Modified

| File | Change |
|------|--------|
| `backend/app/core/config.py` | `public_booking_hold_seconds: int = 900` |
| `backend/app/services/availability/service.py` | `is_service_slot_available(...)` helper |
| `backend/app/api/deps.py` | `get_public_booking_service` / `PublicBookingServiceDep` |
| `backend/app/api/v1/bookings.py` | `POST .../bookings/public` route |

### New

| File | Change |
|------|--------|
| `backend/app/services/public_booking/__init__.py` | Package export |
| `backend/app/services/public_booking/types.py` | `PublicBookingResult` |
| `backend/app/services/public_booking/service.py` | `PublicBookingService` orchestration |
| `backend/app/api/schemas/public_booking.py` | Request/response Pydantic models (`extra=forbid` on request) |
| `backend/tests/api/test_public_booking.py` | HTTP wiring, validation, 404/409/422, no occupied leak |
| `backend/tests/public_booking/test_service.py` | Orchestration, pre-check, hold TTL, inactive skip |
| `backend/tests/availability/test_is_service_slot_available.py` | Helper unit tests |
| `docs/reviews/public-booking-flow-final-review.md` | This report |

### Deleted

None.

---

## 3. Implementation Summary

- **`AvailabilityService.is_service_slot_available`:** Tenant-scoped service load; `ServiceNotFoundError` if missing; `False` if inactive or staff ineligible; otherwise derives occupied interval via `compute_occupied_interval` and delegates to `is_occupied_interval_available`.
- **`PublicBookingService`:** Loads service for 404 early; pre-check only when `is_active`; sets hold from `public_booking_hold_seconds`; calls `create_booking` with `source=public`, `status=pending`, `requested_service_start=service_start`; builds NET `service_end` from service duration (not persisted occupied `starts_at`/`ends_at`).
- **HTTP:** Response model exposes NET times and `hold_expires_at` only; admin booking response unchanged (`starts_at`/`ends_at` occupied).
- **Tenant isolation:** `salon_id` from path passed through to all service/repository calls (unchanged pattern).

---

## 4. Database / Architecture Details

- **No** migration, model, or DB schema changes.
- **No** new foreign keys, indexes, or constraints.
- **Architecture boundary:** New orchestration module `app.services.public_booking`; writes remain exclusively in `BookingService` + existing repositories.

---

## 5. Migration

Not applicable — no migration created or modified.

---

## 6. Validation

| Check | Result |
|-------|--------|
| `cd backend && python -m pytest tests/booking tests/availability tests/api tests/public_booking -v --tb=short` | **PASS** — 215 passed (baseline 197 + 18 new) |
| Import / compile (via pytest collection) | **PASS** |
| Alembic | **BLOCKED** — not required for this task |
| Formatter / static (ruff/mypy) | **BLOCKED** — not run in this task |

---

## 7. Scope Verification

- Requested public endpoint, orchestration, availability helper, settings hold TTL, tests, and review doc: **completed**
- Unrelated refactors, auth changes, admin booking changes, availability GET changes: **not performed**
- Later features (payment, confirm hold, sweeper): **not implemented**
- Architecture docs (`docs/architecture.md`, `docs/database.md`): **not modified** (hold TTL documented here and in `Settings` default)

---

## 8. Git Status

- **Branch:** `main` (tracking `origin/main`)
- **HEAD commit:** `258f27f` Implement service-aware availability engine (working tree changes uncommitted)
- **Modified (unstaged):** `backend/app/api/deps.py`, `backend/app/api/v1/bookings.py`, `backend/app/core/config.py`, `backend/app/services/availability/service.py`
- **Untracked:** `backend/app/api/schemas/public_booking.py`, `backend/app/services/public_booking/`, `backend/tests/api/test_public_booking.py`, `backend/tests/availability/test_is_service_slot_available.py`, `backend/tests/public_booking/`, `docs/reviews/public-booking-flow-final-review.md`
- **Staged:** none
- **Commit made:** no
- **Push made:** no

---

## 9. Issues / Limitations

- **`PUBLIC_BOOKING_HOLD_SECONDS` default:** `900` (15 minutes), aligned with `docs/database.md` “10–15 minutes” guidance; override via environment.
- Pre-check vs create is intentionally racy; **409** on overlap is expected under concurrency.
- `service_end` in the public response uses duration from the service row loaded before create; if duration changed mid-flight, NET end could differ from a strict re-read (acceptable MVP; create still uses snapshot inside transaction).

---

## 10. Final Status

**READY FOR ARCHITECT REVIEW**
