---
status: DRAFT
dependencies: [adr-0029]
last_verified: 2026-08-04
---

## Slice 023-01 — readiness verdict, artifact, and human approval

**Goal:** A `autonomy-readiness` skill reviews a goal's scope + initial prompt and
emits a human-owned three-state verdict that gates whether an unattended loop may
start — refusing bad premises and identity-collapsed setups before any budget is
burned. Implements [ADR-0029](../../decisions/adr-0029-autonomy-readiness-gate.md).

**DoR:**
- ✅ [ADR-0029](../../decisions/adr-0029-autonomy-readiness-gate.md) is the governing record.
- ⬜ Confirm the `edd-suitability` artifact/verdict shape and the `eval-authoring`
  proposed→approved + `criteria-check` mechanics to mirror them.
- ⬜ Confirm `loop.py` / `heartbeat.py` preflight seams (where refuse-without-oracle
  lives) and the dirty-tree preflight to reuse.
- ⬜ Pin the host signal used to compare run-identity vs merge-identity (shared with
  jig spec 106); ground it by probe, not assumption.

**Acceptance Criteria:**

1. **Three-state verdict + atomic artifact.** The skill emits
   `ready | needs_tightening | unsafe_for_autonomy`, exit `{0,2}` (fail-closed),
   writing `<target>/.servo/readiness/<goal-id>.json` atomically. Observable: each
   verdict is reachable from a corresponding fixture brief.
2. **Deterministic tier.** Missing/unexecutable oracle, no approved component,
   infinite (unset) budget/iteration/`max-candidates` cap, dirty tree/no isolation,
   or absent mutation perimeter each downgrade the verdict. Observable: toggling
   each precondition changes the verdict deterministically.
3. **Identity-collapse check.** When the principal that would run the loop is also
   able to merge to the base branch, the verdict is `unsafe_for_autonomy` with a
   message naming identity collapse. Observable: a two-identity fixture is not
   flagged; a single-identity fixture is.
4. **Model-judged tier scores the prompt.** Precision, Scope-boundedness,
   Stop/escalation, Safety surface, and Internal-contradiction are scored via the
   expand-then-independent-review two-call pattern. Observable: an open-ended brief
   → `needs_tightening`; a secrets/deploy-touching brief → at least
   `needs_tightening` with the safety surface named.
5. **Human-owned approval.** The artifact starts `approval_status: proposed`; it is
   never auto-approved; a human flip to `approved` is required before the
   refuse-without-readiness preflight passes. Observable: dispatch is refused while
   `proposed`; permitted after `approved`.
6. **Boundary integrity.** When jig is co-installed, `clarify` / `frame_review` are
   reached by subprocess + filesystem only (no servo→jig import); absent jig, a
   built-in rubric is used. Observable: the co-installed path spawns a subprocess;
   the standalone path does not error.

**DoD:**
- [ ] All ACs pass; test suite green (no regressions).
- [ ] Each AC covered by ≥1 fixture; each new test shown capable of failing.
- [ ] Reviewed (compliance + craft; +arch — this slice adds a Compile-phase gate
      and a preflight contract).
- [ ] Deviation log + reconciliation sweep recorded under this slice.

### Close-out (post-DONE)
- [ ] `docs/specs/README.md` regenerated (status-board).
- [ ] Skill surface documented; README/product-vision Compile-phase order updated
      to place readiness upstream of `edd-suitability`.

**Anti-horizontal-phasing check:** After this slice lands, a user can run
`autonomy-readiness` on a real goal and get an actionable, human-approvable
verdict that blocks an unattended start on a bad premise — end-to-end value even
before the loop is wired.

### Deviation log (after reconciliation)

_TBD — not yet implemented (recorded, not built)._

### Reconciliation sweep

| Artifact | Disposition | Rationale |
|----------|-------------|-----------|
| `docs/specs/README.md` | `updated` | _TBD — regenerate at close._ |
| `README.md` / `docs/product-vision.md` | `no-op` | _TBD — Compile-phase ordering note at close._ |
| `docs/decisions/README.md` | `no-op` | _ADR-0029 already indexed._ |
