# Architecture — Liman Salon MVP v0.1

This document describes the **planned** modular-monolith architecture for Liman Salon. It is the reference for module boundaries, tenancy, availability, and provider abstractions before and during implementation.

## Overview: modular monolith

Liman Salon is a **modular monolith**:

- One deployable application (MVP), divided into **cohesive modules** with explicit boundaries.
- Modules communicate through **application services** and shared kernel types—not through direct database access from unrelated modules or from AI tools.
- Enables incremental delivery (MVP v0.1) without splitting into microservices prematurely.

```
┌─────────────────────────────────────────────────────────────┐
│                    Liman Salon (monolith)                    │
│  ┌─────────┐ ┌─────────┐ ┌──────────┐ ┌─────────┐         │
│  │  auth   │ │ salons  │ │  staff   │ │ services│  ...    │
│  └────┬────┘ └────┬────┘ └────┬─────┘ └────┬────┘         │
│       │           │           │            │               │
│       └───────────┴───────────┴────────────┘               │
│                         │                                    │
│              Application services layer                      │
│                         │                                    │
│              PostgreSQL (tenant-scoped data)                 │
└─────────────────────────────────────────────────────────────┘
```

## Planned modules

| Module | Purpose |
|--------|---------|
| **auth** | Identity, sessions/roles, salon-scoped authorization |
| **salons** | Salon tenant root, settings, branding context |
| **staff** | Staff profiles, assignments, capacity |
| **services** | Service catalog, duration, pricing metadata |
| **schedule** | Working hours, blocked periods, staff calendars |
| **booking** | Appointments lifecycle (create, reschedule, cancel) |
| **customers** | Customer records and salon-scoped history |
| **bonuses** | Global / cross-cutting bonus rules (MVP level) |
| **reviews** | Feedback linked to visits or bookings |
| **notifications** | Outbound messages via provider abstraction |
| **ai** | Assistant orchestration over allowed tools only |
| **subscriptions** | Payment and subscription provider abstraction |

Modules may share a common **kernel** (IDs, `salon_id` conventions, errors) but must not leak persistence details across boundaries.

## Tenant isolation

- Each salon is a **tenant**. The canonical tenant key is **`salon_id`**.
- **All tenant-owned entities** carry `salon_id` (or are reachable only through aggregates that do).
- Queries and commands must **filter by `salon_id`** for the authenticated salon context; public booking flows resolve salon context explicitly (e.g. slug or domain) before reads/writes.

### Public salon entry (slug → tenant)

- **Human-facing URL pattern (future frontend):** `/s/{slug}` — not implemented in MVP backend; no QR or WhatsApp deep links in v0.1.
- **Resolver API (no auth):** `GET /api/v1/public/salons/{slug}` returns `salon_id`, `slug`, `name`, `currency_code`, and `timezone` for **active** salons only; missing or inactive slugs → **404** (`not_found`).
- **Slug storage:** `salons.slug` is unique, indexed (see initial migration), lowercase URL-safe; helpers in `app.services.salon_public.slug` normalize text and allocate `-2`, `-3`, … suffixes when creating salons later—no full salon CRUD in this slice.
- **Downstream public flows** may use either explicit `salon_id` paths (legacy/split clients) or slug-based public catalog reads after the client resolves slug once.
- Cross-tenant access is forbidden at the application layer; tests should assert isolation on critical paths.

### Public catalog flow (slug → services → staff → availability)

- **Purpose:** read-only public catalog and availability entry points for the future customer-facing booking UI (no frontend, QR, or WhatsApp in MVP backend).
- **Orchestration:** `PublicCatalogService` composes `SalonPublicService` (slug → active salon), `ServiceCatalogService` / `AvailabilityRepository` (tenant-scoped catalog reads), and **`AvailabilityService.get_service_availability`** (no duplicated availability math).
- **Endpoints (no auth):**
  - `GET /api/v1/public/salons/{slug}/services` — active services for the resolved salon, stable `sort_order` / name / id ordering, `currency_code` from salon.
  - `GET /api/v1/public/salons/{slug}/services/{service_id}/staff` — active, bookable staff assigned via `staff_services`; missing or inactive service → **404** (`not_found`); response exposes `id` and `display_name` only.
  - `GET /api/v1/public/salons/{slug}/availability/service` — same query contract as `GET /api/v1/salons/{salon_id}/availability/service` (`service_id`, `start_date`, `end_date`, optional `staff_id`; `as_of` server-injected).
