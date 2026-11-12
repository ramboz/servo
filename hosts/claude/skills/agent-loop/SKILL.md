---
name: servo:agent-loop
description: |
  Run a headless agent loop against a scaffolded target. Subprocesses
  `claude -p --agent <runner|judge>` against the target N iterations under
  hard guardrails (iteration cap, cumulative cost ceiling, context-fill
  refusal, oracle-score plateau detection, SIGINT/SIGTERM cleanup), uses
  `gate.py` as the truth-source after each iteration, and checkpoints state
  to `<target>/.servo/runs/<run-id>/state.json` so an interrupted or capped
  run can be resumed.

  Fire this skill when the user wants to:

    - "run an agent loop" / "iterate on this codebase" / "headless loop"
    - "let claude iterate against my target" / "fire-and-forget claude on this"
    - "resume the loop" / "continue the prior loop" / "pick up where it left off"
    - "loop with cost ceiling X" / "loop until the oracle passes"
    - "use /goal to keep going" / "goal-driven loop" / "--driver goal" — the
      ADR-0008 mode that delegates continuation to Claude Code's `/goal` while
      servo keeps the oracle + guardrail layer (caps on the outer call, final
      `gate.py` verdict). `--driver auto` (default) probes the host and picks
      goal-or-loop; `--driver loop` forces the portable hand-rolled path.
    - "run it detached / in the background / unattended" / "--background" —
      launch the goal loop detached so it survives terminal close (slice 003-08).
    - "set up a scheduled run" / "make this Routine-ready" /
      "--emit-routine-prompt" — vendor gate.py + print the /goal prompt to paste
      into a scheduled Routine (web/desktop; gate.py is the in-Routine authority).

  Do NOT fire on:

    - "score this code" / "run the oracle" / "what's the oracle score?" —
      that's `/servo:quality-gate` (the loop's truth-source, not a sibling).
    - "set up servo" / "scaffold the oracle" / "install servo" — that's
      `/servo:scaffold-init`; the loop refuses if the target hasn't been
      scaffolded.
    - "race variants" / "run N parallel attempts" — future
      `/servo:variant-race` (spec 005); the loop is single-track.
    - "review my PR" / "code review" — out of scope. The loop's `judge`
      agent is an internal contract between iterations, not a PR reviewer.

  When in doubt, ask which servo skill the user means rather than invent
  a trigger match.
---

# /servo:agent-loop

Headless iteration driver. Subprocesses `claude -p --agent <runner|judge> --output-format json` against a target N times under hard guardrails, scores via `gate.py --json` after each iteration, and decides whether to iterate again. The first servo skill that crosses the line from "scored scaffolding" into actual unattended operation — and the first one that **costs real money per invocation**.

The helper is at `${CLAUDE_PLUGIN_ROOT}/skills/agent-loop/loop.py`.

## Required policy and recovery

Scalar gate v1 and old state-schema-1 checkpoints remain supported. Enabled
gate v2 carries the **original overall payload** as `oracle` and exact published
`gate_ref: {path, hash}` through iteration history, checkpoints and final
summaries. Each live call requests a fresh UUID and accepts its immutable run
once; resume revalidates recorded bytes/bindings without rerunning the evaluator.
Unknown versions or unavailable mandatory bindings refuse (exit 2,
`oracle_evaluation_refused`), even with `--resume-anyway`.
V2 checkpoints also preserve final availability separately from the last
evaluated gate. A failed/interrupted later turn, including a malformed verdict,
cannot restore the old verdict on a zero-new-iteration resume. A cap with no
current evaluation remains unavailable (exit 2); a fresh valid gate can recover.
A historical v1 checkpoint cannot attest a newly enabled required policy
without evaluating it, while no-policy v1 resume behavior remains unchanged.

Required veto at composite 1 / zero weight / `THRESHOLD=0` stays `fail`.
Component pass plus quality failure also stays overall fail. Diagnostic plateau
can still stop the run with `oracle_plateau`, **never fulfillment**. Existing
iteration, budget, context and goal disagreement/cap reasons remain separate
from structured `oracle_reason`. No pass sentinel is authorized by a component
or remembered score.

Inspect `oracle.required.items` (IDs, reasons, evidence indexes), `gate_ref`, and
the gate's exact component paths/hashes. For a contradiction, repair the
implementation and rerun. For `required_evidence_unavailable`, repair acquisition,
approved runtime/config bindings or installation first; do not substitute `0.0`.
Policy changes require explicit owner review/reapproval. Preserve raw evidence;
`source_identity` is approved provenance, not served/current-build attestation.
Goal/Routine vendors include `gate.py`, `required_runtime.py`, and
`gate_consumer.py`; commit their portable closure when preparing a clone.

## Copilot capability boundary

Installing this skill does not select a native execution backend. The helper's
default remains Claude; do not silently run Claude for a requested Copilot task.

**Loop driver on Copilot (spec 041-02 / ADR-0048).** `--host copilot` runs the
loop under a brake denominated in **AI credits** (never converted to USD), but
only with an explicit **`--credit-ceiling N`** (N ≥ 30, the CLI's `--max-ai-credits`
minimum) **and** an explicit `--max-iterations`. Without both, the ADR-0043 refusal
stands (exit 2, `native_capability_unavailable`, before dispatch or target
mutation). The worker is single-threaded (no `--fleet` — 041-01 found no subagent
tool to deny), the goal driver stays refused (`--driver goal` and `--background`
refuse under Copilot), and a `--models` block is refused (Copilot renders are
model-neutral, spec 032-03). Units never mix: `--cost-ceiling` (USD) is refused
under `--host copilot`, and `--credit-ceiling` under `--host claude`. The brake
**fails closed** — a missing / `partial` usage report, a missing or disagreeing
OpenTelemetry span export, or a worker model with no shipped overrun bound halt
(`credit_usage_unavailable` / `credit_bound_unavailable`) with spend reported as
`null`, never `0`. `--explain-routing --host copilot` stays read-only.

