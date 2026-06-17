---
status: DEFERRED
dependencies: [adr-0011]
last_verified:
---

## Slice 013-01 - phase-hint contract

**Goal:** Define servo's host-neutral phase-hint contract (`plan`, `run`,
`evaluate`, `triage`) and document how it composes with `gate.py`,
`oracle.sh`, run state, and triage state.

**Resolution trigger:** Resume when jig lands an accepted host-mode adapter
decision/spec, or when a servo consumer needs phase hints before running an
autonomous loop.

**DoR:**
- [ ] ADR-0011 Accepted.
- [ ] Current Codex and Claude phase-mode behavior re-verified.

**Acceptance Criteria:**

1. **Small vocabulary.** Docs define `plan`, `run`, `evaluate`, and `triage`
   as advisory phase intent, not a new lifecycle.
2. **Authority preserved.** Docs state that `gate.py`, `oracle.sh`, run state,
   triage state, and frozen eval ledgers remain canonical.
3. **Graceful degradation.** The contract states that missing host-mode
   support falls back to plain prompts and existing loop behavior, never
   `env_error`.
4. **References updated.** `docs/architecture.md` or equivalent loop docs link
   the contract from the agent-loop, heartbeat, and design-eval sections.

**DoD:**
- [ ] All ACs pass; docs/surface checks green where applicable.
- [ ] Reviewed by the appropriate jig reviewer workflow.
- [ ] Deviation log produced under this slice heading.
- [ ] `docs/specs/README.md` regenerated.

**Anti-horizontal-phasing check:** After this slice, a user can understand how
servo will interpret host planning / implementation hints before any runtime
code exists.

### Deviation log (after reconciliation)

_Not started; parked until the resolution trigger fires._
