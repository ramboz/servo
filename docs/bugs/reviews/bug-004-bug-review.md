---
bug: 004
pass: bug-review
verdict: pass
reviewer: jig:reviewer (independent read-only subagent)
reviewed_at: 2026-07-02T17:50:42Z
prompt_source: orchestrator bug-review prompt (jig:bug-fix review pass, independent read-only subagent)
---

Independent bug-review (read-only subagent). Fix addresses the two confirmed
goal-path omissions: `_settings_args(target)` forwarded in `_invoke_claude_goal`
argv (bug 002 twin), and an `is_error` branch in `run_goal_loop` placed AFTER
`transcript_showed_pass` and BEFORE the final gate (bug 001 twin), so an errored
`/goal` run halts `claude_invocation_failed` (exit 2) rather than being scored as
`oracle_below_threshold`. Branch correctly excludes the cap subtypes
(error_max_turns/error_max_budget_usd) — the existing GoalTerminalReasonMapTests
act as a live guard — and cannot fire on normal success (is_error false). No
routing-audit risk (audit reads only disableAllHooks/allowManagedHooksOnly).
Both regression tests are genuine red-without-fix. `fix_class: local_patch`,
`security_surface: false` honest. No blockers.