Use the project-owned `quality-gate` independently of a host driver. Native loop,
checkpoint resume, planned/heartbeat execution and enforcing stop continuation
are incomplete; a package install is not proof of those capabilities.
Identified non-Claude/native version-2 state cannot resume through Claude.
Unmarked legacy version-1 state retains the historical Claude interpretation;
the September prototype did not record a backend, so its origin cannot always
be recovered. Do not convert or blindly resume known prototype native state.

## When to use this skill

Use when the user wants to **iterate** an already-scaffolded target. Scaffolding is a different skill (`/servo:scaffold-init`); scoring without iteration is `/servo:quality-gate`. This one closes the loop — measure (gate.py), compare (against threshold), adjust (claude -p), brake (caps & ceilings), repeat.

## Operation modes

### `loop.py <target> --prompt "<text>"` — fresh run

Generates a fresh `run-id`, writes initial state at `<target>/.servo/runs/<run-id>/state.json`, then iterates. The seed prompt is sent to claude each iteration (assembled with the last oracle output and last verdict block on iter 2+).

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/agent-loop/loop.py" <target> --prompt "fix the failing tests"
```

### `loop.py <target> --resume <run-id>` — resumed run

Reads state from `<target>/.servo/runs/<run-id>/state.json` and continues from `iteration_count + 1`. Cumulative cost, oracle history, session-id, and the seed prompt all carry forward. CLI overrides like `--max-iterations 20` re-apply on top of persisted values.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/agent-loop/loop.py" <target> --resume 20260520T143205-a3f1
```

## Drivers — `--driver {auto|loop|goal}` (ADR-0008)

Two continuation drivers deliver the same guardrailed-iteration value; `auto` picks between them per host:

