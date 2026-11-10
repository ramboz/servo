---
status: DRAFT
skill: agent-loop
use_cases: []
---

# Spec 038: Per-node model tiering

## Overview

servo runs one agent node at a time: the loop driver alternates a `runner`
(edits) and a `judge` (read-only) through `claude -p`, and the goal driver
issues one `/goal` invocation. Today every node inherits whatever model and
effort the host session defaults to. Nothing records which model ran or what
each iteration cost, so no tiering decision can be measured. A plateau ends the
run, and the heartbeat then quarantines the finding after a single attempt.

This spec gives servo **per-node model discipline**. servo records what each
node cost. It lets a plan place each role on a model, effort and advisor. When
a run plateaus, it escalates through configured rungs before giving up. Three
slices, in dependency order:

1. **038-01 accounting.** Each scored iteration records its model usage,
   requested effort, cost delta and token usage in `state.json` (both drivers).
   This also fixes [bug 007](../../bugs/007-agent-loop-overcounts-resumed-session-cost.md),
   which over-counts resumed-session cost.
2. **038-02 role placement.** An optional `models` block (plan.json or
   `--models`) sets `--model` / `--effort` / `--advisor` per role. When the
   runner and judge models differ, the judge runs in its own fresh session.
3. **038-03 escalation ladder.** A plateau climbs configured rungs (raise
   effort, then raise model) inside the same run before the loop reports
   `oracle_plateau`. The heartbeat records the rung reached.

The design decision behind slices 02-03 (role placement, the session split, and
where the ladder lives) is [ADR-0047](../../decisions/adr-0047-per-node-model-tiering-and-escalation-ladder.md).
Research input: jig research note R-003 "advisor-style model tiering"
(servo deep-dive section). It is not a dependency, and servo never reads jig.

### Grounded starting point (origin/main `455ac42`, verified 2026-11-10)

- **Score history** is appended only after a gate scoring, with
  `iteration/composite/threshold/status` plus `gate_consumer.fields`
  (`skills/agent-loop/loop.py:3049-3055`). The goal driver keeps no history: it
  is one invocation (`loop.py:3599-3626`) whose state has
  `cumulative_cost_usd` and `num_turns` only (`_build_goal_state`,
  `loop.py:3338-3370`).
- **Loop-driver argv**: `claude -p --output-format json --max-budget-usd <b>
  [--settings <f>] [--agent <runner|judge>] [--resume <sid>] <prompt>`
  (`_invoke_claude`, `loop.py:2204-2211`). One session is shared by runner
  *and* judge: `current_session_id` is resumed by every iteration and
  overwritten by every iteration's result (`loop.py:2863-2865`, `:2956-2957`).
- **Goal-driver argv**: `claude -p --output-format stream-json --verbose
  --max-turns <n> [--max-budget-usd <c>] [--settings <f>] <prompt>`
  (`_invoke_claude_goal`, `loop.py:3285-3295`).
- **Plan consumption** reads `budget` + `driver` only (`_load_plan`
  `loop.py:1316-1373`; main() `loop.py:4416-4482`). Unknown plan keys are
  ignored, not refused. The planner's recompile-preserve hash covers
  `budget` + `driver` only (`execution_plan.py:293-303`, `:384-401`).
- **Plateau**: `_check_plateau` (`loop.py:617-650`) needs `window+1` numeric
  composites. A hit sets `terminal_reason=oracle_plateau` and breaks
  (`loop.py:3109-3115`).
- **Heartbeat**: `_run_loop` forwards only `--cost-ceiling` /
  `--max-iterations` (`heartbeat.py:2080-2119`). `run_dispatch` quarantines a
  finding whose loop summary says `oracle_plateau` and otherwise marks it
  `passed`/`tried`, with `attempts += 1` (`heartbeat.py:2706-2732`). The
  outcome shape passes optional loop diagnostics through
  (`_outcome_from_summary`, `heartbeat.py:2149-2192`). ADR-0010 grants one
  dispatch per finding (`adr-0010…:105`, `:149`).
- **Copilot**: `run_loop` refuses `--host copilot` before any work
  (`loop.py:2527-2528`, ADR-0043). Copilot agent renders stay model-neutral
  by a source-side raise on a `model:` field (spec 032-03). This spec adds no
  `model:` to `agents/*.md`; model placement lives only in the launcher argv.
