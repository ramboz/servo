---
slice: 043-03 — cross-process resume of a Copilot run
pass: craft
verdict: pass
reviewer: general-purpose
reviewed_at: 2026-11-14T18:39:09Z
prompt_source: review.py pr-review --richer-skill none --non-interactive (spec 043-03); R2
substrate: non-interactive
---

VERDICT: pass.

Scope matches the slice exactly, no creep: narrowed `backend_mismatch` guard; the
two-part AC5 fail-closed block (baseline VALUE + STALENESS) under
`if host == HOST_COPILOT`; the `_COPILOT_RESUMABLE_HALTS` allow-list;
`REASON_CREDIT_BASELINE_UNAVAILABLE`; a `credit_ceiling` resume override symmetric
with cost_ceiling. All three host trees byte-identical to canonical.

Correctness: the value check is short-circuit-safe for str/None/float and the
`bool` clause defeats Python's bool-is-int subtyping; `iter_nano` is integer
throughout so a clean halt persists an int baseline. The interrupt checkpoint does
finalize+bump before `_apply_copilot_credit_iteration`, and an uncaught kill leaves
last_terminal_reason "" / None — so the comment premises are accurate. The e2e
proves no double-count (90cr exact).

Design: allow-list over deny-list is the correct fail-closed call (a future
terminal reason is refused-until-vetted, not silently resumable). The two-part
guard is cleanly structured (value before staleness, each with a distinct
actionable message). Tests non-vacuous (each AC5 sub-condition isolated; the
cross-process mock genuinely exercises the session-delta premise).

3.9-safe (py_compile on 3.9.6 OK; string-quoted return hints; backslash-
continuation, not the 3.10 parenthesized `with`); ruff 0.15.17 clean; no regression
across 20 existing resume tests.

Three nits (all non-blocking): (1) the inherited `host`-key discriminator handling
covers a state key written nowhere today — kept, since it backs the documented
6-case backend_mismatch regression (hand-edited / forward-compat states); (2) the
`credit_ceiling` override comment's dead-path "direct programmatic entry" phrasing —
FOLDED (comment corrected); (3) a copilot `--resume` omitting `--credit-ceiling` is
refused by the generic `_refuse_copilot_capability()` rather than a resume-specific
message — by design (the ceiling is a required opt-in), noted in the deviation log.
(Separately, the staleness refusal message was widened in response to compliance's
pre-invocation-halt note so it does not assert "orphaned spend" for every non-resumable
reason.)

Prompt source: review.py pr-review --richer-skill none --non-interactive (spec 043-03); round 2.
