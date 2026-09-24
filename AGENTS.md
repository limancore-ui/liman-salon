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

## Mandatory Completion Report

Every **AI coding agent**, after finishing **any** task, must automatically provide a full plain-text final report **directly in the Agent chat**.

- The agent must **NOT** wait for the architect to ask for the report.
- The report must **NOT** require screenshots.
- The report must be readable and copy-pasteable as plain text/Markdown.

### Required report structure (every task)

```markdown
# LIMAN SALON REVIEW REPORT

## 1. Task
- What was implemented.
- Exact scope.
- Explicitly state what was NOT implemented when relevant.

## 2. Files Changed
- Every modified file.
- Every new file.
- Every deleted file.
- Clear distinction between modified/new/deleted.

## 3. Implementation Summary
- Main models/code/components changed.
- Important fields, types, defaults, logic, or relationships.
- Mention tenant-isolation implications where relevant.

## 4. Database / Architecture Details
When applicable:
- Foreign keys and ON DELETE behavior.
- Composite foreign keys.
- Unique constraints.
- Indexes / partial indexes.
- CHECK constraints.
- Relationships / back_populates.
- Any architecture-boundary changes.

## 5. Migration
When applicable:
- Migration filename.
- revision.
- down_revision.
- What the migration creates/changes.
- Confirm whether previous committed migrations were modified.

## 6. Validation
Report every check that was actually run, with PASS / FAIL / BLOCKED:
- compile/import checks
- tests
- metadata checks
- Alembic checks
- offline SQL/DDL checks
- formatter/static checks
- any other relevant validation

Never claim a validation passed unless it was actually run.

## 7. Scope Verification
Explicitly confirm:
- requested scope completed
- unrelated work not performed
- later models/features not implemented
- architecture/docs changed or not changed

## 8. Git Status
Show the exact current git status:
- branch
- ahead/behind state when available
- modified files
- untracked files
- staged files
- whether commit was made
- whether push was made

## 9. Issues / Limitations
- Any blockers.
- Any environment limitations.
- Any warnings.
- Clearly distinguish blockers from optional follow-up items.

## 10. Final Status
Use exactly one:
- READY FOR ARCHITECT REVIEW
- BLOCKED
- NEEDS FOLLOW-UP
```

### Rules

- Always produce the report at the end of the task.
- Always produce it automatically; never wait for a second request.
- Do not replace the full report with a short summary.
- Do not hide validation failures or environment limitations.
- Do not invent test results.
- Do not commit or push unless the task explicitly authorizes it.
- STOP after the report unless the task explicitly asks for another action.

## Reference

- Architecture: [docs/architecture.md](docs/architecture.md)
- Product overview: [README.md](README.md)
