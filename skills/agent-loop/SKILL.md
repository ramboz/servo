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
| `--prompt "<text>"` | Seed prompt sent to claude each iteration. Required for fresh runs; optional on resume (persisted prompt is used when omitted). |
| `--max-iterations N` | Iteration cap. Default 5. Loop halts at N if no earlier brake fires. |
| `--cost-ceiling N` | Cumulative cost ceiling in USD. Default $2.00. The iteration that first crosses is the last one to run. Pass `0` to disable. |
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
