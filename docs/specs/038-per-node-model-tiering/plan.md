# Spec 038 — implementation plan

Guidance for implementers. The ACs in the slice files are authoritative; this
file only fixes names and hook points so the three slices compose.

## 038-01 — accounting (`skills/agent-loop/loop.py`)

- **New pure helpers** (unit-testable, no I/O):
  - `_normalize_model_usage(claude_data) -> dict`: `modelUsage` mapped to
    `{id: {cost_usd, input_tokens, output_tokens, cache_read_input_tokens,
    cache_creation_input_tokens}}`. Non-dict → `{}`; non-numeric → 0
    (`bool` is not numeric).
  - `_advisor_model_ids(claude_data) -> set[str]`: the models of
    `usage.iterations[]` elements whose `type == "advisor_message"`.
  - `_iteration_cost_delta(claude_data, *, resumed_session_id, snapshot)
    -> tuple[float, dict, str]`: returns `(cost_usd, per_model_usage,
    cost_basis)` applying spec 038-01 AC3 (running-total proof gives
    `"session_delta"`, otherwise the reported values with `"reported"`).
  - `_iteration_accounting(claude_data, *, agent, cost_usd, model_usage,
    requested) -> dict`: builds the record keys `agent, session_id, cost_usd,
    usage, model_usage, model, requested` (AC1/AC2). The goal driver omits
    `agent` and `cost_usd`, because its cost is already `cumulative_cost_usd`.
- **State keys** (additive, ADR-0004): `current_session_usage_snapshot =
  {"session_id", "total_cost_usd", "model_usage"}` holds the raw running totals
  last reported for `current_session_id`. Old state without it gives no
  snapshot.
- **run_loop hook**: replace the `cost_usd = float(total_cost_usd)` block
  (`loop.py:2930-2953`) with the delta helper. Add the record keys to the
  history append (`:3049`) and the per-iteration `_emit_json` (`:3064`), and
  refresh the snapshot where `current_session_id` is set (`:2956`).
- **Goal driver**: after `result_event` is parsed (`:3672` onward), store the
  record keys on `state` and in the summary on every post-invocation
  `_finalize` path. `_finalize` already persists `state`, so add the keys to
  `state` once and have `_goal_summary` / `_finalize` copy them when present.
- **Tests** (`skills/agent-loop/test_loop.py`, new classes):
  - a mock `claude` that keeps a per-session running total across `--resume`
    calls: for each invocation, emit `usage` = this call and `modelUsage` /
    `total_cost_usd` = the running total;
  - a mock that emits an `advisor_message` iteration plus a second model;
  - unit tests of the pure helpers by importing `loop.py` via `importlib`
    (as the existing unit-style tests do).
- **Bug 007**: once green, record the regression test class on the bug and
  advance it through `bug.py`.

## 038-02 — role placement

- **Constants**: `MODELS_ROLES = ("runner", "judge")`, `MODELS_ROLE_KEYS =
  ("model", "effort", "advisor")`, `EFFORT_LEVELS = ("low", "medium", "high",
  "xhigh", "max")`, `REASON_MODELS_INVALID = "models_invalid"`.
- **Validator**: `_validate_models(block, *, allow_escalation) -> (normalized |
  None, error_msg | None)`. Normalized form: `{"runner": {...}, "judge": {...}}`
  with inherited fields dropped. One function serves both callers; the caller
  picks the reason code.
- **Loader**: `_load_models_arg(value) -> (block | None, error)`. Inline JSON when
  `value.lstrip().startswith("{")`, otherwise a file path.
- **argv**: `_role_args(role_cfg) -> list[str]` emits flags in the fixed order
  `--model`, `--effort`, `--advisor`. Pass the result into `_invoke_claude`
  and `_invoke_claude_goal` as `role_args`, inserted before `--settings`.
  An empty list keeps argv identical.
- **Session**: in run_loop, `split = bool(resolved models block)`, meaning
  any field set. For a judge in split mode, pass `session_id=None` and skip the
  `current_session_id` / snapshot update; the delta helper gets
  `resumed_session_id=None`, so cost = total (`cost_basis: "reported"`).
  Runners always resume `current_session_id` when it is set.
- **Advisor second signal**: `_mark_requested_advisor(model_usage, advisor,
  model)` flags ids equal to the requested advisor, or containing it as a
  `-`-delimited token, unless the id also matches the requested model.
- **main()**: resolve `--models` (argparse, default None) > plan `models`;
  validate before routing; thread the result into `run_loop` /
  `run_goal_loop` / `run_goal_loop_background`. The background child argv
  gets `--models <compact json>`.
- **Planner**: `_budget_hash(budget, driver, models=None)` hashes
  `{"budget", "driver"}` exactly as today when `models` is None, and
  `{"budget", "driver", "models"}` otherwise. `write_plan` passes
  `existing.get("models")`.

## 038-03 — ladder

- `_validate_models(..., allow_escalation=True)` accepts `escalation` (a list
  of non-empty role-key objects).
- `_runner_config_at_rung(models, rung)` folds the base runner config with
  rungs 1..rung.
- State keys: `escalation_rung`, `escalation_events`,
  `escalation_baseline_composite`, `escalation_history_start` (the index of
  the rung's first runner entry; `None` until that entry is appended).
- Plateau check:
  `_check_plateau(([{"composite": baseline}] if baseline is not None else [])
  + history[start:], window, noise_floor)`. At rung 0, start = 0 and there is
  no baseline, which matches today. Before the rung's first runner entry
  exists, the check is skipped.
- Fair-window guard: `needed = window + (1 if _agent_for_iteration(i + 1) ==
  AGENT_JUDGE else 0)`. Escalate iff `max_iterations − i ≥ needed`.
- Escalation resets `current_session_id = ""` and the cost snapshot.
- Heartbeat quarantine predicate: `terminal_reason == oracle_plateau`, or
  (`escalation_rung ≥ 1` and not passed and `terminal_reason in
  {max_iterations_reached, cost_ceiling_reached, context_full}`).
- Heartbeat: add `--models` to `run` / `dispatch`, thread it into `_run_loop`
  argv, check it up front with `json.loads` (or a readable file),
  pass-through in `_outcome_from_summary`, and handle `models_invalid` in
  `_dispatch_one` as `(None, reason)`.
- ADR-0010: append a dated `## Amendments` entry pointing to ADR-0047.

## Cross-cutting

- Regenerate host packages after every source change:
  `python3 scripts/build_host_packages.py`. CI runs `--check`.
- Local CI mirror: `python3 scripts/ci_check.py`. It needs `pipx` for ruff;
  otherwise run `uvx ruff@0.15.17 check .`. Run the suite under both
  `/usr/bin/python3` (3.9 floor) and `python3.13`.
