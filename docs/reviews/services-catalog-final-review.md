# LIMAN SALON REVIEW REPORT

**Subject:** Admin services catalog + staff↔service assignments API  
**Repository:** `liman-salon`  
**Base commit on `main`:** `1992df2` — Staff Management admin API  
**Report date:** 2026-09-24  
**Commit / push for this work:** None (per task instructions)

---

## 1. Task

### What was implemented

Authenticated tenant-scoped **service catalog** admin API and **staff↔service assignment** endpoints under `/api/v1/salons/{salon_id}/services`. Handlers follow the staff module pattern: `get_current_user()` → `get_salon_context(salon_id, current_user)` → `require_roles(...)` → `ServiceCatalogService` → `ServiceCatalogRepository`.

| Method | Path | Roles | Behavior |
|--------|------|-------|----------|
| `GET` | `/api/v1/salons/{salon_id}/services` | owner, admin, staff, receptionist | List services; query `active_only` (default `true`); sort `sort_order`, `name`, `id` |
| `GET` | `/api/v1/salons/{salon_id}/services/{service_id}` | owner, admin, staff, receptionist | Detail; lookup by `(salon_id, service_id)` |
| `POST` | `/api/v1/salons/{salon_id}/services` | owner, admin | Create service in context salon |
| `PATCH` | `/api/v1/salons/{salon_id}/services/{service_id}` | owner, admin | Partial update; `is_active=false` soft deactivation |
| `DELETE` | `/api/v1/salons/{salon_id}/services/{service_id}` | owner, admin, staff, receptionist | **405 Method Not Allowed** (no hard delete) |
| `GET` | `/api/v1/salons/{salon_id}/services/{service_id}/staff` | owner, admin, staff, receptionist | List staff assigned to service; sort `sort_order`, `display_name`, `id` |
| `PUT` | `/api/v1/salons/{salon_id}/services/{service_id}/staff/{staff_id}` | owner, admin | Attach staff to service (idempotent) |
| `DELETE` | `/api/v1/salons/{salon_id}/services/{service_id}/staff/{staff_id}` | owner, admin | Detach junction row only (**204** when link exists; **404** if missing) |

### Role matrix

| Action | owner | admin | staff | receptionist |
|--------|:-----:|:-----:|:-----:|:------------:|
| List / detail services | yes | yes | yes | yes |
| Create / update service | yes | yes | no | no |
| DELETE service (405) | yes* | yes* | yes* | yes* |
| List service staff | yes | yes | yes | yes |
| Attach / detach staff | yes | yes | no | no |

\*Any authenticated read role receives **405** on service DELETE (endpoint exists only to reject deletion).

### Tenant isolation

- Persistence and queries use **`salon_id` from `SalonContext`**, not request body.
- Repository never loads `Service`, `Staff`, or `StaffService` by id alone without `salon_id`.
- Missing service/staff in tenant → **404** `not_found` (same response shape for cross-tenant probes).
- No active membership → **403** `salon_access_denied`.
- Wrong write role → **403** `forbidden`.
- Attach verifies **both** service and staff exist under the same `salon_id` before insert.

### Soft deactivate

Service removal is **`PATCH`** with **`is_active: false`**. Rows are not physically deleted.

### Staff↔service attach / detach / idempotency

- **PUT attach:** If `(salon_id, service_id, staff_id)` link missing, inserts `staff_services` row; if present, no-op. Returns **200** + `StaffResponse` either way.
- **DELETE detach:** Removes junction row when present (**204**); missing link → **404** `not_found` (staff must exist in tenant).

### Optional `currency_code`

`ServiceResponse` includes optional **`currency_code`**, populated from **`Service.salon.currency_code`** via `joinedload(Service.salon)` on catalog reads (not from auth context extension).

### Explicitly NOT implemented

- Hard DELETE of services or staff
- DB schema / Alembic migrations
- Changes to auth, `BookingService`, `AvailabilityService`, public booking/availability routes
- Pagination, bulk assign, service reorder API beyond `sort_order` field
- Commit / push

---

## 2. Files changed

### Modified

| File | Change |
|------|--------|
| `backend/app/api/deps.py` | `get_service_catalog_service`, `ServiceCatalogServiceDep` |
| `backend/app/api/errors.py` | Handlers for `ServiceCatalogNotFoundError`, `ServiceCatalogValidationError`, `ServiceCatalogError` |
| `backend/app/api/v1/router.py` | Include `services.router` |

### New

