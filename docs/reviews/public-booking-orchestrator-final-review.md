# Public Booking Orchestrator 1.0 — final review

## Connection report (pre-implementation inspection)

| Piece | Role in flow |
|-------|----------------|
| `GET /api/v1/public/salons/{slug}` | `SalonPublicService.resolve_public_salon_by_slug` → active salon metadata; missing/inactive → `PublicSalonNotFoundError` → 404 |
| `POST /api/v1/salons/{salon_id}/public/customers/resolve` | `CustomerService.resolve_public_customer` — create or reuse by phone within `salon_id`; existing rows not updated |
| `POST /api/v1/salons/{salon_id}/bookings/public` | `PublicBookingService.create_public_booking` — availability pre-check, then `BookingService.create_booking` |
| `BookingService` | Authoritative booking writes, overlap, staff/service eligibility, tenant scoping |

## New orchestrated entry

- **Service:** `PublicBookingOrchestrator` (`app.services.public_booking.orchestrator`)
- **Endpoint:** `POST /api/v1/public/salons/{slug}/bookings` (no auth)
- **Transaction note:** No nested transaction around `BookingService`; customer create may persist if booking later fails.

## Validation

Run targeted pytest suites under `backend/` (booking, availability, api, public_booking, customer, salon_public) and record counts in the agent completion report.
