---
status: DEFERRED
kind: feature
dependencies: [034-02, adr-0043]
last_verified:
arch_review: true
frame_review: true
---

## Slice 034-03 - native-loop-and-consumers

**Goal:** Native loop, checkpoint resume and planned/heartbeat dispatch preserve
hard requested budgets, oracle authority and independent read-only judges.

**DoR:**
- Executed host evidence proves a requested enforceable budget contract.
- Any different credit/overrun policy has a separate explicit owner decision.

**Acceptance Criteria:**

1. Explicit native selection propagates through loop, plan and heartbeat without
   changing existing backend defaults, driver meanings or budget clamps.
2. Native state/output use version 2 and backend/version identity; old Claude
   version-1 state remains compatible. Cross-backend resume cannot be overridden.
3. Reliable actual spend/context feeds all enabled brakes; absent telemetry is
   unavailable, not zero. Hard in-flight bounds and whole-pass accounting hold.
4. Runner/judge permissions are effective and independently proved. Preserve
   readiness/suitability, cancellation, dirty-tree, plateau and permission-wall
   controls, project-owned oracle and final authoritative 0/1/2 gate.
5. Live safe-edit and read-only-judge proofs plus positive/negative consumer tests
   demonstrate the native behavior, not just a refusal or simulated envelope.

**DoD:**
- [ ] Live enforceable control evidence and all required reviews pass.
- [ ] Each consumer's regression fixtures and reconciliation are complete.

## Assumptions

Future Copilot can provide an enforceable contract; current 1.0.96-2 soft credits
do not prove it. No owner-authorized relaxation exists as of 2026-10-12.

**Resolution trigger:** An executed native hard-budget contract, or an explicit
owner-approved replacement monetary/credit policy recorded in a new ADR, followed
by positive native invocation/tool/context/resume evidence and normal readiness
review. A CLI limit flag alone does not reactivate this slice.

**Anti-horizontal-phasing check:** A consumer can execute safely end to end.

### Deviation log (after reconciliation)

Not implemented; 034-02 is only the capability refusal.

### Reconciliation sweep

Deferred: native state version, runtime propagation and whole-pass accounting
await the resolution trigger.
