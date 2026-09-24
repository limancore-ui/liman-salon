# LIMAN SALON REVIEW REPORT

**Subject:** Admin staff management API (first authenticated admin domain)  
**Repository:** `liman-salon`  
**Base commit on `main`:** `42aaf37` — Auth + SalonContext + RBAC foundation  
**Report date:** 2026-09-24  
**Commit / push for this work:** None (per task instructions)

---

## 1. What was implemented

### Authenticated tenant-scoped staff admin API

All routes live under **`/api/v1/salons/{salon_id}/staff`**. Every handler resolves:

`get_current_user()` → `get_salon_context(salon_id, current_user)` → `require_roles(...)` → `StaffService` → `StaffRepository`.

| Method | Path | Roles | Behavior |
|--------|------|-------|----------|
| `GET` | `/api/v1/salons/{salon_id}/staff` | owner, admin, staff, receptionist | List staff for salon; query `active_only` (default `true`), `bookable_only` (default `false`); sort `sort_order`, `display_name`, `id` |
| `GET` | `/api/v1/salons/{salon_id}/staff/{staff_id}` | owner, admin, staff, receptionist | Detail; lookup by `(salon_id, staff_id)` |
| `POST` | `/api/v1/salons/{salon_id}/staff` | owner, admin | Create staff in context salon |
| `PATCH` | `/api/v1/salons/{salon_id}/staff/{staff_id}` | owner, admin | Partial update; `is_active=false` soft deactivation |

**No `DELETE` endpoint.**

### Application layer

- **`StaffRepository`:** tenant-scoped queries only (`salon_id` in every read/write path).
- **`StaffService`:** create/update validation (blank `display_name`, `sort_order >= 0`, `#RRGGBB` `color_hex`).
- **Pydantic:** `StaffCreateRequest`, `StaffUpdateRequest`, `StaffResponse` (no `user_id`, no `salon_id` in responses beyond implicit tenant via URL).

### Role matrix

| Action | owner | admin | staff | receptionist |
|--------|:-----:|:-----:|:-----:|:------------:|
| List / detail | yes | yes | yes | yes |
| Create | yes | yes | no | no |
| Update (incl. deactivate) | yes | yes | no | no |

### Tenant isolation

- `salon_id` for persistence and queries comes from **`SalonContext`** (membership-resolved), not request body.
- Repository never loads by `staff_id` alone.
- Missing staff in tenant → **`404`** with code **`not_found`** (same as cross-tenant probe).
- No active membership → **`403`** **`salon_access_denied`**.
- Wrong write role → **`403`** **`forbidden`**.

### Soft-delete behavior

Deactivation is **`PATCH`** with **`is_active: false`**. Rows are not physically deleted.

### Staff ↔ user linking

**Not changed.** `staff.user_id` is not accepted on create/update and is not exposed in API responses. No user provisioning, invitations, or `salon_users` changes.

### Explicitly not implemented

- DELETE, pagination, staff↔user account linking, services/working-hours admin, schema/migrations, changes to auth, AvailabilityService, BookingService, or public booking routes.

---

## 2. Files changed

### Modified

| File | Change |
|------|--------|
| `backend/app/api/deps.py` | `get_staff_service`, `StaffServiceDep` |
| `backend/app/api/errors.py` | Handlers for `StaffNotFoundError`, `StaffValidationError`, `StaffError` |
| `backend/app/api/v1/router.py` | Include `staff.router` |

### New

| File | Purpose |
|------|---------|
| `backend/app/api/schemas/staff.py` | Request/response schemas |
| `backend/app/api/v1/staff.py` | Staff HTTP routes + RBAC deps |
| `backend/app/services/staff/__init__.py` | Package export |
| `backend/app/services/staff/errors.py` | Domain errors |
| `backend/app/services/staff/repository.py` | Tenant-scoped SQLAlchemy access |
| `backend/app/services/staff/service.py` | Business validation + orchestration |
| `backend/tests/api/test_staff_management.py` | Staff API + service validation tests |
| `docs/reviews/staff-management-final-review.md` | This report |

### Deleted

None.

### Unchanged (per task)

- SQLAlchemy `Staff` model, Alembic migrations, DB structure
- `backend/app/auth/*` semantics
- `AvailabilityService`, `BookingService`, `availability.py`, `bookings.py`

---

## 3. Architecture decisions

