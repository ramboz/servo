---
status: Proposed
dependencies: [adr-0004, adr-0010, adr-0016, adr-0030]
last_verified:
frame_review: true
---

# ADR-0047: Per-node model tiering and the plateau escalation ladder

## Status

Proposed (2026-11-10)

## Context

servo's loop runs one node at a time: a `runner` that edits and a read-only
`judge`, alternating through `claude -p`, scored by `gate.py` after every
iteration. Every node inherits the host session's model and effort. No servo
agent pins a model, neither driver passes `--model` or `--effort`, and
`plan.json` (ADR-0016) carries `budget` + `driver` only. When a run stops
improving, the loop halts with `oracle_plateau`. The heartbeat then parks the
finding as `quarantined` (ADR-0030) after the single dispatch ADR-0010 allows.

Three forces push on this:

1. **Cost and capability are per node, not per session.** A runner doing
   routine edits does not need the frontier model. A stuck runner might need
   more capability, or just more effort. Anthropic's published guidance is
   that re-running failures at higher effort held the high-effort pass rate for
   "a little over half the cost". That is vendor-measured on its own benchmark,
   so it is a hypothesis to measure here, not a fact about servo. Claude Code
   now offers an advisor (`--advisor`): a stronger model the executor consults
   at decision points. Its read is uncached, which servo probed: 33,438 input
   tokens, 0 cache-read.
2. **A multi-session campaign run showed the failure mode.** Workers without
   per-node discipline ran away (one fixer: 1,383 calls, 59 compactions,
   ~23 h). The campaign tree belongs to the host (spawn, message, persist), and
   servo's boundary forbids a crew or fan-out. Per-node budget, plateau handling
   and escalation are servo's lane.
3. **The judge resumes the runner's session.** `current_session_id` is shared:
   every iteration passes `--resume` and overwrites it
   (`skills/agent-loop/loop.py:2863-2865`, `:2956-2957`). Putting the judge on
   a different model than the runner inside that one session means a model
   switch every iteration. Prompt caches are model-scoped, so each switch
   cold-starts the cache, and thinking blocks do not carry across models.

Spec 038 slice 01 adds the measurement substrate: per-iteration model usage,
requested effort, cost delta and tokens. This ADR decides the placement and
escalation policy built on it.

## Decision Options Considered

### D1: where role placement is configured

- **Option A (chosen): a `models` block in `plan.json`, plus a `--models`
  flag carrying the same block.**
  - **Pros:** it is per run and reviewable like the rest of the plan; one
    schema and one validator serve both sources; the heartbeat, which
    has no plan (ADR-0018), can pass it through; it stays inside the
    launcher argv.
  - **Cons:** a JSON value on the command line is clunkier than a scalar
    flag, which is why a file path is also accepted.
- **Option B: `model:`/`effort:` frontmatter in `agents/runner.md` /
  `judge.md`.**
  - **Pros:** the host-native mechanism.
  - **Cons:** global to every run; breaks Copilot model-neutrality (spec
    032-03 raises on a `model:` field); cannot vary per rung. Rejected.
- **Option C: six per-role scalar flags (`--runner-model`, …).**
  - **Pros:** ergonomic for one-off runs.
  - **Cons:** flag sprawl; a second shape to keep in sync with the plan
    block; the escalation list does not fit scalars. Rejected.
- **Option D: environment (`CLAUDE_CODE_SUBAGENT_MODEL`).**
  - **Cons:** it governs subagents, not the `--agent` main thread servo
    runs; it is process-global; it can't vary per role. Rejected.

### D2: when the judge gets its own session

- **Option A (chosen): split iff the resolved runner and judge models
  differ.** The judge then runs in a fresh session every judge iteration,
  never resumes or overwrites the runner's session, and relies on its
  self-contained prompt (seed + last oracle JSON + last runner verdict, per
  `agents/judge.md`). Same models keep today's shared session.
  - **Pros:** the default is unchanged; it avoids per-iteration model
    switches; it strengthens judge independence exactly when tiering is
    in play.
  - **Cons:** a split judge cannot read the runner's transcript, by
    design. It re-reads `files_changed` cold each time.
- **Option B: always split.**
  - **Pros:** uniform independence.
  - **Cons:** changes default behaviour and cost for every existing run,
    with no measurement yet. Rejected for now; 038-01's accounting can
    justify it later.
- **Option C: never split.**
  - **Cons:** a tiered judge forces a model switch inside the shared session
    every iteration. Rejected.

A runner invocation whose configured model differs from the model its current
session started under also starts fresh. That covers a resumed run whose
configuration changed, and D3's model-raising rungs.

### D3: where the escalation ladder lives

- **Option A (chosen): inside `loop.py`, within one run.** `models.escalation`
  is an ordered, cumulative list of runner overrides. When the plateau check
  fires and a rung remains, the run escalates and continues in the same
  worktree under the same budget. The plateau window restarts from a baseline
  equal to the best composite so far. `oracle_plateau` is emitted only when the
  last rung plateaus.
  - **Pros:** node-owned and trigger-agnostic, so a human run, a heartbeat
    dispatch and a host-campaign worker all get it; partial progress in the
    worktree is kept; one budget bounds all rungs; the heartbeat's quarantine
    trigger is unchanged.
  - **Cons:** rungs compete for the run's `max_iterations`. Under the
    defaults (5 iterations, window 3) the first plateau fires at iteration
    4, so the ladder is usable only with a larger iteration cap.
