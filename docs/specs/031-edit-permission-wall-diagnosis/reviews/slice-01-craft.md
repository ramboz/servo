---
slice: 031-01 — loop-driver-relabel
pass: craft
verdict: pass
reviewer: jig:reviewer (fresh, read-only, pr-review skill)
reviewed_at: 2026-09-01T19:43:20Z
prompt_source: review.py pr-review --richer-skill pr-review
substrate: non-interactive
---

Craft review of slice 031-01 — loop-driver-relabel. VERDICT: **pass** (no blockers).

Strengths: `_relabel_terminal_reason` is pure with every conjunct independently
checkable, matched 1:1 by `RelabelDecisionUnitTests` (cheap mutation
verification). The before/after *delta* (not absolute clean-tree) correctly
treats pre-existing untracked files as not-this-iteration's change
(`test_preexisting_untracked_dirt_does_not_arm`); "skip snapshot once armed"
avoids redundant git calls.

Non-blocking nits (→ reconciliation log):
- [nit][spec] loop.py:2537 vs 1572/1581 — relabel gate reads
  `edit_signal_available=_is_git_work_tree` (rev-parse only) while arming uses
  `_tree_snapshot` (None on non-git OR any git-status error). Transient
  git-status error during a runner edit → flag never arms AND gate passes → a
  capable run mislabeled `edit_permission_unavailable`. Bounded to already-failing
  runs by the below-threshold conjunct (ADR-0037's stated blind-spot). Fix:
  gate the relabel on the same signal-computable notion the arming path uses.
  (Same finding as compliance + arch — 3/3 convergence.)
- [nit][impl] test_loop.py:8053-8076 — AC7 calls the before/after bracket the
  "primary isolation," but no test exercises it: both AC7 fixtures leave only
  `.servo/`/cache residue, which the filter catches regardless of snapshot_after
  timing. A fixture where the gate/oracle creates a non-bookkeeping untracked
  file AFTER the invoke would prove the bracket is load-bearing, not just the
  filter.
- [nit][impl] loop.py:1556,1583 — bare `set` / `Optional[set]`; the file's
  convention is parameterized (`Optional[list[str]]`). Use `set[str]` /
  `Optional[set[str]]` (safe on the 3.9 floor).

Note: `.gitignore`d-only edits would also not arm — same accepted blind-spot
class; worth a one-line note if 031-02 reuses these helpers. No scope creep;
`run_goal_loop` untouched; additive field, no schema bump (justified).
