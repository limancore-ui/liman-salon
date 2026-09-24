# LIMAN SALON REVIEW REPORT

**Subject:** Public Salon Entry Foundation 1.0  
**Repository:** `liman-salon`  
**Report date:** 2026-09-24  
**Commit / push for this work:** None (per task instructions)

---

## 1. Task

### What was implemented

- **No auth** `GET /api/v1/public/salons/{slug}` returning `salon_id`, `slug`, `name`, `currency_code`, `timezone` for active salons.
- Application service `SalonPublicService` with slug normalization on lookup and tenant-safe **404** for missing/inactive salons.
- Slug helpers (`normalize_salon_slug`, `dedupe_salon_slug`) for future salon creation; **no** salon admin CRUD changes.
- **Reused** existing `salons.slug` column and `UniqueConstraint("slug")` from migration `20250924_0001` — **no new Alembic migration**.

### Explicitly NOT implemented

- Frontend `/s/{slug}` page, QR codes, WhatsApp entry, analytics
- Changes to `BookingService`, `PublicBookingService`, availability engine
- Commit / push

---

## 2. Files Changed

See agent chat completion report section 2 for the authoritative list at review time.

---

## 3. Implementation Summary

- `SalonPublicRepository.get_active_salon_by_slug` filters `Salon.is_active.is_(True)`.
- `PublicSalonNotFoundError` → HTTP 404 `not_found` (same envelope as other not-found handlers).
- Response schema uses `extra=forbid` on the Pydantic model (public field allow-list enforced in tests).

---

## 4. Database / Architecture Details

- **No migration.** Slug uniqueness and `ck_salons_slug_min_length` unchanged from initial tenant-root migration.
- Public resolver is read-only; tenant isolation is by resolving to a single `salon_id` before other public APIs.

---

## 5. Migration

Not applicable (slug column pre-existing).

---

## 6. Validation

Run via agent chat report (pytest suites).

---

## 7. Scope Verification

Public salon entry foundation only; booking/availability/customer public paths unchanged.

---

## 8–10. Git / Issues / Status

See agent chat completion report.
