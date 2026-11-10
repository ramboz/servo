---
bug: 007
pass: bug-review
verdict: pass
reviewer: jig:reviewer
reviewed_at: 2026-11-10T20:30:57Z
prompt_source: review.py bug-review docs/bugs/007-agent-loop-overcounts-resumed-session-cost.md skills/agent-loop/loop.py skills/agent-loop/test_loop.py
---

VERDICT: pass

REASONING:
The fix targets the documented root cause: _iteration_cost_delta subtracts the session snapshot only when the four-conjunct proof holds, else reports the raw total (over-count only); run_loop sums the deltas and refreshes the per-session snapshot. The regression test's mock reproduces the evidenced running-total semantics, and ResumedSessionCostDeltaTests is red pre-fix (0.1/0.3/0.6 cumulative) and green post-fix. Blast radius covered (heartbeat reads only cumulative_cost_usd; only one --resume call site); pre-038 and snapshot-carrying resumes tested.

SPECIFIC ISSUES:
- Reuse-decision sentence claimed both drivers use the helper (fixed: run_loop only).
- Line refs mixed pre-/post-fix baselines (fixed: labelled).
- Optional hardening: an empty snapshot model_usage makes the token check vacuous (cost check remains) — recorded as a residual in 038-01's deviation log.

RECONCILIATION NOTES:
- --max-budget-usd per-invocation scope is probe-verified (now cited in Evidence).
- adr-0008-experiments/analyze.py also reads total_cost_usd; never resumes; scope note added.
