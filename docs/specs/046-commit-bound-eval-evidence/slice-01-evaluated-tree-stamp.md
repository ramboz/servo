---
status: DRAFT
dependencies: [042-04, adr-0002, adr-0004]
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

## Slice 046-01 — evaluated-tree-stamp

**Goal:** Every oracle evaluation servo records — the gate's JSON payload, each
loop history entry, spec-oracle ledger rows and eval scoring records — names the
tree it judged: the `HEAD` commit plus digests of the uncommitted tracked diff
and of untracked files (042-04's content fingerprint), or an explicit `null`
with a reason. Any score can then be traced to the exact content behind it.

**DoR:**
- ✅ 042-04 DONE: the fingerprint primitive exists
  (`skills/agent-loop/loop.py:2288-2304`) and campaign's verifier already shares
  it through the dynamic loader.
- ✅ Arch review agrees where the shared fingerprint lives so that `loop.py`,
  campaign and `gate.py`'s portable closure (`gate.py` / `required_runtime.py` /
  `gate_consumer.py`, vendored into targets) all load one implementation —
  never a static cross-skill import.
- ✅ [jig ADR-0069](https://github.com/ramboz/jig/blob/main/docs/decisions/adr-0069-commit-bound-verification-evidence.md)
  Accepted, so field naming is checked against its vocabulary once.

**Acceptance Criteria:**

1. **The gate payload names its tree.** `gate.py <target> --json` (v1 and v2
   payloads) carries `evaluated_tree: {algo, head, tracked_diff, untracked}`,
   computed just before the oracle runs. On a non-git target it carries
   `evaluated_tree: null` with `evaluated_tree_reason: "not_a_git_work_tree"`.
   Text mode adds `evaluated=<short-head>` plus `+dirty` when there are
   uncommitted changes. `schema_version` stays 1 (ADR-0002 clause 2: additive,
   and absent means unbound for older payloads).
2. **One implementation.** On the same tree, the gate's `evaluated_tree` equals
   what `loop.py` records as `halt_fingerprint`; a test asserts equality, and the
   042-04 campaign verify fixtures still pass.
3. **Servo's own evidence does not move the fingerprint.** The shared exclusion
   predicate (`loop.py:2100-2120`, sets at `:342-347`) also excludes servo's
   evidence writes inside a spec directory: `oracle/<id>/ledger.jsonl`,
   `oracle/<id>/runs/`, and `eval/<id>/**/ledger.jsonl`. Fixture: on a clean
   tree, the fingerprint before a scored run that appends ledger rows equals the
   fingerprint after it. (Because loop and campaign share the predicate, a
   campaign item recorded before upgrade and verified after it may downgrade to
   advisory once — the safe direction; noted in the deviation log if seen.)
4. **Loop history entries carry it.** Each `oracle_score_history` entry
   (`loop.py:4910-4918`) and the goal driver's recorded final gate result carry
   the gate's `evaluated_tree`. This is additive under ADR-0004; absent in older
   state means unbound.
5. **Component ledgers carry the same value.** Spec-oracle ledger rows
   (`skills/spec-oracle/checks.py:1069-1080`) and the scoring records of
   eval-authoring, design-eval and content-fidelity
   (`skills/eval-authoring/score.py:626-650` and siblings) carry the
   `evaluated_tree` the gate computed, handed to the oracle process through its
   environment. A component run outside the gate records
   `evaluated_tree: null` with `evaluated_tree_reason: "unbound_invocation"`;
   the field is never simply absent.
6. **Read-only.** Computing the stamp performs no git writes: refs, `HEAD` and
   the index are unchanged across a scored run.
7. **Docs.** `docs/architecture.md` documents `evaluated_tree` in the
   quality-gate JSON contract, the `state.json` schema line and the spec-oracle
   and eval ledger entries, and widens the 042-04 fingerprint description to say
   it is also the per-evaluation stamp.

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
      the spec's Active-specs entry. If the spec is still in flight, leave
      the entry.

**Anti-horizontal-phasing check:** After this slice, anyone reading a ledger
row, a loop's `state.json` or a gate payload can tell exactly which tree that
score was for, including when the tree had uncommitted changes, without trusting
a timestamp.

### Deviation log (after reconciliation)

The original spec is preserved above. Implementation notes:

_Filled at reconciliation._

### Reconciliation sweep

_Filled at reconciliation (artifact / disposition / rationale table)._