- **Option B: the heartbeat re-dispatches a plateaued finding at the next
  rung, on a later tick.**
  - **Pros:** each rung is a clean fresh start, the literal "re-run the
    failure" pattern.
  - **Cons:**
    - It discards the worktree (`_dispatch_one` recreates it at `HEAD`).
    - It multiplies per-dispatch budgets across ticks.
    - It needs cross-tick rung state in the inbox.
    - It reopens quarantine semantics (ADR-0030).
    - It only works under the heartbeat, not for direct or host-campaign
      runs.

    Rejected.
- **Option C: spec 017-d "adaptive planning", which rewrites `plan.json` from
  convergence signals.**
  - **Cons:** rewriting a reviewed, possibly `human_edited` artifact mid-run
    raises a re-approval question (017 open question). A ladder declared up
    front in the plan needs no rewrite. Rejected for this need. This ADR
    supersedes the "switch model/effort" part of 017-d's sketch; plan
    rewriting itself stays parked.

### D4: what a rung may change

The runner's `model` / `effort` / `advisor` only. A rung never changes the
judge, the threshold, the required gate, the driver or any brake. It never
grants iterations or spend (ADR-0016 clamp-never-loosen).

## Recommended Decision

Adopt D1-A, D2-A, D3-A and D4. Concretely:

- `plan.json` gains an optional top-level `models` block (plan
  `schema_version` stays 1; the block is additive and absent by default).
  `loop.py --models <json|path>` carries the same block with block-level
  precedence over the plan. The block is validated fail-closed and persisted
  in `state.json` (ADR-0004 additive).
- Role fields become `--model` / `--effort` / `--advisor` on that role's
  `claude -p` argv. `inherit` or absent adds no flag, so with no block the argv
  is byte-identical to before.
- Session split per D2-A.
- The ladder per D3-A, recorded as `rung` per iteration,
  `escalation_rung`/`escalation_events` in state, and
  `escalation_rung`/`escalation_rungs` on the summary and heartbeat outcome.
- The heartbeat forwards `--models` to `loop.py`.
- **ADR-0010 amendment:** "one dispatch attempt per finding" still holds, but
  one dispatch may span the configured rungs. `attempts` still counts
  dispatches; `outcome.escalation_rung` records how far the dispatch climbed.
  ADR-0030's trigger (`terminal_reason == oracle_plateau`) is unchanged and now
  means the ladder was exhausted.
- The goal driver applies the runner role to its single invocation. Judge
  config and the ladder are ignored there with a stderr note: it has no judge
  and no plateau signal.
- Copilot is out of scope: `run_loop` already refuses `--host copilot`
  (ADR-0043), and agent renders stay model-neutral.

## Consequences

**Becomes easier:**

- Measuring tiering. Every iteration states what it requested, which models
  (and advisor) actually ran, and what it cost, so "Sonnet + advisor vs Opus"
  becomes a query over `state.json`, not a guess.
- Spending capability where the loop is stuck, instead of on every iteration.
- A future host-campaign outcome line (spec 040 follow-up) can report
  `plateau@rung` directly from the summary.

**Becomes harder:**

- Sizing a run: with a ladder, `max_iterations` must cover
  `plateau_window × (rungs + 1) + 1` iterations to give every rung a fair
  window. This is documented in the agent-loop SKILL.md, not enforced.
- Reading a run: the same run can mix models, and a split judge's sessions are
  scattered across iteration records. The history entry's `session_id` is the
  index.
- `models` is a new validated surface on both `loop.py` and the heartbeat.

## Assumptions

- **A1 (vendor evidence):** escalating effort before model is cheaper for an
  equal pass rate. That rests on Anthropic's own benchmark (see Context
  force 1). servo does not assume it holds for its targets; the accounting from
  038-01 plus `escalation_rung` makes it measurable per target.
- **A2 (experimental flag):** `--advisor` is accepted by claude 2.1.321 but is
  absent from `--help` and documented as experimental and Anthropic-API-only.
  If it is removed or renamed, a configured `advisor` fails the invocation
  (`claude_invocation_failed`) rather than silently degrading.
- **A3 (judge cold start):** a split judge's cold read of `files_changed` costs
  less than a model switch inside the shared session. Not measured; 038-01's
  accounting will show it.

## Kill criteria

- After ≥ 20 laddered plateaus across real targets, if escalated rungs convert
  under ~10% of them to a pass, stop recommending the ladder. It would be
  spending without moving outcomes, so the default posture reverts to
  "plateau ⇒ quarantine".
- If Claude Code makes a cross-model resume cache-preserving and
  thinking-compatible, D2-A's split no longer pays for itself. Revisit it.
- If 038-01's accounting shows split-judge iterations cost more than shared ones
  at equal verdict quality across a comparable set of runs, revisit D2-A.

## Open questions

- Should the plan compiler (spec 016) ever *emit* a default `models` block (for
  example, runner on a mid tier)? Deferred until accounting data exists; today
  only a human-edited plan or `--models` sets one.
- Applying a ladder to the goal driver means re-invoking `/goal` at the next
  rung on `oracle_below_threshold`. It is deferred, because that driver has no
  plateau signal and is one invocation by design.
