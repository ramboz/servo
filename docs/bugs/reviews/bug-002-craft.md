---
bug: 002
pass: craft
verdict: pass
reviewer: jig:reviewer (independent read-only subagent)
reviewed_at: 2026-07-02T16:45:05Z
prompt_source: orchestrator craft prompt (jig:bug-fix review pass, independent read-only subagent)
---

Craft pass (pr-review rubric). Clean, minimal implementation: one documented
helper plus one `cmd.extend`. Real argv-capture regression test covers present
and absent cases; resolved-path comparison correctly handles the macOS
/var -> /private/var symlink. `is_file()` symlink-following is desired behavior.
Only open items are reconciliation bookkeeping (frontmatter green/status), which
the teeth gate stamps on transition. No blockers.