- **Full public booking path (future UI):**
  1. `GET /api/v1/public/salons/{slug}`
  2. `GET /api/v1/public/salons/{slug}/services`
  3. `GET /api/v1/public/salons/{slug}/services/{service_id}/staff`
  4. `GET /api/v1/public/salons/{slug}/availability/service`
  5. `POST /api/v1/public/salons/{slug}/bookings`
- **Legacy split APIs remain:** `POST /api/v1/salons/{salon_id}/public/customers/resolve`, `POST /api/v1/salons/{salon_id}/bookings/public`, and salon-id availability are unchanged; slug catalog adds parallel read entry points only.
- **Booking authority:** holds and writes still flow through the existing public booking orchestrator / `BookingService`; this slice is read-only.

### Public orchestrated booking entry (slug → customer → hold)

- **Orchestrated API (no auth):** `POST /api/v1/public/salons/{slug}/bookings` — single public checkout entry that starts from the salon slug (no `salon_id` in the request body).
- **Flow:** `slug` → `SalonPublicService.resolve_public_salon_by_slug` → `CustomerService.resolve_public_customer` (salon-scoped, phone-keyed; existing customers are reused without profile overwrite) → `PublicBookingService.create_public_booking` (service-aware availability pre-check when applicable) → **`BookingService.create_booking`** as the sole booking write authority (`source=public`, `status=pending`, hold TTL from settings).
- **Response:** safe public fields only — `salon_id`, `customer_id`, `booking_id`, NET `service_start` / `service_end`, and `hold_expires_at` (not internal occupied/buffer bounds).
- **Legacy public APIs remain:** `GET /api/v1/public/salons/{slug}`, `POST /api/v1/salons/{salon_id}/public/customers/resolve`, and `POST /api/v1/salons/{salon_id}/bookings/public` are unchanged; clients may still resolve slug once and call the split endpoints.
- **Not in this slice:** QR/deep links, WhatsApp, notifications, campaigns, loyalty, or AI tools.
- **Atomicity:** `PublicBookingOrchestrator` does **not** wrap `BookingService.create_booking` in an outer transaction. Customer resolution may commit before a later booking failure (e.g. slot taken); that is a known limitation unless a future approved cross-service transaction design is added.

## Booking and schedule as source of truth for availability

**Availability is derived**, not stored as an unconstrained free-form calendar:

1. **Schedule** defines when staff (and salon) *can* work: working hours minus blocked periods.
2. **Booking** defines what is *already committed*: existing appointments reduce free capacity.
3. The **availability engine** combines schedule + booking rules (service duration, staff eligibility, buffers if any) to produce bookable slots for the public site and admin tools.

No module should treat “open slots” as authoritative without reconciling schedule and booking state.

## Provider abstractions

External capabilities are hidden behind interfaces so MVP can ship with one provider and swap later.

### Notifications

- Abstraction for outbound channels (e.g. WhatsApp, SMS, email).
- Domain events (booking confirmed, reminder, cancellation) call **notification application services**, not vendor SDKs from deep domain code.

### Payments / subscriptions

- Abstraction for charges, plans, and subscription state.
- Salon SaaS billing and optional customer payments stay behind this boundary until product rules are fixed.

### AI

- Abstraction for an **AI assistant** that orchestrates user intent.
- The assistant **never** connects to the database directly.

## AI tool boundaries

AI integration uses **controlled application services** only—the same entry points a well-behaved HTTP API would use.

**Rules:**

- Tools are explicit, auditable functions with salon context and authorization checks.
- No raw SQL, no ORM sessions, no bypass of `salon_id` scoping.
- Tool implementations live in the application layer and delegate to domain modules.

**Planned tools (future):**

| Tool | Responsibility |
|------|----------------|
| `get_services()` | List bookable services for the salon |
| `get_staff()` | List staff eligible for booking |
| `check_availability()` | Slots from schedule + booking rules |
| `create_booking()` | Create appointment with validation |
| `reschedule_booking()` | Move appointment with conflict checks |
| `cancel_booking()` | Cancel with policy hooks |

Additional tools require architect approval and updates to this document.

## Smart Gap Engine (future)

The **Smart Gap Engine** analyzes staff schedules (after blocks and existing bookings) to **identify idle gaps** and **suggest suitable services** that fit duration and staff skills.

- Inputs: schedule module, booking state, services/staff metadata.
- Outputs: suggestions for staff or admin (e.g. “30-minute gap — suggest express treatment X”).
- Not a separate source of truth for availability; it **reads** schedule and booking via application services.

## Evolution

Structural changes (new modules, revised boundaries, new AI tools) require **architecture approval** per [AGENTS.md](../AGENTS.md). Update this document when approved so implementers and agents share one source of truth.
