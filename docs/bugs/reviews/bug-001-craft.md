---
bug: 001
pass: craft
verdict: pass
reviewer: jig:reviewer (independent read-only subagent)
reviewed_at: 2026-07-02T16:45:05Z
prompt_source: orchestrator craft prompt (jig:bug-fix review pass, independent read-only subagent)
---

Craft pass (pr-review rubric). Minimal single-function change, no new
terminal_reason/exit code/constants; reuses SUBTYPE_ERROR_MAX_BUDGET/TURNS.
Breadcrumb handling robust: missing/empty/whitespace/multiline `result` all safe
(falls back to subtype then "error"; .splitlines()[0]; [:200] cap); api_error_status
appended only when truthy; all .get on confirmed dict. Inline comment explains
the exclusion rationale. Goal driver (`_invoke_claude_goal`) retains a weaker
form of the same masking (surfaces oracle_below_threshold not claude_invocation_failed)
— defensible loop-scoped boundary, worth a follow-up. No blockers.
