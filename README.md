# Liman Salon MVP v0.1

**Liman Salon** is a modular-monolith SaaS platform for beauty salons. MVP v0.1 establishes the product scope, architecture, and development practices before incremental implementation begins.

## Project goal

Deliver a multi-tenant salon management and booking product that salon owners and staff can run day to day, while customers can discover availability and book services through a public booking experience. The codebase is organized as a **modular monolith**: clear module boundaries, shared deployment, and room to evolve without premature microservices.

## MVP scope

The following capabilities are in scope for **Liman Salon MVP v0.1**:

| Area | Description |
|------|-------------|
| **Salon admin** | Configure salon profile, settings, and operational data |
| **Staff** | Manage stylists and other staff tied to the salon |
| **Services** | Define bookable services (duration, pricing context, assignments) |
| **Working hours** | Salon and staff availability windows |
| **Blocked periods** | Time off, holidays, and manual blocks |
| **Customers** | Customer records and booking history context |
| **Booking** | Create, reschedule, and cancel appointments |
| **Availability engine** | Derive bookable slots from schedule and booking rules |
| **Public booking site** | Customer-facing flow to pick service, staff, and time |
| **Admin dashboard** | Operational overview for salon owners |
| **Global bonuses** | Cross-cutting bonus / loyalty concepts (MVP-level) |
| **Reviews** | Post-visit feedback tied to bookings or customers |
| **WhatsApp notification abstraction** | Provider-agnostic notification interface (WhatsApp as first target) |
| **Payment / subscription abstraction** | Provider-agnostic billing hooks for future monetization |
| **AI assistant abstraction** | Controlled assistant entry point over application services |
| **Smart Gap Engine** | Identify gaps in staff schedules and suggest suitable services (planned capability) |

Detailed module boundaries and isolation rules live in [docs/architecture.md](docs/architecture.md).

## Delivery milestones (architecture)

Incremental slices are documented as they are approved. Implementation may lag the contract docs.

| Milestone | Name | Architecture contract |
|-----------|------|------------------------|
| **C20** | Salon Bonus Ledger (MVP) | [docs/reviews/c20-salon-bonus-ledger-architecture.md](docs/reviews/c20-salon-bonus-ledger-architecture.md) |

## Planned tech stack

Implementation has **not** started in this repository phase; the following stack is **planned**:

- **Backend:** Python, FastAPI, PostgreSQL, SQLAlchemy, Alembic, Pydantic
- **Frontend:** React, Vite

Infrastructure, CI, and packaging choices will be documented as they are approved.

## Development approach

- **Small incremental changes** — prefer thin vertical slices over large rewrites.
- **Modular monolith** — respect module boundaries; avoid cross-module shortcuts that bypass tenant or domain rules.
- **Architecture approval before change** — structural or cross-cutting changes require alignment with the architect/lead (see [AGENTS.md](AGENTS.md)) before implementation proceeds.

## Repository

- **GitHub:** [https://github.com/limancore-ui/liman-salon.git](https://github.com/limancore-ui/liman-salon.git)

## Documentation

- [AGENTS.md](AGENTS.md) — rules for human developers and AI implementers
- [docs/architecture.md](docs/architecture.md) — modular monolith design, modules, tenant isolation, and provider abstractions
- [docs/reviews/c20-salon-bonus-ledger-architecture.md](docs/reviews/c20-salon-bonus-ledger-architecture.md) — C20 bonus ledger MVP (approved contract)
