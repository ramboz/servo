---
status: DEFERRED
kind: feature
dependencies: [033-01, adr-0039]
last_verified:
arch_review: true
frame_review: true
---

## Slice 033-07 - native-stop-continuation

**Goal:** An explicitly installed native meta-judge gates per-turn continuation
with effective decisions and a bounded retry guard.

**DoR:**
- Positive live per-turn dispatch/continuation contract, not just registration.

**Acceptance Criteria:**

1. Verify per-turn continuation plus bounded retry guard; agentStop end-of-run
   notification and preToolUse denial do not count.
2. Explicit consent, ownership-safe install/uninstall, fail-open environmental
   errors and project oracle authority remain unchanged.
3. Unsupported enforcing installation refuses explicitly and does not mutate.
   Existing advisory adapter is labelled advisory, not an enforcing gate.

**DoD:**
- [ ] Native live continuation and install/uninstall regression evidence pass.
- [ ] All required reviews and reconciliation pass.

## Assumptions

Native stop decisions may support continuation; that is not established by the
September static adapter or current package install.

**Resolution trigger:** Live CLI evidence proves per-turn continuation decisions
and a bounded retry guard; then re-open via DRAFT and normal readiness review.

**Anti-horizontal-phasing check:** The user's real turn is gated, not merely logged.

### Deviation log (after reconciliation)

Not implemented; existing agentStop adapter remains advisory.

### Reconciliation sweep

Deferred: enforcing continuation awaits positive runtime evidence.
