---
status: DRAFT
kind: feature
dependencies: [038-01, 034-03]
last_verified:
---

## Slice 041-01 — budget unit

**Goal:** A Copilot-hosted run can be capped in premium requests, with brakes
that compare like units, without servo inventing a USD conversion.

**DoR:**
- Spec 041 activation trigger met (034-03 un-deferred under a revised ADR-0043).
- Copilot's per-invocation usage report is verified to carry premium-request
  cost per model (re-probe at activation).

**Acceptance Criteria (sketch):**

1. A plan/CLI budget may declare `budget_unit: usd|premium_requests`. The
   default is the host's native unit, and `usd` on Claude is unchanged.
2. The cumulative brake sums the host-reported cost in the declared unit. A
   unit mismatch between the declared budget and the reported spend refuses
   rc=2 rather than braking on 0.
3. Spec 038 accounting records the native unit next to `cost_usd`, as
   `cost_native: {unit, value}`.
4. The heartbeat whole-pass ceiling refuses to mix units within one inbox.

**DoD:** ACs pass; ADR (amending ADR-0012/ADR-0038 residual) accepted; reviews.

**Anti-horizontal-phasing check:** a Copilot-hosted servo run stops on a
premium-request budget the user actually set.
