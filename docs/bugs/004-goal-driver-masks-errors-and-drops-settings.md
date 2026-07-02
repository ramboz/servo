---
status: DONE
tier: standard
severity: medium
claimed_by: claude/festive-payne-860961
regression_test: skills/agent-loop/test_loop.py::GoalDriverParityTests
main_repro_checked_at: 2026-07-02
main_repro_ref: origin/main@45d8dc0
main_repro_result: reproduces
red_confirmed_at: 2026-07-02
green_confirmed_at: 2026-07-02
fix_class: local_patch
security_surface: false
escalated_to:
---

# Bug 004: goal-driver-masks-errors-and-drops-settings

> Surfaced by the independent reviews of bugs 001 and 002 (both DONE). Those
> fixes were scoped to the loop driver (`_invoke_claude`); the goal driver
> (`_invoke_claude_goal` / `run_goal_loop`) retains a weaker form of both
> defects. This closes the parity gap.

## Symptom

Two loop-driver fixes did not carry to the goal driver (`--driver goal` / the
`auto`-routed goal path):

1. **Auth/API error masked (bug 001 twin).** When the `/goal` `claude -p` run
   returns a hard error envelope (`is_error: true`, e.g. `api_error_status:
   401`), `run_goal_loop` does not inspect `is_error`. The errored result event
   flows to the authoritative final `gate.py` run and is reported as
   `oracle_below_threshold` (with the unchanged oracle state) — misleading the
   operator, who never sees the real auth failure.
2. **Target settings not forwarded (bug 002 twin).** `_invoke_claude_goal`
   builds its own argv (`stream-json` + `--max-turns` + budget) and never calls
   `_settings_args(target)`, so a target that pre-authorizes its tools in a
   committed `.claude/settings.json` gets no `--settings` in a `/goal` run.

## Repro

1. (Auth) Run `loop.py <target> --driver goal --prompt "<edit task>"` where the
   spawned `claude -p` cannot authenticate. The `/goal` result event carries
   `is_error: true` / `api_error_status: 401`; observe the summary
   `terminal_reason: oracle_below_threshold` (not `claude_invocation_failed`).
2. (Settings) With a target declaring `.claude/settings.json`, inspect the goal
   `claude -p` argv — it contains no `--settings`.

## Evidence

Code inspection at HEAD (`skills/agent-loop/loop.py`):
- `_invoke_claude_goal` argv construction (~lines 2099-2105) has no
  `_settings_args(target)` call — cf. the loop driver's `_invoke_claude`
  (~line 1295) which was fixed in bug 002.
- `run_goal_loop` (~lines 2415-2460) extracts `subtype` and runs the gate, but
  never checks `result_event.get("is_error")` — cf. `_invoke_claude`
  (~line 1345) which was fixed in bug 001. Independent reviews of both bugs
  explicitly flagged this goal-driver residual.

## Hypotheses

- [x] **(leading)** The goal driver is a separate code path that was not
  updated when the loop driver received the 001/002 fixes: `_invoke_claude_goal`
  omits `_settings_args`, and `run_goal_loop`'s terminal-reason map has no
  `is_error` branch. *Confirm:* read both sites. *Falsify:* find an existing
  `_settings_args`/`is_error` check on the goal path.
- [ ] The goal path is intentionally exempt because the final authoritative
  `gate.py` run makes the masking harmless. *Confirm:* an auth failure yields a
  clear operator signal today. *Falsify:* it yields `oracle_below_threshold`,
  which hides the invocation failure (it does).

## Root cause

**Confirmed by code inspection.** The two loop-driver fixes (bugs 001/002) were
scoped to `_invoke_claude`; the goal driver is a distinct path
(`_invoke_claude_goal` builds a `stream-json` argv, `run_goal_loop` consumes the
result event). Neither the settings-forwarding helper nor the error-envelope
inspection exists there, so goal-mode runs (a) don't forward the target's own
permissions and (b) report a hard `/goal` invocation failure as a below-threshold
oracle result. Both are the same defects as 001/002, one code path over.

## Fix class

`local_patch` — two additive changes on the goal path in `loop.py`.

## Fix

1. **Settings parity (bug 002 twin).** `_invoke_claude_goal` extends its argv
   with `_settings_args(target)` (the same helper added for bug 002), forwarding
   ONLY the target's own committed `.claude/settings.json`; no bypass mode is
   injected, host managed policy still governs, and the flag is omitted when the
   target declares nothing.
2. **Envelope parity (bug 001 twin).** `run_goal_loop`, after extracting
   `subtype`, checks `result_event.get("is_error")`: if truthy AND `subtype` is
   not a legitimate cap (`error_max_turns` / `error_max_budget_usd`), it finalizes
   `claude_invocation_failed` (exit 2, `STATUS_ENV_ERROR`) with a breadcrumb
   naming `api_error_status` — before running the final gate. Caps and normal
   success (`is_error: false`) are unaffected.

## Already tried

n/a (new record; patterns proven on the loop driver in bugs 001/002).

## Regression test

`skills/agent-loop/test_loop.py::GoalDriverParityTests` — two tests:
`test_goal_forwards_target_settings` (target `.claude/settings.json` → goal argv
carries `--settings <that resolved path>`) and
`test_goal_auth_error_envelope_halts_invocation_failed` (a `/goal` result event
with `is_error: true` / `api_error_status: 401` → rc=2,
`claude_invocation_failed`, `401` in stderr — not `oracle_below_threshold`).

## Proof

Red→green witnessed by the teeth gate (`red_confirmed_at` / `green_confirmed_at`).
Both tests fail without the fixes (no `--settings` in goal argv; auth envelope →
`oracle_below_threshold` rc=0) and pass after. All goal-driver + routing +
background tests green (90 passed); full loop suite green; ruff clean.

## Learning

Fixing a defect in one of two parallel code paths (loop vs goal driver) leaves a
twin in the other. When a bug lives in a shared concept (the `claude -p`
invocation), sweep every invocation site: `_invoke_claude` AND
`_invoke_claude_goal`. Bugs 001/002 were correctly scoped to the reported repro,
but the independent review is what caught the goal-driver residual and closed the
loop. Same family as bugs 001/002: the `claude -p` result envelope and argv are
first-class surfaces, in both drivers. Together, bugs 001/002/004 are the
refuse-loudly half of
[spec 019-04](../specs/019-compile-core-simplification/slice-04-oracle-as-a-service-docs.md)
(ADR-0021); 019-04 verifies this closure and adds the oracle-as-a-service docs.

## Main recheck

- 2026-07-02 - `origin/main@45d8dc0` -> reproduces: origin/main@45d8dc0 goal driver: _invoke_claude_goal has no _settings_args in argv and run_goal_loop has no is_error branch (reports oracle_below_threshold on an auth error). New GoalDriverParityTests reproduces (RED).
