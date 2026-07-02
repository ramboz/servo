---
status: DONE
tier: standard
severity: high
claimed_by: main
regression_test: skills/agent-loop/test_loop.py::ClaudeErrorEnvelopeTests
main_repro_checked_at: 2026-07-02
main_repro_ref: origin/main@45d8dc0
main_repro_result: reproduces
red_confirmed_at: 2026-07-02
green_confirmed_at: 2026-07-02
fix_class: local_patch
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

- [x] **(leading)** `loop.py` inspects only the parsed oracle score + the agent
  `verdict` block, and never checks the `claude -p` **result envelope**
  (`is_error`, `api_error_status`, `subtype`). An errored invocation is scored
  as a real iteration. *Confirm:* read `_invoke_claude`'s return path. *Falsify:*
  find an existing error-envelope check.
- [ ] A `cost_usd: 0` + missing-`modelUsage` iteration is inherently
  non-productive and should be treated as a failed invocation, not a scored one.
  *Confirm:* correlates with the error envelope. *Falsify:* a legitimate
  zero-cost iteration exists (it does not — every real iteration has usage).

## Root cause

**Confirmed by code inspection** (`skills/agent-loop/loop.py:1320-1324`).
`_invoke_claude` returns **any parseable JSON dict as success** —
`if data is not None: return data, None` — regardless of the envelope's
`is_error` / `api_error_status` / `subtype`. The `claude_invocation_failed`
path (loop.py:1780-1787, exit 2) fires *only* when the JSON is unparseable or
the process exits non-zero **without** JSON. A hard auth/API error
(`is_error: true, api_error_status: 401`) is still valid JSON, so it is scored
as a normal below-threshold iteration and the loop plateaus (or, with plateau
disabled, exhausts `max_iterations`) instead of surfacing the invocation
failure. The budget/turn halts (`error_max_budget_usd` / `error_max_turns`)
are the *only* legitimate `is_error: true` envelopes in loop mode and must stay
scored (the per-iteration `--max-budget-usd` floor documented at
loop.py:1254-1261).

## Fix class

`local_patch` — `_invoke_claude`'s result-handling in `loop.py`.

## Fix

`_invoke_claude` (`skills/agent-loop/loop.py`) now inspects the parsed envelope
before returning it as a scored iteration: if `is_error` is truthy **and** the
`subtype` is not one of the legitimate budget/turn halts
(`error_max_budget_usd` / `error_max_turns`), it returns `(None, breadcrumb)`
— which the loop already maps to `terminal_reason: claude_invocation_failed`
(exit 2). The breadcrumb names `api_error_status` and the first line of
`result`, so the operator sees the real cause (e.g. `api_error_status=401`)
instead of a plateau. The two budget/turn subtypes stay scored because they
carry real partial work (the per-iteration `--max-budget-usd` floor).

## Already tried

n/a (reported, not yet worked).

## Regression test

`skills/agent-loop/test_loop.py::ClaudeErrorEnvelopeTests` — two tests:
`test_auth_error_envelope_halts_invocation_failed` (is_error/401 exit-0 JSON →
rc=2, `claude_invocation_failed`, `401` in stderr) and
`test_budget_halt_envelope_is_still_scored` (is_error + `error_max_budget_usd`
→ still scored, runs to `max_iterations_reached`), guarding the fix boundary.

## Proof

Red→green witnessed by the teeth gate (`red_confirmed_at` / `green_confirmed_at`
in frontmatter). Full loop suite green after the fix (255 passed); ruff clean.

## Learning

Servo's headless loop shells out to `claude -p`; the result envelope is a
first-class failure surface, distinct from the oracle score. Related: Bug 002
(the same run later failed on edit permissions once auth was fixed).

## Main recheck

- 2026-07-02 - `origin/main@45d8dc0` -> reproduces: HEAD==origin/main==45d8dc0; _invoke_claude (loop.py:1320-1324) returns any parseable JSON dict as success, so an is_error/401 envelope is scored not failed. New ClaudeErrorEnvelopeTests reproduces (RED) against this code.
