# Agent and developer rules — Liman Salon MVP v0.1

This document applies to **human developers** and **AI coding agents** working in this repository.

## Roles

| Role | Responsibility |
|------|----------------|
| **ChatGPT** | Architect / technical lead — scope, architecture, and approval of structural changes |
| **Human owner** | Product owner — priorities, acceptance, and final decisions |
| **Agents / implementers** | Execute approved, incremental work in this repo only |

## Working in this repository

- Work **only** in `liman-salon` (this GitHub project). Do not modify sibling or external copies of the project unless explicitly directed by the owner.
- Make **small, incremental changes** with clear intent and minimal blast radius.
- **Do not modify unrelated files** — stay within the task scope; avoid drive-by refactors or formatting sweeps.
- **No unnecessary dependencies** — add libraries only when required and approved for the task.

## Architecture and approval

- **Architecture approval is required** before:
  - New modules or major module boundary changes
  - Cross-cutting patterns (auth, tenancy, events, shared kernels)
  - Database schema strategy changes beyond agreed migrations
  - New external integrations (payments, notifications, AI providers)
- When in doubt, stop and confirm with the architect/lead before implementing.

## Security

- Follow **security best practices**: least privilege, no secrets in git, validate all inputs, secure defaults for auth and session handling (when implemented).
- Enforce **tenant isolation**: tenant-owned data must be scoped by **`salon_id`** (see [docs/architecture.md](docs/architecture.md)). Never expose or mutate another salon’s data.
- Agents must **not directly access the database** (no ad-hoc SQL, no ORM sessions outside approved application services). All data access goes through the application layer as it is built.

## Testing

- Add or update tests when behavior changes; prefer tests that prove **tenant isolation**, **booking/availability rules**, and **critical paths**.
- Do not merge behavior changes that break existing tests without explicit owner approval.

## AI-specific constraints

- AI implementers act as **implementers**, not architects — follow approved designs and AGENTS.md.
- Use **controlled application services** only; never bypass tenancy or call the database directly.
- Do not commit, push, or change deployment configuration unless the human owner explicitly requests it for that task.

## Reference

- Architecture: [docs/architecture.md](docs/architecture.md)
- Product overview: [README.md](README.md)
