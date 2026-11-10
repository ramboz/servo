---
status: FIXING
tier: standard
severity: medium
claimed_by: claude/model-tiering
regression_test: skills/agent-loop/test_loop.py::ResumedSessionCostDeltaTests
main_repro_checked_at: 2026-11-10
main_repro_ref: origin/main@4cd95ca
main_repro_result: reproduces
red_confirmed_at: 2026-11-10
green_confirmed_at: 2026-11-10
fix_class: local_patch
security_surface: false
escalated_to:
closure_schema: 1
---

# Bug 007: agent-loop-overcounts-resumed-session-cost

> Surfaced while grounding [spec 038](../specs/038-per-node-model-tiering/spec.md)
> (per-iteration cost accounting). Fixed by slice 038-01, whose per-iteration
> `cost_usd` delta *is* the fix; this record carries the diagnosis.

> **Line references:** Symptom, Evidence, Root cause and the inventory cite
> pre-fix `origin/main@4cd95ca`. Call-site closure cites the post-fix tree
> (commit 44b72f5).

## Symptom

The loop driver's `cumulative_cost_usd` grows faster than real spend. Every
iteration after the first resumes the shared Claude session (`--resume
<current_session_id>`), and `loop.py` adds that invocation's reported
`total_cost_usd` to the running total (`skills/agent-loop/loop.py:2933`,
`:2953`). On a resumed session `claude -p` reports `total_cost_usd` as the
**session's** running total, not the invocation's own cost, so iteration *k*
re-adds the cost of iterations 1..*k*-1. Consequences:

- the `--cost-ceiling` brake (`cost_ceiling_reached`) fires early;
- the per-iteration `--max-budget-usd` (ceiling − cumulative) shrinks too fast;
- the summary's `cumulative_cost_usd`, and the heartbeat outcome
  `cost_usd` and whole-pass spend summed from it (`heartbeat.py`
  `_outcome_from_summary` / `_spent_cost_usd`), are inflated.

The direction is fail-safe (over-count), but every cost number the loop reports
for a multi-iteration run is wrong, which blocks spec 038's accounting.

## Repro

Probe against the real CLI (claude 2.1.321, 2026-11-10), in an empty dir:

```bash
claude -p --safe-mode --output-format json --model haiku --max-budget-usd 0.05 "Reply with exactly: OK" > p1.json
claude -p --safe-mode --output-format json --model haiku --resume "$(jq -r .session_id p1.json)" \
  --max-budget-usd 0.05 "Reply with exactly: OK2" > p5.json
```

## Evidence

| | `total_cost_usd` | `modelUsage[haiku]` tokens (in / cache-read / cache-create / out) | `usage` tokens (in / cache-read / cache-create / out) |
|---|---|---|---|
| p1 (fresh) | 0.0016728 | 2 / 24140 / 7146 / 4 | 2 / 24140 / 7146 / 4 |
| p5 (`--resume` p1) | 0.0028942 | 4 / 50725 / 11910 / 9 | 2 / 26585 / 4764 / 5 |

`modelUsage` on p5 is exactly p1 + p5's own `usage` (4 = 2+2, 50725 =
24140+26585, 11910 = 7146+4764, 9 = 4+5), and `modelUsage.costUSD` equals
`total_cost_usd`. So `total_cost_usd` and `modelUsage` are session-cumulative
on `--resume`, while top-level `usage` is per-invocation. The same session id
is returned (`session_id` unchanged), which is the loop driver's normal path.
Current code therefore sums 0.0016728 + 0.0028942 = 0.0045670 for a real
spend of 0.0028942.

A follow-up probe (spec 038 grounding) checked whether the per-invocation
`--max-budget-usd` is itself session-scoped. A two-turn resumed call under
`--max-budget-usd 0.0025` succeeded on a session whose running total was
already $0.0032, so the cap applies per invocation. Passing `ceiling −
corrected cumulative` is therefore correct.

`cumulative_input_tokens` / `cumulative_output_tokens` read top-level `usage`
(`loop.py:2939-2955`) and are correct. The goal driver issues one fresh
invocation (`loop.py:3599-3626`), so its `total_cost_usd` is that run's cost and
is correct.

## Hypotheses

- [ ] H1: `total_cost_usd` is per-invocation and p5 simply cost more (larger
  context). Falsified: `modelUsage` token counts on p5 equal p1 + p5 `usage`
  exactly, so the reported numbers are running totals.
- [x] H2 (leading): on `--resume`, Claude Code reports the session running
  total in `total_cost_usd` / `modelUsage`; `loop.py` treats it as the
  invocation's cost. Confirmed by the table above.

## Root cause

`run_loop` (`loop.py:2930-2955`) assumes `total_cost_usd` is the cost of the
invocation it just made. Since 003-04 the loop resumes one session across
iterations (`loop.py:2863-2865`, `:2956-2957`), and on a resumed session
the field is the session total, so the sum double-counts. Cost is read in
exactly three non-test places in `skills/` + `scripts/` (enumerated by
`grep -rn total_cost_usd skills scripts`, `.py` files, tests excluded; the
`hosts/` trees are generated copies): `loop.py:2933` (loop driver, affected),
`loop.py:3626` (goal driver, one fresh invocation, unaffected) and
`loop.py:2059` (Copilot normalization, hard-coded 0.0, unaffected).

## Repository closure inventory

**Equivalent / convergent logic searched:** `grep -rn "total_cost_usd" skills
scripts` (Python, tests excluded) gives the three sites above. The heartbeat
does not call Claude; it sums loop summaries' `cumulative_cost_usd`
(`heartbeat.py:2165`, `_outcome_cost_usd`) and is fixed transitively.

