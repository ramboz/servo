---
status: DRAFT
dependencies: [adr-0032, 027-02]
last_verified:
---

## Slice 027-03 — custom-command provider (escape hatch)

**Goal:** Let a project declare an arbitrary capture command (invoked per screen
with the screen id + output path, responsible for driving to state, screenshot,
and returning a frame-normalized PNG), so **any** non-web stack can be scored via
a project-supplied script — the shortest path to cross-stack value and the first
real exercise of the seam on a non-web target. Failure fails closed to
`env_error`; the command identity is recorded in the ledger, unfrozen.

**Scope note:** the generic escape hatch, before the blessed Android/iOS
built-ins. Per-platform state seeding is provider-owned (ADR-0032 §4); only
references/rubric/judge are shared.

**Acceptance Criteria:** _TBD when picked up (READY_FOR_IMPLEMENTATION)._

**DoD:** _Standard slice DoD; ACs + tests authored at pickup._
