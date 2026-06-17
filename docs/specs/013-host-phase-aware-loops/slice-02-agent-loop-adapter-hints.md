---
status: DEFERRED
dependencies: [013-01, 003, adr-0011]
last_verified:
---

## Slice 013-02 - agent-loop adapter hints

**Goal:** Add an advisory phase-hint surface to servo's agent loop so callers
can ask for a plan/run/evaluate rhythm without changing `gate.py` authority or
the existing loop state contract.

**Resolution trigger:** Resume after 013-01 lands and a real caller needs
loop-level phase hints, such as a Codex adapter, a Claude Routine, or a jig
generated workflow prompt.

**DoR:**
- [ ] 013-01 DONE.
- [ ] The current loop drivers and host surfaces have been re-verified.

**Acceptance Criteria:**

1. **Hint-only implementation.** Any CLI flag, prompt field, or adapter hook
   introduced by this slice affects instructions/dispatch only; oracle scoring
   and `state.json` pass/fail semantics are unchanged.
2. **Missing support degrades.** If the active host cannot select a native
   phase mode, the loop still runs with existing behavior and a clear
   diagnostic when requested.
3. **No budget bypass.** Cost ceilings, max turns, plateau handling, and
   oracle preflight remain enforced exactly as before.
4. **Tests cover invariants.** Regression tests prove phase hints do not alter
   `gate.py` result interpretation or state schema.

**DoD:**
- [ ] All ACs pass; full suite green.
- [ ] Reviewed by the appropriate jig reviewer workflow.
- [ ] Deviation log produced under this slice heading.
- [ ] `docs/specs/README.md` regenerated.

**Anti-horizontal-phasing check:** After this slice, an actual `loop.py` caller
can request phase-aware behavior and still receive the same oracle-authoritative
result contract.

### Deviation log (after reconciliation)

_Not started; parked until the resolution trigger fires._