- **CLI probes** (claude 2.1.321, `--safe-mode`, total spend ≈ $0.21):
  - `--model`, `--effort low|medium|high|xhigh|max`, and a `--help`-hidden
    `--advisor` are all accepted.
  - The `-p` JSON never reports effort.
  - With `--model sonnet --advisor opus`, `modelUsage` carries both
    `claude-sonnet-5-5` and `claude-opus-5-5` with separate `costUSD`; the
    advisor's read was uncached (33,438 input, 0 cache-read). `usage.iterations`
    lists the consult as `{"type": "advisor_message", "model": "claude-opus-5-5"}`.
  - `--advisor` reaches an `--agent` whose `tools:` is `[Read, Glob, Grep]`.
  - Changing `--effort` on `--resume` keeps the same session id and its cache.
  - On `--resume`, `total_cost_usd` and `modelUsage` are session running
    totals, while `usage` is per-invocation (bug 007).
  - The stream-json `result` event carries the same
    `total_cost_usd`/`usage`/`modelUsage` fields.

### Product boundary (unchanged by this spec)

- **Serial, one node at a time.** No fan-out, no crew, no parallel rungs.
  Escalation is sequential within one run.
- **The oracle is the authority.** Model choice changes who works, never who
  decides. `gate.py` still scores every iteration, and a rung never relaxes the
  threshold, the required gate or any brake.
- **Never loosen a brake.** Rungs share the run's existing `max_iterations` and
  `cost_ceiling`. No rung grants extra iterations or spend
  (ADR-0016 clamp-never-loosen; spec 017 "spend smarter, never more").
- **servo never merges and the runner does no git operations.** Unchanged.
- **The loop stays trigger-agnostic.** All behaviour is configured through
  plan/flags that any trigger (human, heartbeat, a host campaign) can pass.
  servo never depends on jig internals.
- **Default is today.** With no `models` configuration the argv, session
  handling and halt behaviour are unchanged. The one deliberate exception is
  bug 007's cost fix: reported cost becomes accurate, so on multi-iteration
  runs `cost_ceiling_reached` now fires later than before.

## Assumptions

- **A1: the subset of `modelUsage` that is a subagent's model is not
  identified.** 038-01's `model` field picks the non-advisor `modelUsage`
  entry with the highest `costUSD`. If a runner spawns subagents on another
  model, the per-model breakdown stays exact but `model` may name the subagent
  model. Not probed. The breakdown (`model_usage`) is the authoritative record.
- **A2: Anthropic's "re-run failures at higher effort" figure (equal pass rate
  at "a little over half the cost") is vendor-reported**, on Anthropic's
  benchmark, not servo's. 038-03 makes the ladder measurable (rung reached +
  per-iteration cost) rather than assuming the saving.
- **A3: the advisor pairing rule** (advisor must rank ≥ the main model; Anthropic
  API only) is enforced by Claude Code, not servo. A disallowed pairing surfaces
  as an invocation failure (`claude_invocation_failed`). servo does not pre-validate
  model ranks. Documented, not probed beyond the two allowed pairings above.

## Decomposition (SPIDR)

- **Data** splits the work first: 038-01 records what exists today (no config),
  038-02 adds the configuration input, and 038-03 adds the rule that changes
  configuration mid-run. Each slice is observable on the loop's own
  stdout/state, the user-facing surface of a headless driver.
- **Rules** keep 038-03 separate from 038-02. Static placement is a plain
  input; escalation is a policy with a decision record (ADR-0047) and a
  heartbeat-contract change (ADR-0010 amendment).
- **Interface** was considered for the heartbeat (`--models` passthrough). It is
  folded into 038-03, because the ladder is the first behaviour a heartbeat
  user needs it for.
- No Spike: every unknown above was settled by a probe.

## Slices

- [038-01 — per-iteration accounting](slice-01-per-iteration-accounting.md)
- [038-02 — role model placement](slice-02-role-model-placement.md)
- [038-03 — plateau escalation ladder](slice-03-plateau-escalation-ladder.md)

## Follow-ups (separate specs, drafted after 038 lands)

- **039 variance-gated eval judging.** A cheap judge first, with a frontier
  re-judge only on high-spread samples (`skills/_common/fidelity_eval.py`
  aggregation; `DEFAULT_JUDGE` in `skills/eval-authoring/eval_authoring.py`).
- **040 servo-wrapped worker outcome line** for host-orchestrated campaigns:
  one typed line (passed / plateau@rung / blocked + cost), with no crew and a
  trigger-agnostic loop.
- **041 host-aware budget unit** (USD vs Copilot premium requests × multiplier).
  Low priority while Copilot unattended stays refused (ADR-0043).
