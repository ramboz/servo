---
slice: 043-03 — cross-process resume of a Copilot run
pass: frame-critique
verdict: pass
reviewer: general-purpose
reviewed_at: 2026-11-14T18:35:51Z
prompt_source: review.py frame-critique (spec 043-03); R1 needs-changes -> R2 pass
---

VERDICT: pass (round 2).

Round 1 (needs-changes, 1 load-bearing blocker): the slice's motivating scenario
is interruption, but that is exactly where the session-cumulative premise fails —
credit accumulation runs AFTER the interrupt checkpoint (which finalizes
REASON_INTERRUPTED and bumps iteration_count first), and a killed invocation
writes no usage file (ADR-0048 A3), so the persisted `cumulative_credits_nano` is
a stale lower bound. The original AC5 (null/absent/negative only) passed that
valid-but-stale int, risking either a fail-closed no-op or a silent under-count.

Fix: added a staleness guard (`_COPILOT_RESUMABLE_HALTS` allow-list — resume
allowed only from iteration cap / credit ceiling / plateau / context) + honest
spec narrowing (Goal + anti-horizontal-phasing scoped to clean halts;
interrupted/killed fail-closed; resume-after-kill probe deferred).

Round 2 (pass): verified in code that (a) all four resumable halts complete credit
accumulation before finalizing (sound baseline); (b) the excluded interrupt/kill
paths leave a non-resumable on-disk `last_terminal_reason` (Copilot hardcodes
terminal_reason="", or None pre-finalize), disjoint from the resumable set;
(c) the "resumable-reason on disk ⟹ sound baseline" invariant holds atomically
(`_finalize_state_and_summary` writes reason + accounted cumulative in one write;
`_relabel_terminal_reason` only moves reasons OUT of the set) — a kill cannot
forge a resumable+stale state; (d) the runtime `_copilot_iteration_nano`
reconciliation (`expected < 0` or OTel Σ ≠ delta) backstops the one residual edge
(a clean-halt run resumed then killed mid-first-resumed-iteration), so no path
silently under-counts. Tests faithful and non-vacuous.

Two precision nits folded: the spec's "fail-closed-refused" now documents the
two-layer enforcement (preflight for original runs; runtime reconciliation for a
kill-during-resume); the staleness test now includes the literal "" kill
signature.

Prompt source: review.py frame-critique (spec 043-03); R1 needs-changes -> R2 pass.
