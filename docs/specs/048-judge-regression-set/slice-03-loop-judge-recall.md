---
status: DRAFT
dependencies: [adr-0053]
last_verified: 2026-11-21
---

<!-- jig self-defining vocabulary (soft, forward-only): expand each acronym on
     first use and link the term to docs/memory/glossary.md (or jig's lexicon).
     See docs/workflow.md "Self-defining vocabulary". -->

<!-- jig grounding (spec 064-02 / ADR-0020): ground factual claims about
     runnable surfaces by probe first (run it / read source) or a citation,
     else mark them as assumptions in the spec's `## Assumptions` section —
     never assert an unverified claim as fact. -->

## Slice 048-03 — loop-judge-recall

**Goal:** The loop's judge (`agents/judge.md`) is scored against a labeled case
set — runner changes with a seeded defect and a one-sentence answer key, plus
clean controls — reporting recall per stage (the finding in `reasoning`, then
the verdict) and an over-flagging rate, in results tied to the prompt, tools and
model they measured, so any change to those marks the results stale.

**DoR:**
- ✅ [ADR-0053](../../decisions/adr-0053-judge-regression-rescore.md) Accepted.
- ✅ The owner has agreed who pays for runs (one judge call per case per run) and
  that no CI step requires a billed run (ADR-0053 Open questions).
- ✅ If jig [spec 126](https://github.com/ramboz/jig/blob/main/docs/specs/126-reviewer-recall-eval/spec.md)
  has landed, its case format has been read and adopted where it fits; this
  slice does not depend on it.

**Acceptance Criteria:**

1. **A labeled case set.** `skills/agent-loop/judge-eval/cases/<id>/` holds, per
   case, a small target fixture the judge can read, the gate JSON and runner
   verdict block the judge is shown, and `answer.json` (`kind: defect|control`,
   the expected verdict class, a one-sentence answer key for defects, and a
   source: a captured run log or authored). The set lands with at least six
   defect cases — including a fix the oracle still scores low, a fix that breaks
   an unrelated required item, and a violated runner assumption (spec 021) — and
   at least three controls that are correct changes.
2. **The loop's own prompt and parser.** `judge_eval.py run` builds each prompt
   with `_assemble_iteration_prompt` (`skills/agent-loop/loop.py:676`), invokes
   the `judge` agent the way the loop does with the configured `models.judge`
   (or the default), and parses with `_parse_verdict_block` (`loop.py:611`). An
   unparseable verdict counts as a miss and is recorded as one.
3. **Recall per stage.** For defect cases: verdict recall is the share judged
   `FAIL` or `INCONCLUSIVE`; finding recall is the share whose `reasoning` a
   human credited as describing the answer-key defect, from a crediting sheet
   the run emits (uncredited cases are excluded and counted). "Found but passed"
   — credited finding, `PASS` verdict — is reported separately. For controls:
   the over-flag rate is the share not judged `PASS`.
4. **Bound to what it measured.** Each run appends to
   `skills/agent-loop/judge-eval/results.jsonl` with the sha256 of
   `agents/judge.md`, its frontmatter `tools`, the model id, the case-set hash,
   per-case raw output, and the metrics.
5. **Staleness is visible, not blocking.** `judge_eval.py status` prints `current`
   or `stale` (no results, or the prompt hash, tools or model differ from the
   latest result) and exits 0 either way; `scripts/ci_check.py` prints that line
   without failing.
6. **Offline-testable.** `judge_eval.py score --replay <results>` recomputes the
   metrics from recorded outputs with no model call, so the scoring and crediting
   logic is unit-tested.
7. **Docs.** `skills/agent-loop/SKILL.md` states that the judge prompt is
   measured, how to re-run, what it costs, and that results are advisory.
   Surface-tested.

**DoD:**
- [ ] All ACs pass; full test suite green (no regressions).
- [ ] Implementer test coverage exercises each AC with at least one
      fixture. Edge cases listed in the slice are covered explicitly.
- [ ] Each new test has been shown to fail when its feature is removed —
      the test is capable of failing, not vacuously green (mutate the
      feature, watch the test go red, restore).
- [ ] One billed baseline run recorded against the current `agents/judge.md`
      (owner-authorized), so the first status reads `current`.
- [ ] Host packages rebuilt and drift-clean
      (`scripts/build_host_packages.py --check`); Python 3.9 floor respected.
- [ ] Reviewed by `reviewer` subagent. Reviewer prompt built by
      `review.py`.
- [ ] Implementation review passed.
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

**Anti-horizontal-phasing check:** After this slice, an edit to the loop judge's
prompt or model shows up as stale results, and one command says whether the new
judge still catches the seeded defects, still passes the clean changes, and
whether it finds bugs it then lets through.

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