- **`--driver auto`** (default) — runs a deterministic **host-support probe** (slice 003-07) and routes: the goal driver when `/goal` is available (`claude` ≥ 2.1.139) **and** hooks are permitted, else a fail-safe downgrade to the loop driver (the reason is logged to stderr). See [Host-scope routing](#host-scope-routing-slice-003-07).
- **`--driver loop`** — the hand-rolled driver above. Servo owns the whole loop: it subprocesses `claude -p` once per iteration and enforces every brake itself. The **portable / external-driver** path — works in hook-restricted environments and non-Claude-Code hosts (e.g. Codex) where the platform primitives don't exist.
- **`--driver goal`** — delegates *continuation* to Claude Code's `/goal` primitive. A **single** `claude -p` carries a `/goal` completion condition that drives across-turn continuation; servo's hard guardrails ride the **outer** invocation. The platform owns "keep going"; servo owns "is it actually good, and is it safe to keep going." On an unsupported host an explicit `--driver goal` **refuses** (rc=2) rather than silently degrading.

The goal driver also **vendors a clone-portable copy of `gate.py`** into `<target>/.claude/skills/servo-quality-gate/gate.py` before running (idempotent), so the in-transcript gate run and the authoritative final score resolve the oracle relative to `$CLAUDE_PROJECT_DIR` after a clone (ADR-0008 V4).

### `loop.py <target> --driver goal --prompt "<text>"` — /goal-driven run

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/agent-loop/loop.py" <target> --driver goal --prompt "fix the failing tests"
```

What it does, in one `claude -p`:

1. **Composes a `/goal` prompt.** A `/goal` completion condition that *fact-checks* a printed pass sentinel, then the seed task, then a per-turn loop-body instruction to run `servo:quality-gate` (`gate.py --json`) and print the sentinel verbatim.
2. **Wires the hard caps onto the outer call** — `--max-turns` (= `--max-iterations`, default 5) **and** `--max-budget-usd` (= `--cost-ceiling`, default $2). Both are V2-verified to bind a `/goal` run. (`--cost-ceiling 0` omits the budget flag; `--max-turns` always binds.)
3. **Runs a final authoritative `gate.py --json`** after `claude -p` returns and treats **that** exit code as the verdict — never the transcript judge.

**The sentinel — a single pinned shape.** The loop-body instruction and the driver's transcript parser share one format:

```
SERVO_ORACLE_VERDICT exit=<rc> status=<pass|fail> composite=<c> threshold=<t>
```

The `/goal` condition fact-checks the **bare** `SERVO_ORACLE_VERDICT exit=0 status=pass`; the driver's own parser requires the full `composite=`/`threshold=` tail, so the bare condition text can never be miscounted as a real pass. **`oracle.sh` is never replaced by `/goal`'s transcript judge** (ADR-0008 hard constraint; ADR-0002 exit-code contract) — the judge sits *downstream* of the oracle, confirming a fact the oracle already printed.

**Fail-closed.** If the transcript printed a real pass sentinel but the final `gate.py` scores below threshold, the run halts with `terminal_reason=oracle_disagreement` (exit 2) — the oracle, not the transcript, decides.

**Refuse, don't degrade.** If `/goal` can't run (hooks restricted via `disableAllHooks` / `allowManagedHooksOnly`, or a binary without `/goal`), `--driver goal` refuses with `terminal_reason=goal_unavailable` (exit 2); the breadcrumb names `--driver loop` as the portable fallback. `--resume` is **not** supported in goal mode (detachment is slice 003-08) — both a goal-mode `--resume` and a loop-mode `--resume` of a goal-written run-id refuse with `goal_resume_unsupported`.

## Host-scope routing (slice 003-07)

`--driver auto` (the default) decides the path from two deterministic facts and never silently runs the wrong one:

- **`/goal` available** — `claude --version` ≥ 2.1.139.
- **hooks permitted** — neither `disableAllHooks` (any settings layer) nor `allowManagedHooksOnly` (managed tier) is set; either disables both `/goal` and the meta-judge, leaving only the no-hooks loop driver.

| `--driver` | eligible (both true) | otherwise |
|---|---|---|
| `auto` (default) | goal driver | loop driver — fail-safe downgrade, reason on stderr |
| `goal` | goal driver | **refuses** rc=2 / `goal_unavailable` |
| `loop` | loop driver | loop driver |

Inspect the decision without running anything:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/agent-loop/loop.py" <target> --explain-routing
```

It prints the chosen driver, `/goal` eligibility, every settings layer inspected, and the layer that forced any restriction — then exits 0.

## Refuse-on-dirty-tree (slice 003-07)

Before a fresh run, if `<target>` is a git repo with **uncommitted changes to tracked files**, the driver refuses (rc=2 / `terminal_reason=dirty_tree`; the breadcrumb names the dirty paths) — a scheduled / unattended run could otherwise score leftover state as a spurious immediate pass (ADR-0008 V4). On by default. `--allow-dirty` opts out for an intentional dirty run; a non-git target skips the check; untracked files don't count; and a loop-mode `--resume` skips it (its tree is legitimately mid-flight). 

## Detached runs & scheduled Routines (slice 003-08)

Two surfaces let the guardrailed goal loop run **unattended** — no human at the terminal.

### `loop.py <target> --background --prompt "<text>"` — detached run

Launches the goal-driven run **detached, in a new OS session**, so a long unattended run survives the terminal closing, then returns immediately with the run-id:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/agent-loop/loop.py" <target> --background --prompt "fix the failing tests"
```

`/background` (alias `/bg`) is an **interactive** agent-view action — it detaches a TUI session — and there is **no headless `--background` flag** on `claude -p` (verified on 2.1.175). So servo detaches at the OS level: it re-execs itself as the goal driver under `start_new_session` (POSIX `setsid`), redirects the child's output to `<target>/.servo/runs/<run-id>/background.log`, and hands you the run-id. Inspect or await the run through its `state.json` (003-04) — the detached child rewrites it atomically as it progresses:

```bash
cat <target>/.servo/runs/<run-id>/state.json   # "detached": true + the evolving verdict
```

The detached run carries **every guardrail unchanged** — the hard caps ride the child's outer `claude -p`, the final `gate.py` is the authority (it's the same goal driver, just re-exec'd). Preflight refusals (unscaffolded target, **dirty tree**, un-vendorable gate) are checked **synchronously, before detaching**, so they surface to you instead of being buried in the log. `--background` **requires the goal driver**: on a host that can't run `/goal` it refuses (like an explicit `--driver goal` would) rather than silently downgrading to a non-detachable loop run; `--driver loop --background` is rejected up front (detach a foreground loop with your shell's `nohup`/`&`, or use `--resume`). The parent prints one summary line (`"detached": true`, `terminal_reason: "detached"`, the `run_id`, child `pid`, and the `state_path` / `log_path`) and exits 0 — `detached` means *launched*, not finished.

### `loop.py <target> --emit-routine-prompt --prompt "<text>"` — Routine-ready target

A **Routine** (a scheduled, unattended run on Anthropic-managed cloud infra) is created from the web / desktop app — there is **no `routine` / `schedule` CLI subcommand** (2.1.175). So servo can't *create* a Routine; it makes the target **Routine-ready** and prints the exact prompt to paste:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/agent-loop/loop.py" <target> --emit-routine-prompt --prompt "fix the failing tests"
```

It (1) vendors the **clone-portable `gate.py`** (003-07) so the oracle resolves relative to `$CLAUDE_PROJECT_DIR` after the Routine clones the repo into the cloud, and (2) prints the canonical `/goal` loop-body prompt — the same shape the live goal driver composes, but with a **portable** gate command (`python3 .claude/skills/servo-quality-gate/gate.py . --json`, not this host's absolute interpreter). Paste it into a Routine pointed at the repo, grant Bash + Edit/Write, and schedule it. It runs nothing locally and exits 0; it does **not** gate on this host's `/goal` support (the Routine runs in the cloud).

### `gate.py` is the authority in a Routine (the meta-judge is moot)

A Routine executes the task as a **single continuous agent invocation** — no per-turn `Stop` event — so servo's meta-judge `Stop` hook (spec 004) **never fires** there (ADR-0008 V4), *independent of the cloud's hook policy*. servo's deterministic authority in a continuous-invocation context is therefore **`gate.py`**: the loop body runs `servo:quality-gate` every turn and prints the `SERVO_ORACLE_VERDICT` sentinel, the `/goal` condition only **fact-checks** it, and (for the local goal driver) a **final authoritative `gate.py` run** is the verdict. The run does **not** depend on the meta-judge firing. `oracle.sh` stays the sole authority for what "pass" means (ADR-0002); the meta-judge is the **interactive-only** backstop (it fires on turn-mediated `claude -p` / interactive stops, never in a Routine).

### Clean baseline per scheduled run

A scheduled rerun must start from a **clean committed baseline** — a **fresh clone**, or `git reset --hard` to the committed state — so leftover state from a prior run can't score as a spurious immediate pass (ADR-0008 V4 saw exactly this). servo's **refuse-on-dirty-tree** brake (003-07) enforces this fail-closed: `--background` runs the dirty check *before* detaching, and any fresh goal/loop run refuses (`rc=2 / dirty_tree`) against uncommitted tracked changes unless you pass `--allow-dirty`.

## Output shape

One per-iteration JSON line on stdout per completed iteration (plus one final summary line):

```json
{"schema_version": 1, "iteration": 1, "agent": "runner", "session_id": "...",
 "cost_usd": 0.05, "cumulative_cost_usd": 0.05, "context_fill_ratio": 0.4,
 "verdict": {"schema_version": 1, "verdict": "CHANGES_MADE", "reasoning": "..."},
 "terminal_reason": "completed", "oracle_exit_code": 1, "oracle_status": "below_threshold",
 "oracle_composite": 0.6, "oracle_threshold": 0.5, "run_id": "..."}
```

Each per-iteration line (and each `oracle_score_history` entry in `state.json`) also carries the invocation's accounting (spec 038-01): `cost_basis` (`session_delta` | `reported`), `usage` (this invocation's four token counts), `model_usage` (per model id: `cost_usd` + token counts; an advisor consult adds `"advisor": true`, best-effort), `model` (highest-cost non-advisor model, else `null`) and `requested` (`{model, effort, advisor}` the role asked for; `null` = inherited). **`cost_usd` is the invocation's own cost**: on a resumed session `claude -p` reports the session's running total, so the loop subtracts the last snapshot (`current_session_usage_snapshot` in `state.json`) when it can prove running-total semantics, and otherwise falls back to the reported total (`cost_basis: "reported"`, with a one-line `loop: ` stderr breadcrumb on a resumed iteration), which can only over-count. `cumulative_cost_usd` is the sum of the per-invocation costs (an early-halt iteration such as `verdict_schema_mismatch` adds its cost without a history entry). The fallback breadcrumb is suppressed under `--host copilot`, which reports no `modelUsage`. The goal driver's summary and `state.json` gain the same `session_id` / `usage` / `model_usage` / `model` / `requested` keys with `cost_basis: "reported"`.

**Role model placement (spec 038-02, [ADR-0047](../../docs/decisions/adr-0047-per-node-model-tiering-and-escalation-ladder.md))**: `--models <json|file>` (inline JSON when it starts with `{`, else a path) or a plan's top-level `models` block places the roles: `{"runner": {"model", "effort", "advisor"}, "judge": {...}}`, all optional strings, `inherit` == unset (`effort`: `low|medium|high|xhigh|max`). `--models` replaces the plan block entirely (no per-field merge); on `--resume` it replaces the persisted `models` in `state.json`, otherwise the persisted block is kept. A bad block refuses rc=2 before any run directory exists (`models_invalid` for the flag, `plan_value_invalid` for the plan key). Set fields reach the argv as `--model/--effort/--advisor`; with no block every argv is unchanged. The goal driver applies the runner block to its single invocation and ignores a judge block with one stderr note; `--background` forwards the block to the detached child.

**Plateau escalation ladder (spec 038-03, [ADR-0047](../../docs/decisions/adr-0047-per-node-model-tiering-and-escalation-ladder.md))**: the `models` block also takes `escalation`, a list of rung objects (`model` / `effort` / `advisor`, at least one set) that override the **runner only**; rungs are cumulative (rung *k* = the base runner config with rungs 1..*k* applied in order) and the judge config never changes. A block holding only an `escalation` list counts as in effect (the judge split applies). Instead of halting at `oracle_plateau`, the loop climbs one rung inside the same run, worktree and budget:
- **Rung window.** At escalation the loop records a baseline (the best numeric composite so far). The rung's window starts at its **first runner iteration** (a judge turn between escalation and that iteration re-scores the old tree and is left out); its plateau check is `_check_plateau` over the baseline plus the rung's own entries, with the run's `plateau_window` / `plateau_noise_floor`. Rung 0 is today's check.
- **Fair-window guard.** A plateau escalates only if the next rung can afford one full window: `needed = plateau_window` (+1 when the next iteration is a judge turn); iterations left (`max_iterations - i`) must be at least `needed`, and, with a cost ceiling, `cost_ceiling - cumulative_cost_usd` must be at least `needed x` the largest per-iteration `cost_usd` so far (a lower bound; a raised rung usually costs more). Otherwise, on the last rung, or with no ladder, the run halts `oracle_plateau` as today (a guard refusal adds one stderr line naming budget left vs needed). A ladder therefore never turns a plateau into `max_iterations_reached`.
- **Fresh runner session per rung.** Escalating clears `current_session_id` and the cost snapshot, so the rung's first runner iteration omits `--resume` (the worktree is kept, the stuck transcript is not), and its prompt gains an `Escalation` section (the rung, the best composite so far and the iteration that reached it, the composite at escalation). One stderr line names the rung and runner config. Escalation also discards the old session's context-fill ratio (the fresh session has none yet). A raised-rung (rung >= 1) run that ends `claude_invocation_failed` or `verdict_schema_mismatch` keeps that terminal; a stderr line and the summary's `terminal_breadcrumb` name the rung and the runner config (for a judge turn they name the judge and say its config is unchanged by the rung). The heartbeat passes it on. `--resume` with a block that has no ladder returns the run to rung 0 and drops `escalation_rung` / `escalation_history_start`; `escalation_events` is kept as the per-rung measurement record, and the summary carries no ladder keys. **Driver routing:** `--driver auto` (the default, also a plan's `auto`) with a non-empty `escalation` ladder routes to the loop driver with one stderr line, since the goal driver has no plateau signal; an explicit `--driver goal` (or `--background`, which needs the goal driver) keeps the ladder-ignored note.
`--explain-routing` does not reflect a ladder. Routing reads the ladder only
from `--models` or the plan, so **resume a laddered run with `--driver loop`**.
Under `auto` on a goal-capable host, a resume without `--models` would route to
the goal driver, which refuses with `goal_resume_unsupported`.
- **Sizing.** Rungs share `--max-iterations` and `--cost-ceiling`; no rung raises a cap. At window 3 with nothing improving, rung 0 plateaus at iteration 4, rung 1 at 7 and rung 2 at 11, so a two-rung ladder needs `--max-iterations 11` or more and a cost ceiling covering about 11 iterations at the top rung's price. Any improvement pushes those points later. Under the defaults (5 iterations, window 3) the guard always refuses.
- **Recording (only when a ladder is configured; otherwise no new keys).** Each history entry and per-iteration line carries `rung` (0 = base); `state.json` carries `escalation_rung`, `escalation_events` (`[{rung, at_iteration, baseline_composite, runner}]`), and the window index `escalation_history_start` (the baseline is `escalation_events[-1].baseline_composite`); the summary carries `escalation_rung` and `escalation_rungs` (the ladder length). `requested` reflects the rung's runner config. `--resume` continues at the persisted rung; a shorter resumed ladder clamps the rung to its length (no further escalation). The goal driver has no plateau signal, so it ignores `escalation` with one stderr note.

