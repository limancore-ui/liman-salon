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
| **bonuses** | Salon-scoped loyalty ledger (`BonusLedgerService`); earn on completed bookings and manual adjustments — see [Salon Bonus Ledger (C20)](#salon-bonus-ledger-c20--mvp) |
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
- **Flow:** `slug` → `SalonPublicService.resolve_public_salon_by_slug` → `CustomerService.resolve_public_customer` (salon-scoped, phone-keyed; existing customers are reused without profile overwrite) → `PublicBookingService.create_public_booking` (service-aware availability pre-check when applicable) → **`BookingService.create_booking`** as the sole booking write authority (`source=public`, `status=pending`, hold TTL resolved per salon — see **Salon settings JSONB** below).
- **Response:** safe public fields only — `salon_id`, `customer_id`, `booking_id`, NET `service_start` / `service_end`, and `hold_expires_at` (not internal occupied/buffer bounds).
- **Legacy public APIs remain:** `GET /api/v1/public/salons/{slug}`, `POST /api/v1/salons/{salon_id}/public/customers/resolve`, and `POST /api/v1/salons/{salon_id}/bookings/public` are unchanged; clients may still resolve slug once and call the split endpoints.
- **Not in this slice:** QR/deep links, WhatsApp, notifications, campaigns, loyalty, or AI tools.
- **Atomicity:** `PublicBookingOrchestrator` does **not** wrap `BookingService.create_booking` in an outer transaction. Customer resolution may commit before a later booking failure (e.g. slot taken); that is a known limitation unless a future approved cross-service transaction design is added.

### Salon settings JSONB (v0.1 contract)

- **Storage:** `salons.settings` JSONB (default `{}`) is the per-salon **business-settings** bucket. It is **not** exposed on public APIs; booking and admin flows read it only through application services (`BookingRepository.get_salon_settings` → typed parse in `app.services.salon_settings`).
- **v1 shape (only key in scope today):**

  ```json
  {
    "v": 1,
    "booking": {
      "public_hold_seconds": 900
    },
    "bonuses": {
      "enabled": false,
      "earn_percentage": 0
    }
  }
  ```

- **Bonuses (C20):** optional `bonuses.enabled` (default **`false`** when absent) and `bonuses.earn_percentage` (non-negative). When disabled or 0%, earn on booking completion is a **silent no-op**; completion must still succeed. Parsed via the same typed settings layer as booking keys; extend admin `GET`/`PATCH` settings when C20 APIs land (bonus settings UI deferred).

- **Pending hold TTL resolution** (public checkout and admin-created `pending` bookings): `settings.booking.public_hold_seconds` when present and valid → else deployment env `PUBLIC_BOOKING_HOLD_SECONDS` / `Settings.public_booking_hold_seconds` → else application default **900** seconds. Malformed non-empty JSONB fails closed (`SalonSettingsError`) rather than silently ignoring bad overrides.
- **Admin API (owner/admin, tenant-scoped):** `GET` and `PATCH` `/api/v1/salons/{salon_id}/settings` — read/update v1 JSONB via `SalonSettingsService` (merge PATCH, validate, persist). Path `salon_id` must match the authenticated salon context.
  - **GET / PATCH response body** mirrors stored v1 settings only (no derived TTL fields): `{ "v": 1 }` when the salon has no booking override (empty stored JSONB), or `{ "v": 1, "booking": { "public_hold_seconds": N } }` when a valid override is stored (`N` is 60–3600). Omitted keys are not returned (`response_model_exclude_none`).
  - **PATCH body:** partial update; only `booking` is in scope. Set `{ "booking": { "public_hold_seconds": N } }` to write or replace the override. **Clearing** the override is **only** `{ "booking": null }`, which removes `booking` from stored JSONB and persists `{}` — there is no `public_hold_seconds: null` clear mechanism. An empty PATCH `{}` is a no-op merge.
  - **Not in API responses:** `effective_public_hold_seconds`, `using_salon_override`, or any other computed “effective hold” / env-default disclosure; admins infer deployment fallback from product docs or ops config, while **runtime** hold TTL still follows **Pending hold TTL resolution** below.
- **Explicitly not in JSONB v0.1:** service **buffers** and duration (stay on `services` rows), **logo/branding** (Media attachments), **timezone** and **currency** (stay on `salons` columns). **Currency for bonus amounts** is always **`salons.currency_code`** (not duplicated in ledger rows for MVP).

## Salon Bonus Ledger (C20 — MVP)

Approved contract: [docs/reviews/c20-salon-bonus-ledger-architecture.md](reviews/c20-salon-bonus-ledger-architecture.md).

- **Write authority:** **`BonusLedgerService`** only — append `bonus_transactions` and update `customers.bonus_balance_cents` under the same `salon_id`.
- **Earn:** on booking **`completed`**, from **`bookings.price_cents`**, using salon **`bonuses.earn_percentage`** when **`bonuses.enabled`** is true; idempotency key **`earn:booking:{booking_id}`**; **`SELECT FOR UPDATE`** on the customer row; single DB transaction for ledger insert + balance cache.
- **Completion path:** **`confirmed → completed`** is allowed without `in_progress`. Booking completion and optional earn share **one transaction**; ledger failure **rolls back** completion. Disabled or zero-percent bonuses **must not** fail completion.
- **Clawback:** none in C20 — use **manual adjustment** only.
- **Admin APIs:** paginated ledger **GET** (owner, admin, staff, receptionist); adjustment **POST** (owner, admin) with mandatory description and non-negative balance invariant.
- **Deferred:** redeem, payments hooks, expire jobs, campaigns, per-service rates, public wallet, automatic clawback, `reverses_transaction_id`, HTTP `Idempotency-Key` header, bonus settings UI.

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
