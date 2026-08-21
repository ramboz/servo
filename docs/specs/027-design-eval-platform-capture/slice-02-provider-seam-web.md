---
status: DRAFT
dependencies: [adr-0032]
last_verified:
---

## Slice 027-02 — capture-provider seam + web default

**Goal:** Introduce a `capture.transport` selector (reviving spec 026-02's
designed-but-unbuilt field) and a provider dispatch inside `capture_app`, with
the existing Playwright path refactored into the default **web** provider —
behavior-preserving for every current web project, and recording the chosen
provider in `ledger.jsonl` (unfrozen, per [ADR-0032](../../decisions/adr-0032-design-eval-capture-providers.md) §6 / ADR-0031).

**Scope note:** minimal interface — one provider (web), no non-web target yet.
Absent config → web default, zero change. The seam is the enabling surface the
later provider slices plug into.

**Acceptance Criteria:** _TBD when picked up (READY_FOR_IMPLEMENTATION)._

**DoD:** _Standard slice DoD (see slice template); ACs + tests authored at
pickup._
