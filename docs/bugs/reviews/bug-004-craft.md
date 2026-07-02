---
bug: 004
pass: craft
verdict: pass
reviewer: jig:reviewer (independent read-only subagent)
reviewed_at: 2026-07-02T17:50:43Z
prompt_source: orchestrator craft prompt (jig:bug-fix review pass, independent read-only subagent)
---

Craft pass (pr-review rubric). Two additive, well-commented changes reusing
existing seams (`_settings_args`, `REASON_CLAUDE_INVOCATION_FAILED`, `_finalize`);
`cumulative_cost_usd=cost_usd` correctly reports real spend (consistent with the
interrupt/goal_unavailable branches). Nit (not a blocker): the ~10-line goal
`is_error` block near-duplicates the loop-driver block; a shared
`_is_error_breadcrumb(envelope)` helper would prevent the two drivers from
drifting (which is bug 004's own lesson) — deferred as an optional quality
refactor since the call sites' control flow differs and parity tests guard both.
No blockers.
