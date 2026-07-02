---
status: REPORTED
tier:
severity:
claimed_by: main
regression_test:
main_repro_checked_at:
main_repro_ref:
main_repro_result:
red_confirmed_at:
green_confirmed_at:
fix_class:
security_surface: false
escalated_to:
---

# Bug 001: agent-loop-masks-auth-error-as-plateau

> Reported from an external dogfood run (cwv-workbench spec 015, 2026-07-01).

## Symptom

When the spawned `claude -p` returns an **authentication/API error**
(`is_error: true`, `api_error_status: 401`, `total_cost_usd: 0`, empty
`modelUsage`), `loop.py` records the iteration as `terminal_reason: "completed"`
with `oracle_composite: 0.0` and keeps iterating until it halts on
`oracle_plateau`. A hard auth failure is reported as "the model isn't
improving," not as an invocation failure — the operator never sees the real cause.

## Repro

In an environment where `claude -p` cannot authenticate (e.g. a gateway
`ANTHROPIC_BASE_URL` whose credential is not inherited by the subprocess), run
`loop.py <target> --driver loop --prompt "<any edit task>"`. Observe per-iteration
`cost_usd: 0`, `verdict: null`, `context_fill_ratio: null` (stderr: "context-fill
gate: claude JSON missing `modelUsage` block"), the oracle stuck at 0.0, and a
final `terminal_reason: oracle_plateau` — with **zero files changed**.

## Evidence

Run `20260701T233608-422c`: 4 iterations, all `cost_usd: 0`, `verdict: null`,
plateau halt. The raw `claude -p --output-format json` result for each carried
`is_error: true, api_error_status: 401, result: "Failed to authenticate. API
Error: 401 Invalid authentication credentials"`. `loop.py` scored it as a normal
below-threshold iteration.

## Hypotheses

1. **(leading)** `loop.py` inspects only the parsed oracle score + the agent
   `verdict` block, and never checks the `claude -p` **result envelope**
   (`is_error`, `api_error_status`, `subtype`). An errored invocation is scored
   as a real iteration.
2. A `cost_usd: 0` + missing-`modelUsage` iteration is inherently non-productive
   and should be treated as a failed invocation, not a scored one.

## Root cause

_Not yet diagnosed (REPORTED). See hypotheses._

## Fix class

_TBD (likely `local_patch` in loop.py's result-handling)._

## Fix

**Direction (not yet implemented):** detect `is_error: true` (or an
`api_error_status`, or an error `subtype`) in the `claude -p` result and halt
with `terminal_reason: claude_invocation_failed` (exit 2, per the loop's closed
exit contract) instead of scoring it and plateauing. A run of cost-0 /
empty-`modelUsage` iterations is a strong secondary signal of a broken
invocation, not a plateau.

## Already tried

n/a (reported, not yet worked).

## Regression test

_TBD — a stub `claude -p` returning an `is_error:true`/401 envelope should drive
`loop.py` to `claude_invocation_failed`, not `oracle_plateau`._

## Proof

_TBD._

## Learning

Servo's headless loop shells out to `claude -p`; the result envelope is a
first-class failure surface, distinct from the oracle score. Related: Bug 002
(the same run later failed on edit permissions once auth was fixed).
