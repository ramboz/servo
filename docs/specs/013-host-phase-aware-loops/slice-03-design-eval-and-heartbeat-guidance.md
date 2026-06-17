---
status: DEFERRED
dependencies: [013-01, 011-03, 012, adr-0011]
last_verified:
---

## Slice 013-03 - design-eval and heartbeat guidance

**Goal:** Extend servo's design-eval and heartbeat documentation so phase
hints guide expensive or risky work: plan rubrics/candidates first, run only
after the plan is represented in durable artifacts, then evaluate through the
existing oracle/eval ledger.

**Resolution trigger:** Resume when a second design-eval consumer appears, or
when heartbeat dispatch starts using host-native phase guidance for real
scheduled work.

**DoR:**
- [ ] 013-01 DONE.
- [ ] At least one concrete design-eval or heartbeat consumer exists.

**Acceptance Criteria:**

1. **Design-eval flow documented.** Docs distinguish planning the rubric /
   screen set, implementing UI changes, and evaluating the frozen component.
2. **Heartbeat flow documented.** Docs distinguish discovery/triage from
   dispatch, and state that phase hints never override `actionable AND open`,
   oracle preflight, or cost ceilings.
3. **No ledger drift.** Frozen eval ledgers and triage inbox records remain the
   durable evidence; host mode is not recorded as a pass/fail claim.
4. **Surface tests or doc checks pin wording.** Servo's skill-surface tests, or
   equivalent docs checks, cover the no-authority wording.

**DoD:**
- [ ] All ACs pass; full suite or docs checks green.
- [ ] Reviewed by the appropriate jig reviewer workflow.
- [ ] Deviation log produced under this slice heading.
- [ ] `docs/specs/README.md` regenerated.

**Anti-horizontal-phasing check:** After this slice, real design-eval and
heartbeat users have concrete phase guidance at the points where servo can
spend money or dispatch autonomous work.

### Deviation log (after reconciliation)

_Not started; parked until the resolution trigger fires._
