---
slice: 011-04 — heartbeat-cost-ceiling
pass: craft
verdict: pass
reviewer: codex-main-local-pr-review
reviewed_at: 2026-06-18T15:36:16Z
prompt_source: review.py pr-review docs/specs/011-heartbeat/spec.md 011-04 skills/heartbeat/heartbeat.py skills/heartbeat/test_heartbeat.py docs/decisions/adr-0012-heartbeat-whole-pass-cost-ceiling.md docs/specs/011-heartbeat/slice-04-heartbeat-cost-ceiling.md
---

VERDICT: pass

REASONING:
The change is tightly scoped and follows the existing heartbeat style: stdlib-only
helpers, list-form subprocess plumbing, the established env override test seam,
atomic inbox writes, advisory locking, and closed `{0,2}` exits. The code keeps
manual `dispatch --cost-ceiling` semantics separate from scheduled `run`
semantics, and the tests use the existing real-git/mock-gh/mock-loop harness
without adding live network or LLM calls. No blockers or should-fix issues remain
after the pass-scoped budget correction.

SPECIFIC ISSUES:
- [strength] skills/heartbeat/heartbeat.py:1783 — `run_dispatch` extends the
  existing serial dispatch flow with optional whole-pass accounting instead of
  duplicating the dispatch pipeline for `run`.
- [strength] skills/heartbeat/heartbeat.py:1901 — budget halts happen before
  spawning the next loop, which is the safest point available around an in-flight
  `loop.py` process.
- [strength] docs/decisions/adr-0012-heartbeat-whole-pass-cost-ceiling.md:72 —
  the ADR explicitly documents the non-crash-resumable tradeoff instead of hiding
  it in implementation details.

RECONCILIATION NOTES:
Carry forward the scope note that crash-resume budgeting is not implemented. The
current design remains simpler and keeps future scheduled heartbeats able to make
progress; a future slice can add a heartbeat pass id or ledger if strict crash
resume becomes necessary.
