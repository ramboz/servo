---
status: ROOT_CAUSED
tier: standard
severity: medium
claimed_by: claude/model-tiering
regression_test:
main_repro_checked_at: 2026-11-10
main_repro_ref: origin/main@4cd95ca
main_repro_result: reproduces
red_confirmed_at:
green_confirmed_at:
fix_class: local_patch
security_surface: false
escalated_to:
closure_schema: 1
---

# Bug 007: agent-loop-overcounts-resumed-session-cost

> Surfaced while grounding [spec 038](../specs/038-per-node-model-tiering/spec.md)
> (per-iteration cost accounting). Fixed by slice 038-01, whose per-iteration
> `cost_usd` delta *is* the fix; this record carries the diagnosis.

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
038-01 adds one, `_iteration_cost_delta`, used by both drivers' accounting.

## Fix class

local_patch

## Fix

Slice 038-01. The loop keeps `current_session_cost_usd` and
`current_session_tokens` (the session running totals last reported for
`current_session_id`). When an invocation resumed that session and returned
the same id, and `modelUsage`'s token total is at least the stored total plus
this invocation's `usage` tokens (positive evidence of running-total
semantics), the iteration's cost is `total_cost_usd − current_session_cost_usd`.
Otherwise it is `total_cost_usd`. The unproven case therefore over-counts
(fail-safe) rather than under-counts. `cumulative_cost_usd` sums these deltas.

## Call-site closure

**Disposition per affected site:** filled at FIXING.

## Already tried

None.

## Regression test

Filled at FIXING (slice 038-01 test class).

## Proof

## Learning

## Main recheck

- 2026-11-10 - `origin/main@4cd95ca` -> reproduces: origin/main loop.py still sums the session-cumulative total_cost_usd per resumed iteration (cost_usd = float(total_cost_usd) at :2933, cumulative += cost_usd at :2953); live probe p1/p5 (claude 2.1.321) shows total_cost_usd is a session running total on --resume
