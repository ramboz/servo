---
status: DRAFT
dependencies: [003, adr-0003]
last_verified: 2026-07-11
---

## Slice 021-01 - diff-anchored, narrow-first investigation

**Goal:** Give `agents/runner.md` and `agents/judge.md` diff-anchored,
narrow-first investigation guidance — anchor reads to the changed / oracle-
pointed files, use Glob/Grep to locate before reading, batch discovery before
reads, read focused ranges rather than whole files, and retry a failed search
with a simpler query instead of guessing paths. Refines the existing narrow-read
prose ("Read 1-3 relevant files to understand the failure shape" in runner.md;
"Use files_changed from the runner's verdict to focus your read" in judge.md)
into an explicit discipline. Advisory only — no oracle/gate change.

**DoR:**
- [ ] ADR-0003 remains the governing roster/verdict contract; this slice makes
      no schema change.
- [ ] The agent-prompt surface tests are identified (the tests that assert
      `runner.md`/`judge.md` content — same suite that guards the 003-05 prompts).

**Acceptance Criteria:**

1. **Runner guidance.** `agents/runner.md` instructs the runner to anchor reads
   to the changed / oracle-pointed files, locate-before-read with Glob/Grep,
   batch discovery before reads, read focused ranges, and retry a failed search
   with a simpler query — presented as a coherent block, not scattered asides.
2. **Judge guidance.** `agents/judge.md` gives the parallel guidance, extending
   its existing "focus your read on files_changed / oracle-pointed files" so the
   judge narrows the same way rather than re-reading the tree.
3. **Boundary preserved.** No change to `oracle.sh`, `gate.py`, `loop.py`, or the
   verdict-block schema; the guidance is advisory (ADR-0021 / ADR-0011 / ADR-0005).
4. **Surface tests.** The agent-prompt surface tests assert the new guidance is
   present in both files (a distinctive marker per file).

**DoD:**
- [ ] All ACs met; full suite green.
- [ ] Surface tests cover the runner and judge guidance.
- [ ] Reviewed (compliance + craft); evidence recorded.
- [ ] Deviation log + reconciliation sweep under this slice.
- [ ] Host packages / vendored copies regenerated if servo ships them.

**Anti-horizontal-phasing check:** After this slice, every headless iteration's
runner and judge receive narrow-first investigation guidance — an observable
change in the prompts the loop actually dispatches, end-to-end.

### Deviation log (after reconciliation)

_TODO: filled during reconciliation._

### Reconciliation sweep

_TODO: record drift-prone surfaces checked (agent prompts, README, status board,
any vendored gate.py/agent copies)._
