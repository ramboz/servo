---
status: DRAFT
dependencies: [045-01, 045-02, adr-0051, adr-0005, adr-0024]
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

## Slice 045-03 — eval-freeze-base-anchor

**Goal:** The shared eval freeze (`validate_freeze`,
`skills/_common/fidelity_eval.py:275-299`) reads `approval_status`,
`approved_content_hash` and the frozen `hashes` for an eval-authoring component
from the base copy of its tracked definition
(`<spec_dir>/eval/<spec-id>/<eval>/config.json`), so a run cannot re-freeze the
installed copy under `.servo/<component>/` with a lower threshold or a weaker
rubric. Preset evals with no tracked definition are stamped worktree-anchored
on every ledger record.

**Context (probed):** `emit_target` freezes the tracked spec-dir copy
(`skills/eval-authoring/eval_authoring.py:1404-1446`), then `install_component`
copies it into the git-ignored `.servo/<component>/config.json` without
recording where it came from (`:1375-1381`). The spliced fragment calls
`.servo/<component>/score.py` (`:1322-1333`). The design-eval and
content-fidelity presets author and freeze their config only under `.servo/`
(`skills/design-eval/design_eval.py:82`, `:237`;
`skills/content-fidelity/content_fidelity.py:69-70`), so they have no base copy.

**DoR:**
- ⬜ 045-01 DONE (resolver, fallback semantics).
- ⬜ 045-02 DONE. The tracked-definition path is named in the `oracle.sh`
  fragment (AC1), and only a base-anchored `oracle.sh` keeps a run from
  redirecting it.

**Acceptance Criteria:**

1. **The installed component names its tracked definition in a base-anchored
   place.** `install_component` puts the target-relative path of the tracked
   frozen definition into the component's spliced `oracle.sh` fragment (for
   example as an argument to `score.py`), not only into the git-ignored
   `.servo/<component>/` copy. Under 045-02 a run therefore cannot point it
   elsewhere. A component installed before this slice records
   `freeze_anchor: {kind: "worktree", reason: "no_source_definition"}` until it
   is reinstalled.
2. **The base copy's record is the expected value.** With an anchor and a base
   copy of the tracked definition, `validate_freeze` takes `approval_status`,
   `approved_content_hash` and `hashes` from the base copy and checks the
   installed config and artifacts against them; a mismatch raises `StaleError`
   (exit 2) naming the anchor. Fixture: re-freeze
   `.servo/<component>/config.json` with a lowered `threshold` and
   self-consistent hashes. Before this slice it scores; after, exit 2.
3. **Same fallback rules as 045-01.** A base copy that is not approved → exit 2,
   "approval not committed on base `<short-sha>`". No anchor, or no copy at the
   anchor → today's working-tree check plus the stamp and one stderr line.
4. **Presets are stamped, not changed.** design-eval and content-fidelity
   scoring records carry `freeze_anchor: {kind: "worktree", reason:
   "untracked_definition"}` on every ledger record and print one stderr line per
   score; their freeze behaviour is otherwise unchanged.
5. **One implementation, in the shared harness.** The anchor lookup lives in
   `skills/_common/fidelity_eval.py` (ADR-0024) and all three `score.py`
   callers (`eval-authoring/score.py:170`, `design-eval/score.py:139`,
   `content-fidelity/score.py:114`) go through it; the installed runtime copy of
   the harness carries it.
6. **Docs name the residual.** `docs/architecture.md` (the `<spec_dir>/eval/`
   entry and the threat model) lists which eval definitions are base-anchored
   (eval-authoring) and which are not (presets), and that the installed runtime
   copies under `.servo/<component>/` (`score.py`, `fidelity_eval.py`) stay
   outside the anchor.

**DoD:**
- [ ] All ACs pass; full test suite green (no regressions).
- [ ] Implementer test coverage exercises each AC with at least one
      fixture. Edge cases listed in the slice are covered explicitly.
- [ ] Each new test has been shown to fail when its feature is removed —
      the test is capable of failing, not vacuously green (mutate the
      feature, watch the test go red, restore).
- [ ] Host packages regenerated (`build_host_packages.py`) and `--check`
      clean.
- [ ] Reviewed by `reviewer` subagent. Reviewer prompt built by
      `review.py`.
- [ ] Implementation review passed.
- [ ] Deviation log produced under this slice heading.
- [ ] Reconciliation sweep produced under this slice heading.
- [ ] Reconciliation review passed.
- [ ] `docs/refinement-todo.md` updated if any decisions were
      deferred during implementation (expected: an entry for giving preset
      definitions a tracked home, per ADR-0051 Open questions).

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
      the spec's Active-specs entry. If the spec is still in flight, leave
      the entry.

**Anti-horizontal-phasing check:** After this slice, a judged eval authored
through `/servo:eval-authoring` and approved on the base cannot be quietly
re-frozen by a run, and a preset eval's results say plainly that their
definition was not base-anchored.

### Deviation log (after reconciliation)

The original spec is preserved above. Implementation notes:

_Filled at reconciliation._

### Reconciliation sweep

_Filled at reconciliation (artifact / disposition / rationale table)._
