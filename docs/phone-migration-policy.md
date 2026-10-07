# Customer phone normalization — migration policy (Kyrgyzstan MVP)

This document defines the **candidate policy** for a future production migration that canonicalizes salon-scoped customer phone values to a single Kyrgyzstan format. It is based on a **completed read-only production phone conflict audit** and must be reviewed by the architect before any implementation, schema change, or data mutation.

**Canonical MVP format:** `+996XXXXXXXXX` — a leading `+996` country code followed by **exactly nine** local Kyrgyz digits (13 characters total including `+`).

**Related:** [architecture.md](architecture.md) (tenancy, customers module), [database.md](database.md) (`customers.phone`), [AGENTS.md](../AGENTS.md) (tenant isolation and migration rules).

---

## Table of contents

1. [Purpose](#1-purpose)
2. [Canonical format](#2-canonical-format)
3. [Existing production findings](#3-existing-production-findings)
4. [Normalization rules](#4-normalization-rules)
5. [Collision policy](#5-collision-policy)
6. [Confirmed SAFE backfill candidates](#6-confirmed-safe-backfill-candidates)
7. [NEEDS MANUAL candidates](#7-needs-manual-candidates)
8. [Unmappable phones](#8-unmappable-phones)
9. [Migration order](#9-migration-order)
10. [Constraints before unique phone constraint](#10-constraints-before-unique-phone-constraint)
11. [Rollback / safety](#11-rollback--safety)
12. [Out of scope](#12-out-of-scope)
13. [Architecture decision status](#13-architecture-decision-status)

---

## 1. Purpose

Liman Salon MVP targets **Kyrgyzstan salons only**. Customer phone numbers are the primary contact key for public resolve, admin records, and future WhatsApp notifications. Today, production stores phones as free-form strings with **no enforced canonical shape** and **no unique constraint** on `(salon_id, phone)`.

This policy exists so that a future migration can:

- Store and compare phones consistently within a salon tenant (`salon_id`).
- Align public booking UX with a fixed Kyrgyz country prefix.
- Avoid silent data loss, mistaken deduplication, or booking/customer_id reassignment.

**MVP scope:** normalization rules and UX assumptions apply to **Kyrgyzstan (`+996`) numbers only**. Supporting Kazakhstan, Uzbekistan, or generic international formats is explicitly **future work**, not part of this policy’s MVP execution.

---

## 2. Canonical format

### Stored representation

- **Database and API persistence (target):** E.164-style string `+996` + **9** local digits, e.g. `+996555123456`.
- **Length:** 13 characters (`+` plus 12 digits).
- **No** spaces, hyphens, parentheses, or national trunk `0` in stored values after migration.

### Public UX (future frontend / forms)

- Display a **fixed `+996` prefix**; the user enters **only the 9 local digits**.
- **No country selector** in MVP.
- Validation rejects incomplete or over-long local input before submit.

### Future scope (not MVP)

- Kazakhstan (`+7`), Uzbekistan (`+998`), and other international numbering plans.
- Country selector and multi-country validation libraries.
- Any automatic inference of country from ambiguous bare digit strings.

---

## 3. Existing production findings

The following facts come **only** from the completed read-only production phone conflict audit. No additional production counts or row identities are asserted here.

| Metric | Audit result |
|--------|----------------|
| Customer rows audited | **30** |
| Non-empty `phone` | **30 / 30** |
| Already match `+996` + 9 digits | **4** |
| Local `0` + 9 digits (`0XXXXXXXXX`) | **4** |
| Values with `+7` prefix | **0** |
| Values with `+998` prefix | **0** |
| Values like `996…` **without** leading `+` | **0** |
| Values containing spaces, hyphens, or parentheses | **0** |
| Values containing **letters** | **16** |
| Other malformed (approx.) | **~6** |
| Conservatively **unmappable** | **22** |
| Exact duplicate `(salon_id, phone)` pairs | **0** |
| Conservative canonicalization: collision groups | **2 groups / 4 rows** |

### `0XXXXXXXXX` rows by audit classification

| Audit class | Customer id (prefix) | Stored phone |
|-------------|----------------------|--------------|
| **SAFE** (no canonical collision in audit) | `b1b1c400…` | `0551515445` |
| **SAFE** | `9ce60384…` | `0555388988` |
| **NEEDS MANUAL** (canonical target occupied) | `67146dea…` | `0550530999` |
| **NEEDS MANUAL** | `d0ad942e…` | `0555123456` |

> **Note:** Full UUIDs were not present in repository audit artifacts; only the prefixes above were recorded in the audit handoff. Future implementation must re-resolve full `customer_id` values from a fresh read-only query before any mutation.

---

## 4. Normalization rules

Future application and migration logic **must** follow these rules. Values outside the rules remain unchanged until explicit manual handling.

| Input pattern | Policy |
|---------------|--------|
| `0` + exactly 9 digits | Convert to `+996` + same 9 digits (drop leading `0`). |
| Already `+996` + exactly 9 digits | **Unchanged** (already canonical). |
| Exactly 9 digits **without** `0` or `+996` | **Do not** bulk-convert automatically; requires a **manual decision** per row or an separately approved rule. |
| Contains letters, or otherwise malformed | **Unmappable** until manually corrected; **never guess**. |
| Ambiguous or invalid | **Never guess**; leave as-is or set to NULL only under an approved manual/collision workflow. |

**Principles:**

- Deterministic transforms only for the approved `0XXXXXXXXX` → `+996XXXXXXXXX` pattern (and identity for already-canonical values).
- No fuzzy matching, no stripping of arbitrary punctuation beyond what a future spec explicitly defines (audit found **no** space/hyphen/parenthesis cases).
- Tenant isolation unchanged: all lookups and uniqueness considerations remain scoped by **`salon_id`**.

---

## 5. Collision policy

Conservative canonicalization of audit data produced **2 collision groups involving 4 rows**. Collisions are **blocking** for automatic updates.

**Mandatory rules:**

1. **Never assume** two `Customer` rows represent the same human merely because normalized phone values would collide.
2. **Never automatically merge** `customer_id` values.
3. **Never delete** a `Customer` row as part of phone normalization.
4. **Existing bookings** must remain attached to their **existing** `customer_id`; normalization must not reassign booking ownership.
5. Before changing **either** phone value in a collision group, the collision must be **resolved manually**.
6. **Do not** automatically select one resolution path.

**Permitted future resolution options** (human or separately approved process only):

- **a)** Manual correction of one or both stored phones to distinct, valid canonical values (or intentional NULL where allowed).
- **b)** Setting one phone to **NULL** when business policy allows missing phone on a duplicate-looking row.
- **c)** Controlled deduplication **only** under a **separately approved** customer-merge policy (not defined here).

Until resolution is recorded, automatic backfill for colliding rows is **prohibited**.

---

## 6. Confirmed SAFE backfill candidates

The audit identified **two** `0XXXXXXXXX` rows that are **SAFE** in the **narrow** sense: applying `0` + 9 → `+996` + 9 would **not** create a canonical phone already held by another customer in the same salon according to the audit.

| Customer id (prefix) | Current phone | Expected canonical |
|----------------------|---------------|--------------------|
| `b1b1c400…` | `0551515445` | `+996551515445` |
| `9ce60384…` | `0555388988` | `+996555388988` |

**Important:**

- “SAFE” does **not** mean “same person” or “merge candidates.”
- **This documentation task does not backfill** these or any other rows.
- A future approved migration must re-verify collisions immediately before UPDATE.

---

## 7. NEEDS MANUAL candidates

These `0XXXXXXXXX` rows **cannot** be automatically converted because the audit found the **canonical target already occupied** by another customer in the same salon.

| Customer id (prefix) | Current phone | Blocked canonical target |
|----------------------|---------------|---------------------------|
| `67146dea…` | `0550530999` | `+996550530999` (occupied) |
| `d0ad942e…` | `0555123456` | `+996555123456` (occupied) |

Automatic backfill is **prohibited** until manual collision resolution (see [§5 Collision policy](#5-collision-policy)) determines distinct correct values or NULL handling per row.

---

## 8. Unmappable phones

- **22** production phone values are conservatively classified as **unmappable** under automated rules (includes letter-containing and other malformed cases identified in the audit).
- **Do not** attempt fuzzy matching, partial digit recovery, or heuristic “fixups.”
- **Existing bookings** tied to those customers remain **untouched**; normalization must not move or rewrite booking links.
- Future correction should occur through an **explicit customer/admin workflow** or a **separately approved** cleanup process with audit trail—not silent bulk SQL.

---

## 9. Migration order

Future work must follow this **MVP sequence**. Do not skip steps. **Manual collision resolution** (see [§5 Collision policy](#5-collision-policy)) is **mandatory before** any **SAFE backfill** (see [§6](#6-confirmed-safe-backfill-candidates) and [§7](#7-needs-manual-candidates)); automated backfill for NEEDS MANUAL or unresolved collision groups remains **prohibited** per §5.

### Prohibited mixed legacy/canonical production state

Production must **not** rely on **strict canonical write, resolve, and validation** as the **sole** phone lookup representation while **legacy-equivalent** values still exist in stored customer data (for example, `0XXXXXXXXX` alongside another row’s `+996XXXXXXXXX` for the same intended number, or unmigrated `0…` rows that strict resolve would not match). Deploying application behavior that **only** reads or matches canonical `+996` + 9 digits **before** stored data is canonicalized (or explicitly NULL) under the steps below would strand customers and break public resolve/booking lookup for legacy strings. **Strict canonical write/resolve/validation** (step 8) applies **only after** collision resolution, SAFE backfill, and unmappable handling have brought existing rows to canonical or approved NULL—not before.

### MVP sequence

1. **Production audit** — read-only, repeatable baseline (see [§3](#3-existing-production-findings)).
2. **Policy approval** — this document; architect sign-off.
3. **Implementation, automated tests, and staging migration rehearsal** — normalization/migration tooling, tests (create, update, public resolve, lookup; tenant isolation), staging dry-run counts and collision reports (separate approved tasks; no production mutation).
4. **Production re-verification** — read-only re-audit or equivalent immediately before any production UPDATE; conservative canonicalization and collision report on **current** production data.
5. **Manual collision resolution** — NEEDS MANUAL and any newly discovered groups; per [§5](#5-collision-policy); no automatic merges or booking reassignment.
6. **SAFE backfill** — only rows re-verified as SAFE immediately before UPDATE; never NEEDS MANUAL or unresolved collision rows.
7. **Unmappable cleanup / re-entry** — manual or approved workflow for unmappable values ([§8](#8-unmappable-phones)); no guessing or silent bulk fixups.
8. **Strict canonical write, resolve, and validation** — reject non-canonical persistence on write; read/resolve paths may treat canonical form as the **sole** matching representation **only after** steps 1–7 have canonicalized or NULL’d existing stored phones (dependency: data canonicalization **before** strict canonical-only lookup, not the reverse).
9. **Only then** consider a **unique normalized-phone constraint** per salon ([§10](#10-constraints-before-unique-phone-constraint)).

---

## 10. Constraints before unique phone constraint

A database **unique constraint** on canonical phone (e.g. partial unique on `(salon_id, phone) WHERE phone IS NOT NULL`, as suggested in [database.md](database.md)) must **not** be introduced until **all** of the following are true:

- All existing stored values are **canonical** (`+996` + 9 digits) or **NULL**.
- **All collisions** are resolved (no two distinct customers share the same intended canonical phone within a salon unless explicitly allowed by a future policy—which MVP does not define).
- **All unmappable** values are resolved or explicitly allowed to remain **NULL** with business approval.
- **Application writes** persist canonical values on create/update/resolve (no new non-canonical inserts).
- **Tests** cover create, update, public resolve, and phone lookup paths under `salon_id` scoping.
- **Staging migration** has succeeded end-to-end with metrics matching the production plan.
- **Production migration plan** documents explicit **rollback / recovery** considerations (see [§11](#11-rollback--safety)).

---

## 11. Rollback / safety

- **No destructive migration** (no mass DELETE of customers or bookings as a normalization shortcut).
- **No automatic customer merge.**
- **No booking reassignment** to different `customer_id` values as part of phone cleanup.
- **No production UPDATE or DELETE** without an explicit, architect-approved migration script and runbook.
- Every future migration step must be **reversible** or have a **documented recovery strategy** (backup, forward-only compensating script, or accepted rollback window).

Read-only audits and this policy document do **not** mutate production.

---

## 12. Out of scope

The following are explicitly **excluded** from this policy document and from the documentation-only task that produced it:

- International phone support (non-`+996`).
- Country selector UI or multi-country validation.
- Automatic fuzzy customer matching.
- Automatic customer merging or `customer_id` consolidation.
- Booking reassignment between customers.
- Deletion of test customers in production.
- Production cleanup or data mutation in the task that authored this policy.
- **Unique constraint** implementation (Alembic revision).
- **Strict validation** implementation in application code.

---

## 13. Architecture decision status

**PROPOSED — ARCHITECT REVIEW REQUIRED**

This policy is **not approved** for implementation. No code, schema migration, or production data change should proceed until the architect accepts or revises this document.
