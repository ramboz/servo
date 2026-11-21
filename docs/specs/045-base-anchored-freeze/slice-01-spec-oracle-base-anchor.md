---
status: DRAFT
dependencies: [adr-0051, adr-0022, adr-0023]
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

## Slice 045-01 — spec-oracle-base-anchor

**Goal:** `checks.py --enforce-freeze` reads the spec-oracle's approval record —
`approval_status`, `approved_content_hash`, `approved_artifacts`, and in
required mode `approved_required_binding` — from the base ref's copy of
`checks.json` instead of the working tree's. A change that edits a check and
rewrites its recorded hash in the same file is then refused. Where no base copy
exists, the freeze runs against the working tree as it does today and says so.

**DoR:**
- ✅ [ADR-0051](../../decisions/adr-0051-base-anchored-freeze.md) Accepted.
- ✅ Home for the anchor resolver agreed at arch review. It must be reachable
  from `checks.py` (referenced or vendored), `gate.py`'s portable closure
  (045-02) and the eval harness (045-03) through the existing dynamic-load
  pattern, never a static cross-skill import.
- ✅ Fixture: a scratch git repo with an approved overlay committed on `main`
  and a feature branch, built in the test (no network).

**Acceptance Criteria:**

1. **Anchor resolution.** Under `--enforce-freeze`, the anchor is
   `SERVO_FREEZE_BASE` when set; it must resolve to a commit, otherwise rc=2
   with reason `freeze_base_invalid` (a configured base that does not resolve is
   an error, not a fallback). Unset, the anchor is
   `git merge-base HEAD <default>`, where `<default>` is the first of
   `refs/remotes/origin/HEAD`, `main`, `master` that resolves locally.
   Otherwise there is no anchor. No network call is made. Fixtures cover each
   source.
2. **The base copy's record is the expected value.** When the anchor's tree has
   the overlay's `checks.json` at the same repo-relative path, the freeze
   compares the working tree's plan content hash, `oracle.sh.fragment` and
   (when vendored) `checks.py` against the hashes recorded in the *base copy*.
   Fixture: approve and commit on `main`; on the branch, relax a check and
   recompute `approved_content_hash` in the working tree. Before this slice the
   component exits 0; after, rc=2 `spec_oracle_plan_modified`, with stderr
   naming the anchor (`base <short-sha> via merge_base`).
3. **Approval has to be on the base.** A base copy that is `draft` or `stale`
   while the working tree says `approved` → rc=2 `spec_oracle_unapproved` or
   `spec_oracle_stale`, and the message says: approval not committed on base
   `<short-sha>`; commit it on the base or set `SERVO_FREEZE_BASE` to a
   reviewed commit.
4. **Explicit fallback.** With no anchor, or no `checks.json` at the anchor,
   today's working-tree comparison runs unchanged. Stderr carries exactly one
   line `spec-oracle: freeze anchored to worktree (<reason>)`, where reason is
   one of `not_a_git_work_tree`, `no_default_branch`, `base_object_missing`,
   `no_base_copy`. Every ledger row of that run carries
   `freeze_anchor: {kind: "worktree", reason}`; an anchored run's rows carry
   `freeze_anchor: {kind: "base", ref: <sha>, source: "configured" | "merge_base"}`.
5. **Required mode reads the same base copy.** For a required-mode plan,
   `validate_binding` (`skills/quality-gate/required_runtime.py:457-485`)
   receives the base copy's `approved_required_binding` as the expected entry,
   so a working-tree binding edited after approval is refused
   (`approved binding modified`).
6. **Read-only and scoped.** Resolution and base reads use only read-only git
   (`rev-parse`, `merge-base`, `cat-file`, `show`); a test shows refs, `HEAD`
   and the index unchanged across a scored run. `checks.py` without
   `--enforce-freeze` makes no git call and its output is byte-identical to
   today's (authoring stays frictionless, `docs/architecture.md:280`).
7. **Docs tell the truth.** The "Spec-oracle freeze & approval" threat model in
   `docs/architecture.md` (`:282`) describes the base anchor, the fallback, the
   approval-on-base workflow, and the residuals (the `oracle.sh` bypass until
   045-02 lands; untracked `.servo/` copies). The `agents/runner.md:96` bullet
   says edits are judged against the base copy.

### Behavioral rules

| Rule | Operation/control | Actor | State/precondition | Outcome | Rationale | AC |
|------|-------------------|-------|--------------------|---------|-----------|----|
| BR-1 | enforced score | oracle component | anchor = base; base copy approved; working tree matches it | scores | the reviewed oracle is the one running | AC2 |
| BR-2 | enforced score | oracle component | anchor = base; base copy approved; working tree differs | rc=2 `spec_oracle_plan_modified` / `spec_oracle_artifact_modified` | the change edited its own judge | AC2 |
| BR-3 | enforced score | oracle component | anchor = base; base copy `draft` / `stale` | rc=2 unapproved / stale on base | approval must be on the base | AC3 |
| BR-4 | enforced score | oracle component | anchor = base; no copy at the path | worktree check + `no_base_copy` stamp | branch-local oracle, visibly unanchored | AC4 |
| BR-5 | enforced score | oracle component | no anchor resolvable | worktree check + reason stamp | never silent | AC4 |
| BR-6 | enforced score | oracle component | `SERVO_FREEZE_BASE` set but unresolvable | rc=2 `freeze_base_invalid` | an explicit choice that fails is an error | AC1 |

**DoD:**
- [ ] All ACs pass; full test suite green (no regressions).
- [ ] Implementer test coverage exercises each AC with at least one
      fixture. Edge cases listed in the slice are covered explicitly.
- [ ] Each new test has been shown to fail when its feature is removed —
      the test is capable of failing, not vacuously green (mutate the
      feature, watch the test go red, restore).
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

**Anti-horizontal-phasing check:** After this slice, an overlay approved on the
base can no longer be relaxed and re-hashed by a branch or a loop run; the
refusal names the base commit it checked against. The remaining bypass — editing
the spliced block in `oracle.sh` to drop `--enforce-freeze` — is stated in the
docs and closed by 045-02.

### Deviation log (after reconciliation)

The original spec is preserved above. Implementation notes:

_Filled at reconciliation._

### Reconciliation sweep

_Filled at reconciliation (artifact / disposition / rationale table)._
