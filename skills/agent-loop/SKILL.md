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
      `gate.py` verdict). `--driver loop` (default) is the portable fallback.

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

## Drivers — `--driver {loop|goal}` (ADR-0008)

Two continuation drivers deliver the same guardrailed-iteration value; pick by host:

- **`--driver loop`** (default) — the hand-rolled driver above. Servo owns the whole loop: it subprocesses `claude -p` once per iteration and enforces every brake itself. The **portable / external-driver** path — works in hook-restricted environments and non-Claude-Code hosts (e.g. Codex) where the platform primitives don't exist.
- **`--driver goal`** — delegates *continuation* to Claude Code's `/goal` primitive. A **single** `claude -p` carries a `/goal` completion condition that drives across-turn continuation; servo's hard guardrails ride the **outer** invocation. The platform owns "keep going"; servo owns "is it actually good, and is it safe to keep going."

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

## Output shape

One per-iteration JSON line on stdout per completed iteration (plus one final summary line):

```json
{"schema_version": 1, "iteration": 1, "agent": "runner", "session_id": "...",
 "cost_usd": 0.05, "cumulative_cost_usd": 0.05, "context_fill_ratio": 0.4,
 "verdict": {"schema_version": 1, "verdict": "CHANGES_MADE", "reasoning": "..."},
 "terminal_reason": "completed", "oracle_exit_code": 1, "oracle_status": "below_threshold",
 "oracle_composite": 0.6, "oracle_threshold": 0.5, "run_id": "..."}
```

Final summary line carries `terminal_reason` (one of `oracle_passed`, `max_iterations_reached`, `cost_ceiling_reached`, `context_full`, `oracle_plateau`, `interrupted`, `claude_invocation_failed`, `gate_invocation_failed`, `verdict_schema_mismatch`, plus the resume-time refusals), `iterations_completed`, `cumulative_cost_usd`, and the configured caps.

## Options

| Flag | What it does |
|---|---|
| `--driver {loop\|goal}` | Continuation driver. `loop` (default) is the hand-rolled 003-01..05 driver (portable; every brake servo-side). `goal` delegates continuation to `/goal` with the caps on the outer call + a final `gate.py` verdict (ADR-0008). See [Drivers](#drivers----driver-loopgoal-adr-0008). |
| `--prompt "<text>"` | Seed prompt sent to claude each iteration. Required for fresh runs; optional on resume (persisted prompt is used when omitted). |
| `--max-iterations N` | Iteration cap. Default 5. Loop halts at N if no earlier brake fires. **Goal mode:** becomes `--max-turns N` on the outer `claude -p`. |
| `--cost-ceiling N` | Cumulative cost ceiling in USD. Default $2.00. The iteration that first crosses is the last one to run. Pass `0` to disable. **Goal mode:** becomes `--max-budget-usd N` on the outer call (`0` omits it). |
| `--context-fill-threshold N` | Refuse iter N+1 when the prior iteration's context-fill ratio ≥ this value (in [0.0, 1.0]). Default 0.75. Pass `0` to disable. |
| `--plateau-window N` | Halt when the oracle composite has not improved over the last N iterations. Default 3. Pass `0` to disable. |
| `--resume <run-id>` | Resume a prior run. Refuses with rc=2 on missing / schema-mismatched / claude-version-mismatched state (escape via `--resume-anyway`). |
| `--resume-anyway` | Bypass the schema/version mismatch refusals on resume. Risky — silent mis-decoding may corrupt the run. Does not bypass missing-state refusal. |

Env var: `SERVO_CLAUDE_TIMEOUT` — per-invocation wall-clock cap on each `claude -p` (default 1800s = 30 min). `0` disables the bound. Test/CI environments commonly lower this.

## Refusal handling

The loop uses a closed `{0, 2, 130}` exit contract. **Do NOT silently retry** — surface the message verbatim to the user and offer the appropriate recovery.

| `terminal_reason` | Exit | Meaning | Recovery to suggest |
|---|---|---|---|
| `oracle_passed` | 0 | Composite ≥ threshold — done | None needed. |
| `max_iterations_reached` | 0 | Hit the iteration cap without passing | Offer `--resume <run-id> --max-iterations N+M`. |
| `cost_ceiling_reached` | 0 | Cumulative cost crossed the ceiling | Offer `--resume <run-id> --cost-ceiling <new>` if user wants to keep spending. |
| `context_full` | 0 | Prior iteration's context was ≥ threshold full | The session is saturated; resume starts a fresh subprocess but reuses `session_id`. Suggest `--resume-anyway` only if user is sure the saturated session is recoverable. |
| `oracle_plateau` | 0 | No composite improvement over the last M iterations | Loop is likely stuck. Offer to change the seed prompt OR raise `--plateau-window` if a longer plateau is genuinely expected. |
| `interrupted` | 130 | SIGINT/SIGTERM received | The state file is finalized; resume picks up after the interrupted iteration. |
| `target_missing` / `target_not_directory` | 2 | Bad target path | Confirm the path. |
| `manifest_missing` / `oracle_missing` | 2 | Target not scaffolded | Run `/servo:scaffold-init` on the target first. |
| `state_missing` | 2 | `--resume <run-id>` against an absent/malformed state file | Verify the run-id against `<target>/.servo/runs/`. `--resume-anyway` does NOT bypass this. |
| `state_schema_mismatch` | 2 | State file's `state_schema_version` differs from this `loop.py` | Resume with `--resume-anyway` if you accept the risk of silent mis-decoding. |
| `claude_version_mismatch` | 2 | State file's `claude_version` differs from current `claude --version` | Same — `--resume-anyway` accepts the risk that session/JSON semantics may have changed. |
| `run_id_collision` | 2 | Three consecutive run-id allocation collisions | Pathological; usually a stuck clock or a filesystem issue. Surface the colliding ids. |
| `claude_invocation_failed` | 2 | `claude -p` failed (binary missing, JSON parse error, timeout) | Surface the stderr breadcrumb. Most common: `claude` not on PATH, or the configured `SERVO_CLAUDE_TIMEOUT` was too tight. |
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
| `goal_unavailable` | 2 | `/goal` couldn't run (hooks restricted, or no `/goal` in this binary) | Re-run with `--driver loop` (the portable hand-rolled driver). Surface the breadcrumb. |
| `goal_resume_unsupported` | 2 | `--resume` of a goal-driven run (out of scope until 003-08) | Start a fresh `--driver goal` run, or use `--driver loop` for resumable runs. |
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