- **Layering:** Routes → Pydantic → `StaffService` → `StaffRepository` → SQLAlchemy (matches booking/availability API pattern).
- **RBAC:** Reuse `require_roles` with read vs write dependency aliases (`ReadSalonContext`, `WriteSalonContext`) on the staff router.
- **Path guard:** `_assert_path_salon` ensures route `salon_id` matches `SalonContext.salon_id` (defense in depth; context already keyed by path param).
- **Errors:** Staff domain errors mapped in `register_exception_handlers`; FastAPI/Pydantic request validation remains **422** for schema-level failures.
- **`updated_at`:** Relies on existing `TimestampMixin` / DB behavior on flush (no manual timestamp mutation in service).

---

## 4. DB changes

**None.**

- No new tables, columns, indexes, or migrations.
- No changes to `backend/app/db/models/staff.py`.
- Existing CHECK on `color_hex` remains enforced at DB layer; API validates `#RRGGBB` before insert/update.

---

## 5. Tests added/run

### New test file

`backend/tests/api/test_staff_management.py` — **26 tests**, including:

- Read roles (owner/admin/staff/receptionist), 401 unauthenticated, 403 no membership
- Tenant-scoped get/list; 404 not found / wrong tenant
- Create: owner/admin OK; staff/receptionist 403; validation (blank name, color, sort_order); body cannot override salon
- Update: owner/admin OK; staff/receptionist 403; soft deactivate; wrong tenant 404
- No DELETE (405)
- Cannot create in salon B without membership
- Unit-level `StaffService` validation (invalid color, negative sort_order)

API tests mock **`AuthRepository`** and **`StaffService`** (consistent with auth API tests; no live PostgreSQL required).

### Commands run

```text
cd backend
python -m pytest tests/booking tests/availability tests/api -v --tb=short
python -m pytest tests/api/test_staff_management.py -v --tb=short
```

### Results

| Run | Result |
|-----|--------|
| `tests/booking` + `tests/availability` + `tests/api` | **91 passed**, 47 warnings, ~2.13s |
| `tests/api/test_staff_management.py` only | **26 passed**, 1 warning, ~0.67s |

Prior baseline (before staff): **65 passed** in the same combined paths; **+26** staff tests; all prior tests remain green.

---

## 6. Validation performed

| Check | Status |
|-------|--------|
| `pytest tests/booking tests/availability tests/api -v` | **PASS** (91) |
| `pytest tests/api/test_staff_management.py -v` | **PASS** (26) |
| Alembic / live DB integration | **NOT RUN** (not required; mocked service layer in API tests) |
| Manual OpenAPI smoke | **NOT RUN** |

---

## 7. Risks / edge cases

- **Integration gap:** API tests mock `StaffService`; repository SQL and real DB constraints (e.g. duplicate display names if any) are not exercised end-to-end until integration tests exist.
- **Inactive staff listing:** With default `active_only=true`, deactivated staff disappear from list; admins must pass `active_only=false` to see them (by design).
- **Service vs Pydantic validation:** Some rules exist in both layers (color, sort_order); DB CHECK remains final authority for `color_hex`.
- **SQLAlchemy relationship overlap warnings** in booking tests (pre-existing) unchanged.

---

## 8. Anything intentionally not implemented

- DELETE and hard delete
- `user_id` read/write on API
- User/staff account provisioning and invitations
- Pagination
- Protecting or changing public availability/booking endpoints
- Services, working hours, blocked periods, or other admin domains
- Commits and pushes

---

## 9. Git status

```text
## main...origin/main
 M backend/app/api/deps.py
 M backend/app/api/errors.py
 M backend/app/api/v1/router.py
?? backend/app/api/schemas/staff.py
?? backend/app/api/v1/staff.py
?? backend/app/services/staff/
?? backend/tests/api/test_staff_management.py
?? docs/reviews/staff-management-final-review.md
```

- **Branch:** `main` (tracking `origin/main`)
- **Commit:** not made
- **Push:** not made

---

## 10. Recommended next step

**Services catalog admin API** (tenant-scoped CRUD for bookable services and optional `staff_services` links), reusing the same auth stack and repository/service layering—or add a thin **integration test** fixture for staff repository against SQLite/in-memory if the architect wants DB-level proof before expanding admin domains.

---

## Appendix — AGENTS.md cross-check

| Item | Status |
|------|--------|
| Tenant isolation via `salon_id` + membership | Yes |
| No schema/migration changes | Yes |
| No Availability/Booking/auth logic changes | Yes |
| Soft deactivation only | Yes |
| `user_id` linking unchanged | Yes |

**Final status:** **READY FOR ARCHITECT REVIEW**
