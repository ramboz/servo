---
slice: 011-04 — heartbeat-cost-ceiling
pass: compliance
verdict: pass
reviewer: codex-main-local
reviewed_at: 2026-06-18T15:36:16Z
prompt_source: review.py implementation docs/specs/011-heartbeat/spec.md 011-04 skills/heartbeat/heartbeat.py skills/heartbeat/test_heartbeat.py docs/decisions/adr-0012-heartbeat-whole-pass-cost-ceiling.md docs/specs/011-heartbeat/slice-04-heartbeat-cost-ceiling.md
---

VERDICT: pass

REASONING:
Slice 011-04 is implemented against the fleshed acceptance criteria: `run` composes
`discover` then `dispatch`, applies one pass-scoped heartbeat ceiling, forwards
remaining budget to each loop, halts cleanly between candidates, and preserves the
closed `{0,2}` exit contract. The review initially found that lifetime-cumulative
inbox spend would starve later scheduled heartbeats; that was corrected before this
verdict by scoping spend to outcomes whose `dispatched_at` is at or after the
current pass start. The new tests meaningfully exercise the public CLI behavior,
including discovery env-errors, current-pass budget recomputation, budget-floor
halts, overshoot halts, and the regression that old outcomes do not drain a fresh
run budget.

SPECIFIC ISSUES:
- [strength] skills/heartbeat/heartbeat.py:1688 — `_spent_cost_usd(..., since=...)`
  keeps spend accounting on the ADR-0010 inbox spine while avoiding the reviewed
  lifetime-budget starvation bug.
- [strength] skills/heartbeat/heartbeat.py:1982 — `run_heartbeat` captures the pass
  start before discovery, so current-pass outcomes can be charged without requiring
  a new schema field in this slice.
- [strength] skills/heartbeat/test_heartbeat.py:3216 — the tests verify observable
  CLI behavior and forwarded `--cost-ceiling` values rather than helper internals.

RECONCILIATION NOTES:
Record the reviewed semantic adjustment: the accepted slice now uses current-pass
spend accounting, not lifetime-cumulative inbox spend. Historical outcomes remain
audit history and do not consume a later scheduled heartbeat's fresh budget. True
crash-resumable heartbeat budgeting would require a pass id or separate ledger and
is intentionally left outside this slice.
