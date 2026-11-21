---
status: DRAFT
dependencies: [adr-0052, 047-01]
last_verified: 2026-11-21
arch_review: true
---

<!-- jig self-defining vocabulary (soft, forward-only): expand each acronym on
     first use and link the term to docs/memory/glossary.md (or jig's lexicon).
     See docs/workflow.md "Self-defining vocabulary". -->

<!-- jig grounding (spec 064-02 / ADR-0020): ground factual claims about
     runnable surfaces by probe first (run it / read source) or a citation,
     else mark them as assumptions in the spec's `## Assumptions` section —
     never assert an unverified claim as fact. -->

## Slice 047-02 — required-runtime-skip

**Goal:** Required-policy targets get the same deterministic-first behaviour:
`required_runtime.oracle()` scores deterministic components (every required
component among them) first and skips judged components when the exit code is
already decided — now including a failed required constraint — and the gate's
independent re-derivation accepts a skip only when it was decided.

**DoR:**
- ✅ [ADR-0052](../../decisions/adr-0052-deterministic-components-gate-judges.md)
  Accepted; 047-01 DONE (the kind declaration and the decided-outcome rule this
  slice mirrors in Python).
- ✅ Re-probed at implementation time: the scoring loop
  (`required_runtime.py:762-823`), `outcome()` (`:704-722`), and the gate-side
  re-derivation in `run_gate` (`:877-918`), which compares components in
  `COMPONENTS` order and requires every component to carry a score.
- ✅ Upgrade note agreed with the owner: the approved required binding pins the
  required runtime's bytes (`required_runtime.py:450-451`), so this slice costs
  every required-policy target one re-approval and reinstall (ADR-0052
  Consequences). Batch with other required-runtime changes if any are queued.

**Acceptance Criteria:**

1. **Order and kind.** `oracle()` reads each component's kind from the oracle
   prefix (the 047-01 declaration) and scores deterministic components first.
   Every component bound in `.servo/required-policy.json` is deterministic
   whatever it declares, and is never skipped. Observable: a trace fixture.
2. **A failed required constraint decides the run.** With a required item at
   `fail` after the deterministic pass, no judged component is called; the
   payload has `exit_code: 1` and `required.status: fail`. The reason is
   `required_and_quality_failed` only when the quality ceiling is also below the
   threshold (quality failure is then certain); otherwise it is
   `required_constraints_failed`, because quality was not evaluated and must not
   be reported as failed (ADR-0044's side-by-side honesty).
3. **Unavailable evidence decides the run.** A deterministic component with
   rc ≠ 0, or a required item at `unknown`: no judged component is called; the
   payload has `exit_code: 2` and `reason: required_evidence_unavailable`, as
   today's `outcome()` would give.
4. **A quality ceiling below threshold decides the run.** All required items
   pass and the quality ceiling (judged components at 1.0) is below the
   threshold: no judged component is called; `exit_code: 1`,
   `reason: quality_below_threshold`; `composite` is the lower bound and is
   numeric (a `None` composite would read as exit 2, `required_runtime.py:706-708`).
5. **Payload shape.** `components` stays in `COMPONENTS` order. A skipped
   component appears with `score: null`, `exit_code: null` and
   `skipped: {"reason": <reason>}`, and the payload carries a top-level
   `skipped` list of names. A run that skips nothing publishes a payload
   byte-identical to today's.
6. **The gate verifies every skip.** `run_gate` recomputes the decided condition
   from the components that ran. It refuses (env error,
   `invalid oracle aggregate/decision`) a payload that skips when the outcome was
   not decided, skips a required component, or reports exit 0 alongside any
   skip. The oracle can add refusal causes but cannot use a skip to change a
   verdict.
7. **Exit-code equivalence (property test).** The 047-01 AC5 matrix plus
   required pass / fail / unknown injections: the gate's exit code equals
   today's on the same inputs, with the same single named difference as 047-01
   AC5 (a judged component that would have been unavailable on a decided run),
   pinned by its own test.
8. **Upgrade behaviour is loud, never silent.** A target approved against the
   pre-047 runtime either keeps today's behaviour (vendored runtime pin) or
   refuses with an env error naming the modified runtime artifact (shared
   runtime pin) until re-approved and reinstalled. After re-approval it gets the
   new behaviour; the required checks' `config_hash`, fragment and source
   bindings are unchanged. Observable: fixtures for both pin shapes.

**DoD:**
- [ ] All ACs pass; full test suite green (no regressions), including
      `skills/spec-oracle/test_required_gate.py`.
- [ ] Implementer test coverage exercises each AC with at least one
      fixture. Edge cases listed in the slice are covered explicitly.
- [ ] Each new test has been shown to fail when its feature is removed —
      the test is capable of failing, not vacuously green (mutate the
      feature, watch the test go red, restore). In particular, removing the
      gate-side skip check reds AC6.
- [ ] Host packages rebuilt and drift-clean
      (`scripts/build_host_packages.py --check`); Python 3.9 floor respected.
- [ ] Reviewed by `reviewer` subagent. Reviewer prompt built by
      `review.py`.
- [ ] Implementation review passed (compliance + craft + arch).
- [ ] Deviation log produced under this slice heading.
- [ ] Reconciliation sweep produced under this slice heading.
- [ ] Reconciliation review passed.
- [ ] `docs/refinement-todo.md` updated if any decisions were
      deferred during implementation.

### Close-out (post-DONE)

These items can only be ticked AFTER the final `RECONCILED → DONE`
transition. Slice-land's `check_dod` (slice 009-01) excludes them
from the count.

- [ ] `docs/specs/README.md` regenerated by `workflow.py status-board`.
      Notes column receives any load-bearing per-slice invariant
      (it's preserved across regen).
- [ ] Primer hygiene per spec 025-01 rule: **if this slice closes the
      spec** (all non-deferred slices DONE), check `CLAUDE.md`,
      `AGENTS.md`, and scaffold templates when present, then **compress**
      the spec's Active-specs entry — drop facts derivable from the
      spec dir + status board, migrate load-bearing per-slice
      invariants to the status board Notes column, keep at most a
      one-liner only for cross-cutting facts. If the spec is still
      in flight (other slices DRAFT / READY / IN_PROGRESS), leave
      the entry. If this slice introduces a new skill, add or
      update its row in the Skills table.

**Anti-horizontal-phasing check:** After this slice, a required-policy target
whose required check fails gets the same `required_constraints_failed` verdict
it gets today without paying for its judged components, and the gate refuses
any oracle result that uses a skip to dodge a judged score.

### Deviation log (after reconciliation)

The original spec is preserved above. Implementation notes:

_TODO: numbered sections covering deviations from the planned shape,
reviewer findings folded back in, doc updates, plan adherence._

### Reconciliation sweep

Record the drift-prone surfaces checked during reconciliation. The transition
gate only requires this subsection to exist; the reconciliation reviewer judges
whether coverage and rationales are honest.

| Artifact | Disposition | Rationale |
|----------|-------------|-----------|
| `README.md` | `no-op` | _TODO: why this slice did not affect the project front door, or summarize the update._ |
| `docs/specs/README.md` | `updated` | _TODO: regenerated by `workflow.py status-board`, or explain why deferred._ |
| `docs/product-vision.md` | `no-op` | _TODO: checked for behavior / scope drift._ |
| `docs/architecture.md` | `no-op` | _TODO: checked for module-boundary / public-contract drift._ |
| Primer surfaces: `CLAUDE.md` / `AGENTS.md` / scaffold templates | `no-op` | _TODO: primer hygiene checked; note compression or template updates if any._ |
| `docs/inbox.md` | `no-op` | _TODO: checked for items resolved by this slice._ |
| `docs/refinement-todo.md` | `no-op` | _TODO: checked for resolved items or new deferred decisions._ |
| `docs/memory/**` | `no-op` | _TODO: note memory-sync result or why nothing was worth capturing._ |
| `docs/decisions/README.md` / ADR index | `no-op` | _TODO: use `updated` when the slice touched ADRs; otherwise mark checked._ |
| Additional live prose / generated templates touched by this slice | `deferred` | _TODO: name owner or trigger when real cleanup remains; otherwise replace with `no-op`._ |
