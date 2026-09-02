---
slice: 031-01 — loop-driver-relabel
pass: arch
verdict: pass
reviewer: jig:reviewer (fresh, read-only, arch-review skill)
reviewed_at: 2026-09-01T19:43:20Z
prompt_source: review.py arch-review --richer-skill arch-review
substrate: non-interactive
---

Architecture review of slice 031-01 — loop-driver-relabel. VERDICT: **pass**.

Faithfully realizes ADR-0037 Option E. The relabel is a pure post-halt transform
(`_relabel_terminal_reason`, loop.py:1980-2016) invoked *after* the existing
brakes already set `terminal_reason` (loop.py:2533) — no new mid-run brake, so
the "can never fire earlier than today, can never lose a capable run" property is
structurally preserved. The disk-delta seam is tight (before/after the runner
invoke only, runner-iterations-only, skip-once-armed, bookkeeping-filtered). The
schema decision is sound: additive `runner_ever_edited` + `setdefault(False)`
backfill, no version bump — explicitly sanctioned by ADR-0004:44 ("a new optional
field with a documented default MAY keep the version at 1"); resume compat holds
both directions. Correctly scoped to `run_loop`; no goal-driver leakage.

Non-blocking open question (→ reconciliation log): `edit_signal_available`
re-derived as `_is_git_work_tree(target)` at the relabel guard while arming uses
`_tree_snapshot` (None on git *errors* too, not just non-git). On a valid tree
whose `git status` fails during arming, the flag never arms while the guard reads
"available" → possible mislabel. AC9 framed the fallback by target *type*
("non-git") rather than signal *computability* — the frame gap. Very low
likelihood, largely absorbed by the below-threshold residual. Consider tracking a
"signal actually computed at least once" bit and feeding that (not
git-tree-ness) as `edit_signal_available`. (Same finding as compliance + craft.)

Reconciliation notes:
- Doc drift: `docs/architecture.md` (state.json schema field list ~:228, terminal
  reasons) does not mention the new persisted `runner_ever_edited` /
  `terminal_breadcrumb` fields or `edit_permission_unavailable`. Update it or
  record the deliberate "ADR-0037 is the single source" choice.
- rc=2 on a *fully-executed* `run_loop` is new (loop.py:2550) — the intended
  fail-closed signal (AC1), but downstream exit-code consumers (heartbeat
  dispatch, `docs/architecture.md:236`) should be re-checked when 031-02 lands.