| File | Purpose |
|------|---------|
| `backend/app/api/schemas/services.py` | `ServiceCreateRequest`, `ServiceUpdateRequest`, `ServiceResponse` |
| `backend/app/api/v1/services.py` | Service catalog + staff assignment HTTP routes + RBAC |
| `backend/app/services/service_catalog/__init__.py` | Package export |
| `backend/app/services/service_catalog/errors.py` | Domain errors |
| `backend/app/services/service_catalog/repository.py` | Tenant-scoped SQLAlchemy access (`Service`, `Staff`, `StaffService`) |
| `backend/app/services/service_catalog/service.py` | Validation + attach/detach orchestration |
| `backend/tests/api/test_service_catalog.py` | API + service validation tests (32 tests) |
| `docs/reviews/services-catalog-final-review.md` | This report |

### Deleted

None.

---

## 3. Implementation summary

- **`ServiceCatalogRepository`:** `list_services`, `get_service_by_id` (with `joinedload(Service.salon)`), `list_staff_for_service` (join `staff_services` → `staff`), CRUD helpers for junction rows. All filters include `salon_id`.
- **`ServiceCatalogService`:** Create/update validation (`name`, `duration_minutes > 0`, non-negative buffers/price/sort_order). Uses `StaffRepository` for staff existence on attach/detach. Create reloads service after insert for salon currency. Attach is idempotent; detach removes link only (not staff/service entities).
- **Pydantic:** Request schemas mirror staff patterns (strip/validate name, numeric bounds). Response excludes `salon_id`; includes optional `currency_code`.
- **Routes:** `ReadSalonContext` / `WriteSalonContext` aliases match `staff.py`. `_assert_path_salon` guards path vs context.

---

## 4. Database / architecture details

**No schema changes.**

Uses existing models:

- **`services`** — tenant-scoped catalog; `UNIQUE (salon_id, id)`; CHECK on duration, buffers, price.
- **`staff_services`** — junction with composite FKs to `staff(salon_id, id)` and `services(salon_id, id)`; `UNIQUE (staff_id, service_id)`; CASCADE deletes on parent removal at DB level (API does not delete parents).

Architecture boundary: new module **`service_catalog`** (application service name avoids collision with SQLAlchemy `Service` entity and booking `ServiceSnapshot`).

---

## 5. Migration

**Not applicable** — no migration created or modified.

---

## 6. Validation

| Check | Status |
|-------|--------|
| `cd backend && python -m pytest tests/booking tests/availability tests/api -v --tb=short` | **PASS** — **123 passed**, 47 warnings, ~3.11s |
| `cd backend && python -m pytest tests/api/test_service_catalog.py -v --tb=short` | **PASS** — **32 passed**, 1 warning, ~1.17s |
| Baseline before this task (same combined paths) | **91 passed** |
| Delta | **+32** tests (123 − 91) |
| Alembic / live PostgreSQL integration | **NOT RUN** (API tests mock `ServiceCatalogService`; consistent with staff API tests) |
| App import without `DATABASE_URL` | **NOT RUN** / **BLOCKED** in bare shell (Settings requires `database_url`; pytest configures test env) |

---

## 7. Scope verification

| Item | Status |
|------|--------|
| Requested service catalog + staff↔service API | **Completed** |
| Unrelated refactors | **None** |
| Auth / booking / availability modules | **Unchanged** |
| Architecture docs (`docs/architecture.md`, `docs/database.md`) | **Not modified** (implementation aligns with existing `services` / `staff_services` tables) |

---

## 8. Git status

```text
On branch main
Your branch is up to date with 'origin/main'.

Changes not staged for commit:
	modified:   backend/app/api/deps.py
	modified:   backend/app/api/errors.py
	modified:   backend/app/api/v1/router.py

Untracked files:
	backend/app/api/schemas/services.py
	backend/app/api/v1/services.py
	backend/app/services/service_catalog/
	backend/tests/api/test_service_catalog.py
	docs/reviews/services-catalog-final-review.md

no changes added to commit
```

- **Branch:** `main` (up to date with `origin/main`)
- **HEAD:** `1992df2` Implement staff management admin API
- **Commit:** not made
- **Push:** not made

---

## 9. Issues / limitations

- **Integration gap:** API tests mock `ServiceCatalogService`; repository SQL, composite FK behavior, and DB CHECK constraints are not exercised end-to-end until integration tests exist.
- **Inactive services:** Default `active_only=true` hides deactivated services; admins pass `active_only=false` to list them.
- **Service DELETE:** Returns **405** for all roles (including read roles) once authenticated — intentional “no delete” surface.
- **SQLAlchemy relationship overlap warnings** in booking tests remain pre-existing and unchanged.
- **Detach when staff or link missing:** Returns **404** (staff must exist in tenant; relationship must exist to detach).

---

## 10. Final status

**Recommended next step:** **Working hours / blocked periods admin API** (schedule module), or thin **integration tests** for `ServiceCatalogRepository` against a test database to complement mocked API tests.

**Final status:** **READY FOR ARCHITECT REVIEW**