**The judge split.** When the resolved block sets any field, every judge iteration starts a fresh session (no `--resume`) and never updates `current_session_id` or the cost snapshot (its `cost_basis` is `reported`; its `session_id` is still recorded on its history entry). Runners keep resuming one session so their cache stays warm. Why: probed, the judge's agent-switched `--resume` reads 0 cached tokens even at equal model and later ones re-read the interleaved runner turns uncached, whereas a fresh judge reads only its self-contained prompt and stays independent of the runner's transcript. With no block in effect, runner and judge share one session as before. Measurement baseline: a block that names the default model explicitly (e.g. `{"judge": {"model": "<default>"}}`) gives the split without a model tier, so the split's effect can be measured on its own. When a role requests an advisor, any `model_usage` id equal to it (or containing it as a `-`-delimited token, e.g. `opus` in `claude-opus-5-5`) is also marked `"advisor": true` unless the id also names the role's own requested model. Caveat: the heuristic applies only when the role requests a `model`; with an inherited model only `advisor_message` consults (final-turn ones) are attributed, because the executor's own `claude-opus-*` entry could otherwise be mislabelled as the advisor. Under the split, `context_fill_ratio` alternates between the runner's session and a fresh judge session; the context-fill gate still protects the runner, since every runner turn is followed by the pre-judge check on the runner's own ratio.

