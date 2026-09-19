---
slice: 031-01 — loop-driver-relabel
pass: compliance
verdict: pass
reviewer: jig:reviewer (fresh, read-only)
reviewed_at: 2026-09-01T19:43:20Z
prompt_source: review.py implementation
---

Compliance review of slice 031-01 — loop-driver-relabel. VERDICT: **pass**.

All nine acceptance criteria met and backed by non-vacuous tests. The relabel is
a pure, conjunct-isolated helper (`_relabel_terminal_reason`, loop.py:1980) gated
on existing-brake halt + git-signal-available + unarmed + below-threshold, wired
to exit rc=2 (loop.py:2550). The signal is an untracked-inclusive per-invoke
delta (`_tree_snapshot`, loop.py:1556) bracketing only the runner invoke
(loop.py:2332-2350), armed into a persisted `runner_ever_edited` flag that
survives `--resume`. Each DoD mutation check (oracle-below conjunct,
disarm-on-edit, untracked inclusion, judge exclusion) has a test that flips red
if the guard is neutered; host-package copies carry the change (13/13 symbol
parity, no drift). No principle violations.

Non-blocking finding (→ reconciliation log): signal-availability asymmetry
(loop.py:2537 vs 1580-1582) — the relabel guard re-probes `_is_git_work_tree`
while arming uses `_tree_snapshot` (None on non-git OR transient git-status
error); on a healthy tree whose `git status` transiently errors, a capable run
could be mislabeled. Bounded to already-failing runs by the below-threshold
conjunct; no AC covers transient git errors (AC9 scoped fallback to "non-git").

Intentional interpretation to record: AC5's "below threshold (not a pass)" is
implemented as `== STATUS_BELOW_THRESHOLD`, which also excludes `env_error`
halts from relabeling — a defensible tightening (a broken-gate halt is a
different diagnosis), consistent with the AC's literal wording.
