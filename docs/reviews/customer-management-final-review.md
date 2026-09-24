# LIMAN SALON REVIEW REPORT

**Subject:** Customer Management + Public Customer Resolve  
**Repository:** `liman-salon`  
**Base commit on `main`:** `7239abf` — Implement public booking flow  
**Report date:** 2026-09-24  
**Commit / push for this work:** None (per task instructions)

---

## 1. Task

### What was implemented

**Admin customer CRUD (no delete)** with salon-scoped RBAC matching staff patterns:

| Method | Path | Auth / roles | Behavior |
|--------|------|--------------|----------|
| `GET` | `/api/v1/salons/{salon_id}/customers` | owner, admin, staff, receptionist | List with `q`, `limit` (1–200), `offset`, `sort` (`full_name`, `id`, optional `-` prefix for desc) |
| `GET` | `/api/v1/salons/{salon_id}/customers/{customer_id}` | same read roles | Tenant-scoped detail |
| `POST` | `/api/v1/salons/{salon_id}/customers` | owner, admin (write) | Create; `extra=forbid`; WhatsApp consent timestamps via `ClockDep` |
| `PATCH` | `/api/v1/salons/{salon_id}/customers/{customer_id}` | owner, admin (write) | Partial update; consent transitions; `extra=forbid` |
| `DELETE` | — | — | **Not implemented** (HTTP **405** on DELETE to customer path) |

**Public resolve (no auth):**

| Method | Path | Body | Response |
|--------|------|------|------------|
| `POST` | `/api/v1/salons/{salon_id}/public/customers/resolve` | `full_name`, `phone` required; `email` optional; `extra=forbid` | `{ "customer_id", "created" }` only |

**Resolve semantics:** Exact `phone` match within `salon_id`; if found → return existing `customer_id`, `created=false`, **no profile update**. If not found → insert with defaults (`notes=null`, opt-ins false, `user_id=null`). `IntegrityError` on insert/update → `CustomerConflictError` → HTTP **409** `conflict`.

**Non-writable via API:** `bonus_balance_cents`, `user_id` (omitted from request schemas; rejected if sent due to `extra=forbid`).

**Application layer:** `backend/app/services/customer/` (`errors`, `repository`, `service`, `types`).

### Explicitly NOT implemented

- DELETE customer endpoint or soft-delete flag
- Changes to `BookingService`, `PublicBookingService`, availability engine, SQLAlchemy `Customer` / `Booking` models, or Alembic migrations
- Linking customers to `users` from admin/public APIs
- Commit / push

---

## 2. Files Changed

### Modified

| File | Change |
|------|--------|
| `backend/app/api/deps.py` | `get_customer_service` / `CustomerServiceDep` |
| `backend/app/api/errors.py` | Handlers for `CustomerNotFoundError`, `CustomerConflictError`, `CustomerValidationError`, `CustomerError` |
| `backend/app/api/v1/router.py` | Register `customers` and `customers_public` routers |

### New

| File | Change |
|------|--------|
| `backend/app/services/customer/__init__.py` | Lazy export |
| `backend/app/services/customer/errors.py` | Domain errors |
| `backend/app/services/customer/repository.py` | List/get/by-phone/add/flush |
| `backend/app/services/customer/service.py` | Admin + public resolve logic, WhatsApp consent |
| `backend/app/services/customer/types.py` | `CustomerResolveResult` |
| `backend/app/api/schemas/customer.py` | Admin + public Pydantic models |
| `backend/app/api/v1/customers.py` | Authenticated customer routes |
| `backend/app/api/v1/customers_public.py` | Public resolve route |
| `backend/tests/api/test_customer_management.py` | Admin HTTP + RBAC tests (mock auth/service) |
| `backend/tests/api/test_public_customer_resolve.py` | Public resolve HTTP tests |
| `backend/tests/customer/__init__.py` | Package marker |
| `backend/tests/customer/test_service.py` | Service unit tests (resolve, consent, conflict) |
| `docs/reviews/customer-management-final-review.md` | This report |

### Deleted

None.

---

## 3. Implementation Summary