Final summary line carries `terminal_reason` (one of `oracle_passed`, `max_iterations_reached`, `cost_ceiling_reached`, `context_full`, `oracle_plateau`, `interrupted`, `claude_invocation_failed`, `gate_invocation_failed`, `verdict_schema_mismatch`, the preflight `dirty_tree` refusal, plus the resume-time refusals), `iterations_completed`, `cumulative_cost_usd`, and the configured caps.

## Outcome line — `--outcome-line <path|->` (spec 040)

`--outcome-line` makes the loop write **exactly one** typed, compact record after
its summary — to a file (`<path>`) or to stdout (`-`). **Without the flag, output
is byte-identical** to today. It is a pure *rendering* of the summary the run
already emits (spec 038 cost + escalation-ladder fields included); the loop stays
trigger-agnostic — a host orchestrator is just another trigger, like the heartbeat.

```json
{"servo_outcome": 1, "result": "plateau", "rung": 1, "rungs": 2,
 "iterations": 7, "cost_usd": 0.84, "composite": 0.78, "threshold": 0.8,
 "run_id": "20260112T143205-a3f1", "reason": "oracle_plateau"}
```

- **`result`** is derived from the summary's `terminal_reason` **and**
  `final_oracle_status`: `passed` (oracle cleared the bar) / `plateau` (ran, stayed
  below) / `budget` (iterations / turns / USD / credits / context exhausted while
  scoring) / `blocked` (an environment / host / permission precondition refused) /
  `error` (a fault, malformed input, or an oracle that ran but never produced a
  valid verdict). The original `terminal_reason` rides along verbatim as `reason`.
  Both the loop and goal drivers emit it; the goal driver reports `rung: 0`.
- **`rung` / `rungs`** are the spec-038 ladder position (`0` / `1` with no ladder).
  **`cost_usd`** is the run's `cumulative_cost_usd`. **`run_id`** locates the run.
  Under `--host copilot` the run has no USD cost, so `cost_usd` is `null`: the
  credit spend lives in the summary line and `state.json` (`cumulative_credits`,
  spec 041-02), which a campaign ledger re-derives by `run_id` regardless.

**A host forwards it (servo does not orchestrate).** A host — a Claude Code
session, a Copilot `create_session`, a Managed Agents workflow — spawns a worker
under `loop.py` and forwards the single line up, instead of a conversation:

```bash
# Capture the one outcome line from the worker's stdout and forward it:
python3 "${CLAUDE_PLUGIN_ROOT}/skills/agent-loop/loop.py" <target> \
  --prompt "<task>" --outcome-line - | tail -1
# → {"servo_outcome":1,"result":"plateau","rung":1,"rungs":2,"cost_usd":0.84,...}

# …or write it to a file (robust against interleaved logging) and read it back:
python3 "${CLAUDE_PLUGIN_ROOT}/skills/agent-loop/loop.py" <target> \
  --prompt "<task>" --outcome-line "$RUN_DIR/outcome.json"
cat "$RUN_DIR/outcome.json"   # the host forwards this verbatim to its coordinator
```

A Claude Code host that runs the worker as `claude -p "<run loop.py …>"` reads the
same line from that invocation's captured stdout (A1). With `--background` the flag
is **forwarded to the detached child**, which owns the real terminal (the parent
prints only a `detached` launch summary and exits): the child writes the one record
at its halt — to `--outcome-line <path>` (poll it beside `state.json`), or to its
stdout (the run-dir `background.log`) for `-`. For an unattended/background worker,
prefer a `<path>` so the host reads a file rather than scraping the log.

**Boundary (spec 040, non-negotiable).** This is output only. servo does **not**
spawn, message, or track workers — **no `/servo:crew` (spec 003), no fan-out (spec
005)**. The host owns the worker tree; the outcome line is just the worker's typed
result. A campaign ledger (spec 042) uses the line only to locate the run by
`run_id`, then re-derives result / rung / cost from that run's `state.json`.

## Options

