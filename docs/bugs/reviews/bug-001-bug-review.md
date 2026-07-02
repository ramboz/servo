---
bug: 001
pass: bug-review
verdict: pass
reviewer: jig:reviewer (independent read-only subagent)
reviewed_at: 2026-07-02T16:45:05Z
prompt_source: orchestrator bug-review prompt (jig:bug-fix review pass, independent read-only subagent)
---

Independent bug-review (read-only subagent). Fix targets the confirmed root
cause: `_invoke_claude` inspects the parsed envelope's `is_error` and routes a
hard failure to the existing `(None, breadcrumb)` -> `claude_invocation_failed`
(exit 2) seam rather than inventing a new path. `test_auth_error_envelope_...`
fails on all four assertions without the fix (genuine red->green). Exclusion set
{error_max_budget_usd, error_max_turns} is correct and complete for loop mode;
`test_budget_halt_envelope_is_still_scored` guards the blast radius. Normal
success (falsy is_error) is untouched. `fix_class: local_patch` honest. No blockers.