- **`CustomerRepository`:** Tenant-scoped queries; list search `q` matches `full_name`, `phone`, `email` (ILIKE); sort on `full_name` or `id`; phone lookup uses **exact equality** (not normalized).
- **`CustomerService`:** Admin create/update with `IntegrityError` → `CustomerConflictError`; WhatsApp opt-in: `false→true` sets `whatsapp_opt_in_at` from injected clock; `true→false` clears timestamp; create with `whatsapp_opt_in=true` sets timestamp on first write.
- **`resolve_public_customer`:** Phone hit short-circuits without mutating stored name/email; miss creates row with public defaults.
- **HTTP mapping:** 404 `not_found`, 409 `conflict`, 422 `validation_error` / Pydantic 422 for schema violations, 403 `forbidden` for role violations (same auth deps as staff).
- **Tenant isolation:** All repository filters include `salon_id`; admin routes use `SalonContext.salon_id` (path must match context).

---

## 4. Database / Architecture Details

- **No** migration or model changes in this task (read existing `Customer` model and migration `20250924_0007_customers.py`).
- **Existing constraints relevant to conflicts:**
  - Partial unique index `uq_customers_salon_id_email_lower` on `(salon_id, lower(email))` where `email IS NOT NULL` → duplicate email in same salon surfaces as `IntegrityError` → **409**.
  - **Phone is not unique** per salon (non-unique index `ix_customers_salon_id_phone` only); resolve relies on exact match lookup, not DB uniqueness on phone.
  - Composite unique `(salon_id, id)` supports composite FKs from bookings and related tables.
- **Architecture boundary:** New module `app.services.customer`; no direct DB access from routes; no changes to booking/public-booking write paths.

---

## 5. Migration

Not applicable — no migration created or modified.

---

## 6. Validation

| Check | Result |
|-------|--------|
| `cd backend && python -m pytest tests/booking tests/availability tests/api tests/public_booking -v --tb=short` | **PASS** — **240 passed** (baseline **215** + **25** new in-scope tests). Executed as `py -3 -m pytest …` on Windows (Python 3.14); `pytest` installed locally for this run. |
| `py -3 -m pytest tests/customer -v --tb=short` (supplementary service tests) | **PASS** — **6 passed** |
| Import / compile (via pytest collection) | **PASS** |
| Alembic | **BLOCKED** — not required for this task |
| Formatter / static (ruff/mypy) | **BLOCKED** — not run in this task |

---

## 7. Scope Verification

- Admin customer list/detail/create/patch, public resolve, service layer, schemas, error wiring, router registration, and tests: **completed**
- `BookingService`, `PublicBookingService`, availability service, customer/booking models, migrations: **not modified**
- Customer DELETE, user linking, phone normalization, bonus ledger APIs: **not implemented**
- Architecture docs (`docs/architecture.md`, `docs/database.md`): **not modified**

---

## 8. Git Status

- **Branch:** `main` (up to date with `origin/main`)
- **HEAD commit:** `7239abf` Implement public booking flow (working tree changes uncommitted)
- **Modified (unstaged):** `backend/app/api/deps.py`, `backend/app/api/errors.py`, `backend/app/api/v1/router.py`
- **Untracked:** `backend/app/api/schemas/customer.py`, `backend/app/api/v1/customers.py`, `backend/app/api/v1/customers_public.py`, `backend/app/services/customer/`, `backend/tests/api/test_customer_management.py`, `backend/tests/api/test_public_customer_resolve.py`, `backend/tests/customer/`, `docs/reviews/customer-management-final-review.md`
- **Staged:** none
- **Commit made:** no
- **Push made:** no

---

## 9. Issues / Limitations

- **Phone uniqueness:** Not enforced at DB level; duplicate phones in one salon are possible if created via admin API; resolve returns the first exact match only.
- **Email conflicts:** Case-insensitive uniqueness per salon; mixed-case duplicates rejected on flush.
- **Public resolve** does not verify salon exists before insert; invalid `salon_id` would fail at FK flush (likely **500** via generic SQLAlchemy handler) — acceptable MVP unless salon-exists check is added later.
- **Race on resolve:** Two concurrent resolves with the same new phone may create two rows (no unique phone constraint).

---

## 10. Final Status

**READY FOR ARCHITECT REVIEW**