| Flag | What it does |
|---|---|
| `--driver {auto\|loop\|goal}` | Continuation driver. `auto` (default) probes the host and routes goal-or-loop; `loop` is the hand-rolled 003-01..05 driver (portable; every brake servo-side); `goal` delegates continuation to `/goal` with the caps on the outer call + a final `gate.py` verdict (ADR-0008). See [Host-scope routing](#host-scope-routing-slice-003-07). |
| `--prompt "<text>"` | Seed prompt sent to claude each iteration. Required for fresh runs; optional on resume (persisted prompt is used when omitted). Not required with `--explain-routing`. |
| `--max-iterations N` | Iteration cap. Default 5. Loop halts at N if no earlier brake fires. **Goal mode:** becomes `--max-turns N` on the outer `claude -p`. |
| `--cost-ceiling N` | Cumulative cost ceiling in USD. Default $2.00. The iteration that first crosses is the last one to run. Pass `0` to disable. **Goal mode:** becomes `--max-budget-usd N` on the outer call (`0` omits it). Refused under `--host copilot`. |
| `--credit-ceiling N` | **Copilot only** (spec 041-02 / ADR-0048): cumulative budget in **AI credits** for `--host copilot`. Required (with an explicit `--max-iterations`) to run the loop on Copilot; min 30. Never converted to USD; mutually exclusive with `--cost-ceiling`. Each worker invocation gets `--max-ai-credits` = the remaining headroom (the cap is invocation-scoped). Refused under `--host claude`. |
| `--context-fill-threshold N` | Refuse iter N+1 when the prior iteration's context-fill ratio ≥ this value (in [0.0, 1.0]). Default 0.75. Pass `0` to disable. |
| `--plateau-window N` | Halt when the oracle composite has not improved over the last N iterations. Default 3. Pass `0` to disable. |
| `--plateau-noise-floor N` | Frozen noise floor δ (ADR-0005 clause 4): composite gains smaller than N read as "flat" for plateau detection, so a wobbling non-deterministic eval component can neither fake progress nor fake a plateau. Default 0.0 (any strict gain counts as improvement). Set to a frozen eval's δ when an eval component contributes to the composite. Loop-mode brake — ignored under `--driver goal`. |
| `--allow-dirty` | Bypass the refuse-on-dirty-tree preflight (slice 003-07). By default a fresh run against a git target with uncommitted changes to tracked files refuses (rc=2 / `dirty_tree`). Non-git targets skip the check regardless. |
| `--explain-routing` | Print the host-scope routing verdict for `<target>` (chosen driver, `/goal` eligibility, settings layers, forcing layer) and exit 0. Read-only — needs no `--prompt`, runs nothing. |
| `--background` | Launch the goal-driven run **detached** in a new OS session (slice 003-08) so it survives the terminal closing; prints the run-id + state/log paths and returns 0. Requires the goal driver (refuses on a host that can't run `/goal`; rejected with `--driver loop`). Inspect via `<target>/.servo/runs/<run-id>/state.json`. |
| `--emit-routine-prompt` | Make `<target>` Routine-ready — vendor the clone-portable `gate.py` (003-07) — and print the paste-ready `/goal` Routine prompt (portable `python3` + relative gate path), then exit 0 (slice 003-08). Requires `--prompt`; runs no loop. |
| `--models <json\|file>` | Place the `runner` / `judge` roles on a model, effort and advisor (spec 038-02): inline JSON starting with `{`, else a JSON file path. Replaces a plan's `models` block entirely, and on `--resume` the persisted one. Any set field (or an `escalation` ladder) gives the judge its own fresh session. A bad block refuses `models_invalid`. `--emit-routine-prompt` does not carry it (stderr note). |
| `--resume <run-id>` | Resume a prior run. Refuses with rc=2 on missing / schema-mismatched / claude-version-mismatched state (escape via `--resume-anyway`). |
| `--resume-anyway` | Bypass the schema/version mismatch refusals on resume. Risky — silent mis-decoding may corrupt the run. Does not bypass missing-state refusal. |
| `--outcome-line <path\|->` | Spec 040: after the summary, write **one** typed outcome record (`servo_outcome`) a host-spawned worker forwards to its orchestrator — to `<path>`, or stdout for `-`. Without it, output is byte-identical. Pure rendering of the summary; no `/servo:crew`, no fan-out. See [Outcome line](#outcome-line----outcome-line-path---spec-040). |

Env var: `SERVO_CLAUDE_TIMEOUT` — per-invocation wall-clock cap on each `claude -p` (default 1800s = 30 min). `0` disables the bound. Test/CI environments commonly lower this.

## Refusal handling

The loop uses a closed `{0, 2, 130}` exit contract. **Do NOT silently retry** — surface the message verbatim to the user and offer the appropriate recovery.

| `terminal_reason` | Exit | Meaning | Recovery to suggest |
|---|---|---|---|
| `oracle_passed` | 0 | Composite ≥ threshold — done | None needed. |
| `max_iterations_reached` | 0 | Hit the iteration cap without passing | Offer `--resume <run-id> --max-iterations N+M`. |
| `cost_ceiling_reached` | 0 | Cumulative cost crossed the ceiling | Offer `--resume <run-id> --cost-ceiling <new>` if user wants to keep spending. |
| `credit_ceiling_reached` | 0 | **Copilot:** cumulative AI credits crossed `--credit-ceiling` | Offer `--resume <run-id> --credit-ceiling <new>` to keep spending. |
| `context_full` | 0 | Prior iteration's context was ≥ threshold full | The session is saturated; resume starts a fresh subprocess but reuses `session_id`. Suggest `--resume-anyway` only if user is sure the saturated session is recoverable. |
| `oracle_plateau` | 0 | No composite improvement over the last M iterations (with a `models.escalation` ladder: on the last rung, or when the next rung could not get a full window) | Loop is likely stuck. Offer to change the seed prompt OR raise `--plateau-window` if a longer plateau is genuinely expected. With a ladder, `escalation_rung` in the summary shows how far it climbed; a ladder needs `--max-iterations` and `--cost-ceiling` sized for its rungs. |
| `interrupted` | 130 | SIGINT/SIGTERM received | The state file is finalized; resume picks up after the interrupted iteration. |
| `target_missing` / `target_not_directory` | 2 | Bad target path | Confirm the path. |
| `manifest_missing` / `oracle_missing` | 2 | Target not scaffolded | Run `/servo:scaffold-init` on the target first. |
| `state_missing` | 2 | `--resume <run-id>` against an absent/malformed state file | Verify the run-id against `<target>/.servo/runs/`. `--resume-anyway` does NOT bypass this. |
| `state_schema_mismatch` | 2 | State file's `state_schema_version` differs from this `loop.py` | Resume with `--resume-anyway` if you accept the risk of silent mis-decoding. |
| `claude_version_mismatch` | 2 | State file's `claude_version` differs from current `claude --version` | Same — `--resume-anyway` accepts the risk that session/JSON semantics may have changed. |
| `run_id_collision` | 2 | Three consecutive run-id allocation collisions | Pathological; usually a stuck clock or a filesystem issue. Surface the colliding ids. |
| `claude_invocation_failed` | 2 | `claude -p` failed (binary missing, JSON parse error, timeout) | Surface the stderr breadcrumb. Most common: `claude` not on PATH, or the configured `SERVO_CLAUDE_TIMEOUT` was too tight. |
| `credit_usage_unavailable` | 2 | **Copilot:** a missing / `partial` usage report, or a missing / disagreeing OTel span export — spend is unknown (`null`, never 0) | Fail-closed by design (ADR-0048 part 3). Check the worker's telemetry; never treat the halt as free spend. |
| `credit_ceiling_insufficient` | 2 | **Copilot:** the worker model's overrun bound is ≥ `--credit-ceiling` (a budget in name only) | Raise `--credit-ceiling` above the bound named in the stderr breadcrumb. |
| `credit_bound_unavailable` | 2 | **Copilot:** the worker model has no shipped overrun bound | servo cannot verify the overrun guarantee for this model (fail-closed). File a follow-up to add its bound. |
| `gate_invocation_failed` | 2 | `gate.py` emitted unparseable output | Defensive branch — should not fire in normal operation. Inspect gate.py output. |
| `verdict_schema_mismatch` | 2 | Agent's `verdict` block missing `schema_version`, non-integer, or ≠ 1 | The agent (runner/judge) malfunctioned. Likely a Claude Code or agent-prompt upgrade is needed; surface the breadcrumb and ask the user. |

### Goal-mode terminal reasons (`--driver goal`)

Goal mode emits a single summary line (`"driver": "goal"`, no per-iteration lines — the loop runs inside `claude`):

```json
{"schema_version": 1, "driver": "goal", "terminal_reason": "oracle_pass",
 "subtype": "success", "claude_terminal_reason": "completed", "num_turns": 3,
 "cumulative_cost_usd": 0.42, "cost_ceiling_usd": 2.0, "max_turns": 5,
 "final_oracle_status": "pass", "oracle_composite": 0.91, "oracle_threshold": 0.85,
 "transcript_showed_pass": true, "run_id": "..."}
```

| `terminal_reason` | Exit | Meaning | Recovery to suggest |
|---|---|---|---|
| `oracle_pass` | 0 | `/goal` stopped and the final `gate.py` confirms composite ≥ threshold | None needed. |
| `oracle_below_threshold` | 0 | Run ended (no real pass sentinel) and the final gate is below threshold | Re-run with a sharper prompt, or raise `--max-iterations` / `--cost-ceiling`. |
| `iteration_cap_reached` | 0 | `--max-turns` bound the `/goal` run (`subtype=error_max_turns`) | Offer a fresh `--driver goal` run with a higher `--max-iterations`. |
| `cost_ceiling_reached` | 0 | `--max-budget-usd` bound the run (`subtype=error_max_budget_usd`) | Offer a fresh run with a higher `--cost-ceiling` if the user wants to keep spending. |
| `oracle_disagreement` | 2 | Transcript printed a real pass sentinel but the final gate is below threshold — **fail-closed** | The transcript judge was fooled (or the tree changed). Inspect the target; do NOT treat as a pass. |
| `goal_unavailable` | 2 | `/goal` couldn't run — explicit `--driver goal` on an unsupported host (hooks restricted, or `claude` predates `/goal`), or `/goal` refused at runtime | Re-run with `--driver loop` (the portable hand-rolled driver), or `--driver auto`. Surface the breadcrumb; `--explain-routing` shows why. |
| `goal_resume_unsupported` | 2 | `--resume` of a goal-driven run (out of scope until 003-08) | Start a fresh `--driver goal` run, or use `--driver loop` for resumable runs. |
| `models_invalid` | 2 | Preflight: `--models` (or a persisted `state.json` `models` on `--resume`) is unreadable, not a JSON object, has an unknown key, a non-string value, a bad `effort`, or a malformed model/advisor id (spec 038-02; a bad plan `models` key is `plan_value_invalid`) | Fix the block; nothing ran and no state was written. |
| `dirty_tree` | 2 | Preflight: the git target has uncommitted changes to tracked files (slice 003-07) | Commit/stash, or pass `--allow-dirty` for an intentional dirty run. The breadcrumb names the paths. |
| `gate_vendor_failed` | 2 | Couldn't vendor the clone-portable `gate.py` into the target (e.g. `.claude` is a non-directory, or perms block the write) | Surface the breadcrumb; fix the target's `.claude/` path/permissions. |
| `detached` | 0 | **Parent of a `--background` launch** (slice 003-08): the run was launched detached — this is not a finished outcome. | None — inspect `state.json` for the real verdict as the detached child progresses. |
| `detach_failed` | 2 | `--background` couldn't spawn the detached child (e.g. the run-dir `background.log` can't be opened) | Surface the breadcrumb; check the target's `.servo/runs/` path/permissions. |
| `claude_invocation_failed` / `gate_invocation_failed` | 2 | Same as loop mode (binary/JSON failure; final gate unparseable) | Surface the stderr breadcrumb. |

## Examples

**Fresh run (convergence path)**:

```
user: run an agent loop against my project to make the tests pass
assistant: → python3 .../loop.py /path/to/repo --prompt "make the tests pass"
        → iter 1: agent=runner, oracle_status=below_threshold
        → iter 2: agent=judge, oracle_status=below_threshold
        → iter 3: agent=runner, oracle_status=pass, oracle_exit_code=0
        → summary: terminal_reason=oracle_passed iterations_completed=3
```

**Iteration cap reached**:

```
user: iterate on this for 3 cycles
assistant: → python3 .../loop.py /path/to/repo --prompt "..." --max-iterations 3
        → iter 1..3 emitted; oracle never passes
        → summary: terminal_reason=max_iterations_reached run_id=20260520T...
assistant: [surfaces the result; offers --resume <run-id> --max-iterations 6 to continue]
```

**Resume after iteration cap**:

```
user: resume that loop with 5 more iterations
assistant: → python3 .../loop.py /path/to/repo --resume 20260520T143205-a3f1 --max-iterations 8
        → iter 4..8 run; cumulative cost carries forward
```

**Cost-ceiling halt**:

```
user: cap the spend at $0.50
assistant: → python3 .../loop.py /path/to/repo --prompt "..." --cost-ceiling 0.50
        → iter 1 burns $0.30, iter 2 burns $0.25 → cumulative $0.55 > $0.50 → halt
        → summary: terminal_reason=cost_ceiling_reached cumulative_cost_usd=0.55
```

**Plateau halt**:

```
user: iterate until done
assistant: → python3 .../loop.py /path/to/repo --prompt "..."
        → iter 1..4 all score composite=0.6 (no improvement)
        → summary: terminal_reason=oracle_plateau plateau_window=3 iterations_completed=4
assistant: [surfaces the plateau; suggests refining the prompt OR --resume with --plateau-window 0]
```

**Goal-driven run (`/goal` continuation)**:

```
user: loop on this with /goal until the oracle passes, cap 4 turns
assistant: → python3 .../loop.py /path/to/repo --driver goal --prompt "..." --max-iterations 4
        → one claude -p: /goal drives turns; each turn runs the gate + prints SERVO_ORACLE_VERDICT
        → --max-turns 4 + --max-budget-usd 2 bind the outer call; final gate.py is the verdict
        → summary: driver=goal terminal_reason=oracle_pass final_oracle_status=pass num_turns=3
```

**Refusal — target not scaffolded**:

```
assistant: → python3 .../loop.py /path/to/repo --prompt "..."
        stderr: loop: .servo/install.json not found at /path/to/repo/.servo/install.json; run /servo:scaffold-init first
        stdout: summary terminal_reason=manifest_missing
assistant: [surfaces verbatim; offers to run /servo:scaffold-init; does NOT silently retry]
```

**Refusal — verdict schema mismatch**:

```
assistant: → python3 .../loop.py /path/to/repo --prompt "..."
        stderr: loop: verdict block schema_version is 2; expected 1
        stdout: summary terminal_reason=verdict_schema_mismatch
assistant: [surfaces verbatim; the agent (runner/judge) emitted an incompatible block — likely a Claude Code or prompt upgrade is needed]
```

## After invocation

The loop persists state at `<target>/.servo/runs/<run-id>/state.json` (per ADR-0004). On a clean iteration cap / cost ceiling / plateau / context-full / oracle pass, the state file holds the final scoreboard for forensic reading or future resume. On SIGINT/SIGTERM, the state file is finalized atomically; resume continues from `iteration_count + 1`.

The loop is **not stateless** — that's the whole point of the slice 003-04 contract. If a caller wants to inspect a run after the fact, point them at `<target>/.servo/runs/<run-id>/state.json`.

## Oracle-as-a-service / bring-your-own-implementer

This skill is **one optional driver**, not a prerequisite for using servo. [ADR-0021](../../docs/decisions/adr-0021-oracle-first-agent-loop-optional-consumer.md) reframes servo as **oracle-first**: `/servo:scaffold-init` + Compile produce a frozen, reviewable oracle, and `/servo:quality-gate` (`gate.py`) is the pass/fail **authority** over it. Any driver may then perform the edits — a human, a CI pipeline, or another agent — and the flow is the same either way:

1. **Compile** — scaffold + freeze the oracle (`/servo:scaffold-init`; spec 001/006).
2. **Drive** — some implementer edits the target. This skill (`loop.py`) is one such driver — the hand-rolled `--driver loop` and `/goal`-delegated `--driver goal` paths both subprocess `claude -p`. But nothing requires it: a human editing by hand, a CI job running its own script, or another agent (e.g. a jig:implementer working inside a different harness) can drive the edits instead.
3. **Judge** — `quality-gate` (`gate.py`) scores the result with the closed 0/1/2 exit contract, independent of who or what made the edits.

This mode exists because the native loop **cannot always run** — it shells out to `claude -p`, which needs top-level authentication and edit permissions it cannot obtain when nested inside another agent's sandboxed sub-process (see the refusal table below: `claude_invocation_failed` on an auth failure, and the plateau/`context_full` symptom of denied edit permissions). When that's the case, skip this skill and drive `quality-gate` directly — see [`skills/quality-gate/SKILL.md`'s "External-driver / bring-your-own-implementer contract"](../quality-gate/SKILL.md#external-driver--bring-your-own-implementer-contract) for how to use `gate.py` standalone as the authority. Full context: [ADR-0021](../../docs/decisions/adr-0021-oracle-first-agent-loop-optional-consumer.md).