**Relevant history inspected:** `git log -S total_cost_usd -- skills/agent-loop/loop.py`:
003-01 (`ea6de43`) introduced the per-iteration read and 003-02 (`e4afaff`)
the cumulative sum, both before 003-04 added `--resume` session reuse. The
sum was written for one-shot invocations and never revisited.

**Affected call sites:** `run_loop` cost extraction (`loop.py:2930-2953`); the
per-iteration stdout `cost_usd` (`loop.py:3068`).

**Reuse decision:** no existing helper computes an invocation delta. Slice
038-01 adds one, `_iteration_cost_delta`, called only from `run_loop`. The goal
driver's single fresh invocation uses `_reported_total_cost` with
`cost_basis: "reported"`.

**Search scope:** `skills/` + `scripts/` Python, tests excluded.
`docs/decisions/adr-0008-experiments/analyze.py` also reads `total_cost_usd`.
It is an offline experiment analyser that never passes `--resume`, so it is
unaffected.

## Fix class

local_patch

## Fix

Slice 038-01 fixes this in `_iteration_cost_delta` (`skills/agent-loop/loop.py`).
The loop persists one dict in `state.json`,
`current_session_usage_snapshot = {session_id, total_cost_usd, model_usage}`:
the raw running totals Claude last reported for `current_session_id`. It is
replaced after every invocation that sets that id.

An iteration's cost is the delta `total_cost_usd − snapshot.total_cost_usd`
only when all of the following hold:
- the iteration passed `--resume S`;
- Claude returned the same `S`;
- `snapshot.session_id == S`;
- Σ `modelUsage` tokens ≥ the snapshot's Σ tokens + this invocation's `usage`
  tokens. This is ≥ rather than =, so advisor and subagent tokens that are
  absent from `usage` still pass;
- the reported cost did not go down (≥ the snapshot's).

In that case `model_usage` is the per-model, per-field difference from the
snapshot, floored at 0, with all-zero models dropped, and `cost_basis` is
`"session_delta"`. In every other case cost and `model_usage` are the
reported values with `cost_basis: "reported"`: over-count, never under-count.
`cumulative_cost_usd` sums the per-invocation costs.

## Call-site closure

**Disposition per affected site:**
- `run_loop` cost extraction — **changed**: cost comes from
  `_iteration_cost_delta` (`skills/agent-loop/loop.py:1867`); `cumulative_cost_usd`
  sums the per-invocation costs (`:3151`); the session snapshot is refreshed
  with `current_session_id` (`:3157`). Tested by `ResumedSessionCostDeltaTests`,
  `ResumedSessionFailSafeTests`, `SnapshotResumeTests`, `OldStateResumeTests`.
- Per-iteration stdout `cost_usd` — **changed** (now the invocation's own cost);
  tested in `ResumedSessionCostDeltaTests`.
- Goal driver result-cost read — **left alone**: one fresh invocation, so
  `total_cost_usd` is already its own cost (`cost_basis: "reported"`).
- Copilot normalization (hard-coded 0.0) — **left alone**: no USD cost exists
  (ADR-0043); the fallback breadcrumb is suppressed off the Claude host.
- Heartbeat `_outcome_from_summary` / `_spent_cost_usd` — **left alone**: they
  read the loop summary's `cumulative_cost_usd`, which is now correct.

## Already tried

None.

## Regression test

`skills/agent-loop/test_loop.py::ResumedSessionCostDeltaTests` — a mock `claude`
that keeps per-session running totals across `--resume` (the real semantics in
the Evidence table) asserts each resumed iteration costs the delta, the state
cumulative equals the sum of per-iteration costs, and the iteration-3
`--max-budget-usd` uses the corrected cumulative.

## Proof

- Red (2026-11-10): before the slice 038-01 implementation, 22 of its first 25
  new tests failed, including all of `ResumedSessionCostDeltaTests`. The bug.py
  FIXING gate independently re-ran `ResumedSessionCostDeltaTests` against the
  pre-fix `loop.py` and confirmed RED.
- Green (2026-11-10): `python3.13 scripts/run_tests.py` 2567 passed / 10
  skipped; 3.9.6 run green except two `test_gate_output_readback.py [forged]`
  cases that fail identically on an `origin/main` baseline (macOS bytecode-cache
  path; unrelated).
- Mutation: disabling the delta proof turns 4/6 `ResumedSessionCostDeltaTests`
  red; deleting the returned-id conjunct turns
  `test_returned_session_id_must_match_resumed_id` red.

## Learning

On `claude -p --resume`, `total_cost_usd` and `modelUsage` are session running
totals while top-level `usage` is per invocation. Any consumer that sums
`total_cost_usd` across resumed calls over-counts; compute a delta against the
last reported total for the same session, and fall back to the reported value
(over-count, never under-count) when the running-total identity
`Σ modelUsage_now ≥ Σ modelUsage_prev + Σ usage` (≥, so advisor and subagent tokens
missing from `usage` still pass), with a non-decreasing cost, does not hold.

## Main recheck

- 2026-11-10 - `origin/main@4cd95ca` -> reproduces: origin/main loop.py still sums the session-cumulative total_cost_usd per resumed iteration (cost_usd = float(total_cost_usd) at :2933, cumulative += cost_usd at :2953); live probe p1/p5 (claude 2.1.321) shows total_cost_usd is a session running total on --resume
