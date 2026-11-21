---
status: DRAFT
dependencies: [046-01, adr-0002]
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

## Slice 046-02 — gate-ledger-and-staleness

**Goal:** Every `gate.py` invocation on an existing target appends one record —
pass, below threshold, or not evaluable (an env-error with its reason) — bound to
the evaluated tree. A read-only `gate.py evidence <target>` then answers whether
the latest evidence still describes the current tree (`current` / `stale` /
`none`), so a pass on an out-of-date tree is never read as current.

**Context (probed):** on the ordinary path `gate.py` writes nothing; its result
exists only on stdout (`skills/quality-gate/gate.py:372`, `:482`). The oracle
hook can let a turn through on an env-error ("fail open"), and its docs say such
a turn "is **not completion attestation**" (`skills/oracle-hook/SKILL.md:81-82`)
— but nothing records that it happened.

**DoR:**
- ✅ 046-01 DONE (`evaluated_tree` exists on every gate payload).
- ✅ Ledger path and record shape agreed at arch review (proposed below).

**Acceptance Criteria:**

1. **Every outcome is recorded.** Each invocation whose target is an existing
   directory appends exactly one record to `<target>/.servo/gate-ledger.jsonl`
   (git-ignored, and excluded from the fingerprint as `.servo/` bookkeeping):
   `{kind: "gate_evaluation", schema_version: 1, at, status, exit_code, reason,
   composite, threshold, evaluated_tree, freeze_anchor, gate_ref}`.
   `freeze_anchor` is present when spec 045 provides it; `gate_ref` is the
   required-mode `.servo/gate-runs/<run_id>/gate.json` path and hash when one was
   written. Env-error outcomes — missing oracle, unexpected exit, timeout,
   `required_evidence_unavailable`, freeze refusals — are recorded with their
   `reason`: "not evaluated" is a recorded value, never an absence. A target that
   is not a directory has nowhere to record, and that is documented.
2. **Recording never changes the verdict.** Appends are `flock`-guarded with the
   campaign ledger's blocking discipline (`docs/architecture.md:266`). A write
   failure leaves the gate's exit code and payload unchanged (the best-effort
   precedent of `skills/_common/fidelity_eval.py:360-368`) and prints one stderr
   warning.
3. **The evidence verb reports freshness.** `gate.py evidence <target> [--json]
   [--paths P ...]`, dispatched like `audit` (`gate.py:699-716`), reads the
   latest record and the current fingerprint and reports `freshness`:
   - `current` when the record's `evaluated_tree` equals the current one; or
     when the record's uncommitted tracked changes were committed exactly (the
     digest of `git diff <record.head> HEAD --full-index` equals the record's
     `tracked_diff`, the record had no untracked files, and the working tree is
     now clean);
   - with `--paths`, a record taken on a clean tree is also `current` when
     nothing under those paths changed between `record.head` and the working
     tree, untracked files included;
   - `stale` when a record exists and none of the above holds; the output lists
     the paths changed since `record.head`, bounded like the dirty-tree
     breadcrumb (`skills/agent-loop/loop.py:2323`);
   - `none` when there is no record.

   `--json` carries `{freshness, outcome, evaluated_tree, record}`.
4. **Closed exit codes (ADR-0002).** 0 only for `current` with outcome `pass`;
   1 for `stale`, `none`, or a current non-pass outcome; 2 when the ledger is
   unreadable or the target is not a git work tree.
5. **The verb is read-only.** It writes no file and no git state: a byte
   snapshot of `.servo/` plus refs, `HEAD` and the index is unchanged afterwards.
6. **Docs.** `docs/architecture.md` (quality-gate JSON contract and the
   `.servo/` path list) documents the ledger and the verb, and states that the
   verb's `current` + `pass` result is the servo-side input a
   [jig ADR-0069](https://github.com/ramboz/jig/blob/main/docs/decisions/adr-0069-commit-bound-verification-evidence.md)
   stamp can cite, with `stale` / `none` corresponding to its `none`. Servo
   defines no trailer. `skills/oracle-hook/SKILL.md` notes that a turn let
   through fail-open now leaves a recorded non-pass outcome.

### Behavioral rules

| Rule | Operation/control | Actor | State/precondition | Outcome | Rationale | AC |
|------|-------------------|-------|--------------------|---------|-----------|----|
| BR-1 | `gate.py evidence` | person or jig commit gate | latest record's tree equals the current tree | `current` | exact binding | AC3 |
| BR-2 | `gate.py evidence` | person or jig commit gate | record was dirty; exactly those tracked changes are now committed; tree clean | `current` | the loop never commits; a human commit of the evaluated content keeps its evidence | AC3 |
| BR-3 | `gate.py evidence --paths` | person or jig commit gate | clean record; no listed path changed since `record.head` | `current` | the brief's "relevant paths" scoping | AC3 |
| BR-4 | `gate.py evidence` | person or jig commit gate | record exists; none of the above | `stale` + changed paths | an out-of-date pass means nothing | AC3 |
| BR-5 | `gate.py evidence` | person or jig commit gate | no record | `none` | "none" is queryable, not missing | AC3 |
| BR-6 | `gate.py <target>` | any caller | oracle missing / env-error | recorded with `reason` | not-evaluable is a recorded outcome | AC1 |

**DoD:**
- [ ] All ACs pass; full test suite green (no regressions).
- [ ] Implementer test coverage exercises each AC with at least one
      fixture. Edge cases listed in the slice are covered explicitly
      (new untracked files at evaluation time → `stale`; partial commit →
      `stale`).
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

**Anti-horizontal-phasing check:** After this slice, a person (or a jig commit
gate) can ask servo "is the latest oracle result about the tree in front of me?"
and get `current`, `stale` with the paths that moved, or `none`, and an oracle
that could not run leaves a record saying so instead of nothing.

### Deviation log (after reconciliation)

The original spec is preserved above. Implementation notes:

_Filled at reconciliation._

### Reconciliation sweep

_Filled at reconciliation (artifact / disposition / rationale table)._
