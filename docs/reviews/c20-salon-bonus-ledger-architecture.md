# C20 — Salon Bonus Ledger (MVP) — Architecture formalization

**Repository:** `liman-salon`  
**Milestone:** **C20 — Salon Bonus Ledger (MVP)**  
**Document type:** Approved architecture contract (documentation only; no implementation in this milestone slice)  
**Related:** [architecture.md](../architecture.md), [database.md](../database.md)

---

## 1. Purpose

Formalize the **salon-scoped bonus ledger** for MVP: earn on completed bookings, manual adjustments, admin read APIs, and tenant isolation. All ledger writes go through **`BonusLedgerService`**; booking completion coordinates earn in the **same database transaction** as the status transition.

**Explicitly out of C20 implementation scope:** automated tests (separate implementation phase), redeem at checkout, payments integration, expiry jobs, campaigns, per-service earn rates, public customer wallet UI, automatic clawback on cancellation, `reverses_transaction_id`, HTTP `Idempotency-Key` header standard, bonus settings admin UI.

---

## 2. Approved product and policy decisions

| # | Decision |
|---|----------|
| 1 | **Complete path:** `confirmed → completed` is allowed **directly** (skipping `in_progress` is valid). |
| 2 | **Bonus policy:** Opt-in per salon; **`bonuses.enabled` defaults to `false`**. |
| 3 | **Disabled / 0% earn:** **Silent no-op** — no ledger row, no balance change. **Booking completion must not fail** when bonuses are disabled or earn percentage is zero. |
| 4 | **Ledger failure:** `BonusLedgerService` earn runs in the **same DB transaction** as booking completion; any ledger error **rolls back** the completion (booking stays non-terminal). |
| 5 | **Clawback:** **No automatic clawback** in C20; corrections use **manual adjustment** only. |
| 6 | **Ledger read RBAC:** `owner`, `admin`, `staff`, `receptionist`. |
| 7 | **Adjustment RBAC:** `owner`, `admin` only; **no separate cap** on adjustment amount; **mandatory** reason/description; resulting balance **must not go negative**. |

---

## 3. C20 MVP scope (implementer contract)

### Write authority

- **`BonusLedgerService`** is the **sole write point** for `bonus_transactions` and updates to `customers.bonus_balance_cents` (same `salon_id`).
- No other module or route inserts or patches ledger rows directly.

### Salon settings

- Stored in `salons.settings` JSONB v1 under **`bonuses`** (see [architecture.md](../architecture.md#salon-settings-jsonb-v01-contract)).
- **`bonuses.enabled`** — boolean, default **`false`** when absent (treated as disabled).
- **`earn_percentage`** — non-negative number (salon policy); **0** behaves like disabled for earn (silent no-op).

### Earn rules

- Trigger: booking transitions to **`completed`** (from `confirmed` or `in_progress` per [Booking status](../database.md#booking-status)).
- **Amount base:** `bookings.price_cents` at completion time (booking snapshot field, not live catalog price).
- **Formula (app):** `floor(price_cents * earn_percentage / 100)` or equivalent integer-safe rounding policy documented in service; **zero earn** → no insert.
- **Currency:** display and API semantics use **`salons.currency_code`** (no per-transaction currency column in MVP).
- **Idempotency:** ledger insert uses **`idempotency_key = earn:booking:{booking_id}`** (unique per `salon_id` when set). Repeat completion/earn attempts must not double-credit.

### Concurrency and atomicity

- Before balance update: **`SELECT … FOR UPDATE`** on the tenant-scoped **`customers`** row (`salon_id`, `customer_id`).
- Same transaction: append **`bonus_transactions`** row (with `balance_after_cents`) and update **`customers.bonus_balance_cents`** cache.

### Booking completion integration

- Booking lifecycle command (e.g. complete booking application service) opens one transaction:
  1. Validate transition (including **`confirmed → completed`**).
  2. Persist booking terminal state and timestamps.
  3. Invoke **`BonusLedgerService`** earn hook when policy yields a positive earn; otherwise skip silently.
- **Do not** treat disabled bonuses as an error on the completion path.

### Admin HTTP surface (tenant-scoped)

| Method | Path (conceptual) | Roles | Behavior |
|--------|-------------------|-------|----------|
| `GET` | `/api/v1/salons/{salon_id}/customers/{customer_id}/bonus-transactions` | owner, admin, staff, receptionist | Paginated ledger history for one customer; `salon_id` must match auth context. |
| `POST` | `/api/v1/salons/{salon_id}/customers/{customer_id}/bonus-transactions/adjustment` | owner, admin | Manual **`adjustment`** row; **required** description/reason; reject if balance would go **negative**. |

Pagination parameters and response shapes are defined at implementation time; must preserve **`salon_id`** filtering on every query.

### Tenant isolation

- All reads and writes filter by authenticated or resolved **`salon_id`**.
- Composite FKs `(salon_id, customer_id)` and `(salon_id, booking_id)` remain mandatory (see [database.md](../database.md)).

---

## 4. C20 deferred (not in MVP contract)

- Redeem at checkout and bonus-as-payment
- Payments module integration for earn/redeem
- Scheduled **expire** jobs and campaign-driven earn
- Per-service earn percentages
- Public customer wallet / balance APIs
- **Automatic clawback** when a completed booking is reversed or cancelled
- **`reverses_transaction_id`** (or similar) on ledger rows
- Standard HTTP **`Idempotency-Key`** header handling (app uses stored `idempotency_key` column only in C20)
- Admin UI for bonus settings (API may extend settings PATCH later; UI deferred)

---

## 5. Database alignment (no schema change required for C20 doc)

Existing tables **`bonus_transactions`**, **`customers.bonus_balance_cents`**, and **`bookings.price_cents`** support C20. Transaction types **`earn`** and **`adjustment`** are in scope; **`redeem`**, **`expire`**, **`refund`** remain documented for future use but are **not** implemented in C20.

---

## 6. Validation (this documentation task)

- Architecture and database docs updated to reference this contract.
- Booking transition **`confirmed → completed`** documented as allowed (matches [database.md](../database.md) transition diagram).
- No application code, migrations, or tests modified in the formalization slice.
