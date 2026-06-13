---
slice: 003-08 — detach-and-schedule
pass: craft
verdict: pass
reviewer: pr-review (general-purpose)
reviewed_at: 2026-06-13T18:35:58Z
prompt_source: review.py pr-review docs/specs/003-agent-loop/spec.md 003-08 <deliverables>
---

VERDICT: pass

REASONING:
Detach mechanism correct — start_new_session for true session detachment, clean fd
handoff (stdin=DEVNULL, stdout/stderr -> run-dir log, parent fd closed after the child
dup's its own), fail-closed on both un-openable log and un-spawnable child. Parent/child
run-id injection is sound (parent pre-allocates + seeds state.json; child reuses via
--_detached-run-id; child carries --allow-dirty since the parent is the single dirty-tree
gate). Flag-conflict handling exhaustive + actionable. Tests meaningful (real detached
subprocess + bounded poll-until-condition, not a fixed sleep; dirty-before-detach asserts
no run dir). Naming/idioms match the 003-06/003-07 baseline. 20 new cases pass; ruff clean.

SPECIFIC ISSUES:
- [strength] loop.py _spawn_detached — textbook detachment (setsid, DEVNULL, fd in finally) + fail-closed breadcrumbs.
- [strength] loop.py run-id re-entrancy handled cleanly (reuse parent dir; detached child short-circuits routing).
- [strength] loop.py run_goal_loop_background — preflight-before-detach satisfies AC4's clean-baseline intent.
- [strength] test_loop.py detached-run integration test is genuinely end-to-end + bounded poll; dirty-before-detach is a real regression guard.
- [strength] loop.py _compose_goal_prompt python= seam minimal + well-justified.
- [nit] loop.py run_goal_loop_background didn't document the host-eligibility caller-precondition. -> ADDRESSED inline (docstring note).
- [nit] loop.py background.log was a bare literal vs the STATE_FILE_NAME convention. -> ADDRESSED inline (BACKGROUND_LOG_NAME constant).

RECONCILIATION NOTES:
Both nits were addressed inline post-review (BACKGROUND_LOG_NAME constant; caller-precondition
docstring). No blockers; craft consistent with the 003-06/003-07 baseline.
