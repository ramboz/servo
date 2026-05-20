---
status: DONE
dependencies: [001, 002]
last_verified: 2026-05-20
---

# Spec 003 — agent-loop

> Headless iteration driver. Subprocesses `claude -p --output-format json` against a target N times under hard guardrails — **iteration cap, cumulative cost ceiling, context-fill refusal gate, checkpoint/resume, stuck-loop detection** — and uses `gate.py --json` (spec 002) as the truth-source after each iteration. Owns the subagent-handoff state machine across iterations: which agent (`runner` / `judge`) each spawn invokes, what context it carries, what survives. The first servo skill that crosses the line from "scored scaffolding" into actual unattended operation.

## Why this spec

Spec 001 dropped a tailored `oracle.sh` + manifest into the target. Spec 002 made the oracle uniformly callable via `gate.py` with normalized exit codes and structured JSON. Without spec 003, those two stop short of the headline servo promise — **run an agent against the oracle without a human watching, with the brakes wired in from day one.**

This is also the spec where servo earns its name. A servo is a closed-loop control system that measures a signal, compares it to a target, and adjusts until they match. Specs 001 + 002 built the signal-and-target machinery. 003 closes the loop:

- **Measure:** `gate.py --json` reads the oracle's composite score.
- **Compare:** loop driver checks oracle exit (0 = match), context-fill ratio, cumulative cost, oracle-score plateau.
- **Adjust:** invoke `claude -p` to mutate the target; repeat.
- **Brakes:** iteration cap, cost ceiling, context-fill gate, plateau halt — every brake fails-closed (halt the loop) rather than fails-open (keep burning budget).

Spec 003 is the first servo skill that **costs real money per invocation**. The hard guardrails are not optional safety theater — they are the contract that lets a user fire-and-forget a loop and trust that it will stop on its own.

It is also the truth-source for the *next two* runtime skills:

- **Spec 004 (`/servo:oracle-hook`)** installs a `Stop` hook that scores every assistant turn against the oracle and emits structured retry hints. The hook reuses `gate.py` from spec 002, but it borrows the **per-iteration prompt-assembly machinery** from spec 003 (what oracle output + what judge verdict gets fed back to the agent).
- **Spec 005 (`/servo:variant-race`)** races N worktrees in parallel, each running its own agent-loop, then picks the highest oracle score. The race driver wraps the loop driver — so the loop's checkpoint/resume + cost-ceiling primitives become race-shared state.

So 003 is unblocking for the rest of the runtime backlog, in the same way 001 was unblocking for the whole servo backlog.

## Pre-spec research

A [pre-spec research spike](spike.md) (2026-05-18) verified Claude Code's headless surface against `claude --help` + a live `claude -p ... --output-format json` invocation. Every guardrail in this spec maps cleanly to today's CLI surface — primarily via `--output-format json` + external accounting in the Python loop driver. None is blocked on a Claude Code feature gap. The spike also surfaced three load-bearing corrections to the initial research brief (no `--max-turns` flag exists; `--agent <name>` does exist; context-fill % is exposed via `usage` + `modelUsage.contextWindow`) and reframed ADR-0004's scope (servo's per-run state is a small scoreboard that references `session_id`, not a transcript copy).

## Out of scope (deferred to later specs or refused outright)

- **Hook-driven `Stop`-event scoring (→ 004 oracle-hook).** The loop driver is a one-shot subprocess; hook integration is its own surface.
- **Per-variant scoring across worktrees (→ 005 variant-race).** The race driver wraps the loop driver; the loop doesn't know about variants.
- **Multi-agent crew coordination.** Servo ships a post-mortem template only; no `/servo:crew` skill ever (per `docs/architecture.md` "Why no crew skill").
- **Loop UI / progress bars / TUI.** The loop emits one JSON line per iteration to stdout, plus a final summary line. Consumers can pipe it to whatever rendering they want. Servo doesn't ship a renderer.
- **Cloud cost ceilings.** Only Claude Code's per-invocation cost (`total_cost_usd`) is tracked. Out-of-band charges (network egress, third-party tool calls) are not in the gate. Documented limitation.
- **Cross-machine checkpoint portability.** Per ADR-0001's filesystem-only coupling: state files are valid on the machine they were written on. A future spec may add export/import; today, "filesystem-only" means "wherever the JSONL session lives."
- **`claude --version` compatibility shims.** If the captured CLI surface drifts under a future Claude Code release, spec 003 refuses to resume sessions written by an incompatible version (per the spike's risk register). No translation layer.
- **Cross-run coordination / locking / mutex on the target filesystem.** Per Clarifications Q10: two `loop.py` instances against the same target rely on per-run-id directory isolation; the user owns side-effect coordination on the target's content (oracle.sh outputs, `claude -p` mutations). If concurrent-run footguns surface in practice, a future refinement-todo entry can add an advisory lockfile — but no preemptive locking is in scope here.

## SPIDR decomposition

Mirrors the spec 001 / 002 cadence (spike-shaped first slice → core safety primitives one at a time → state-file contract → agent-roster authoring + plateau detection) because the problem shape rhymes: ship a tool the LLM and the runtime skills both invoke, in vertical slices that each deliver end-to-end value.

### Slice index

| Slice | Title | Goal |
|---|---|---|
| 003-01 | invoke-loop | `loop.py <target>` subprocesses `claude -p --output-format json` N times; capture per-iteration JSON; halt on oracle pass or iteration cap. Spike-shaped: validates the loop-driver-subprocesses-Claude-Code assumption. |
| 003-02 | cost-ceiling | Cumulative cost tracking from per-iteration `total_cost_usd`; halt when cumulative exceeds `--cost-ceiling` (default $2). Per-iteration `--max-budget-usd` defense-in-depth. |
| 003-03 | context-fill-gate | External ratio from `usage` + `modelUsage.<model>.contextWindow`; refuse iteration N+1 when ratio exceeds threshold (default 75%). The hard-gate cousin of jig's soft `jig-context-check.sh`. |
| 003-04 | checkpoint-resume | Per-run state at `<target>/.servo/runs/<run-id>/state.json`; `loop.py --resume <run-id>` reads back, passes `--resume <session_id>` to `claude -p`. ADR-0004 lands. |
| 003-05 | stuck-loop-and-handoff | Oracle-score-plateau detection (halt on no improvement over M iterations) + real `runner.md` / `judge.md` prompts authored; loop dispatches via `claude --agent <name>`. Closes ADR-0003 candidate. |

Five slices, sized to match the spec 001 / 002 cadence. The vertical-value rule still applies — after every slice the loop driver is end-to-end usable on its own.

---

## Slice 003-01 — invoke-loop

**STATUS: DONE**

**Goal:** A `loop.py` helper that, invoked against a target with a scaffolded oracle, runs `claude -p --output-format json --max-budget-usd <budget>` in a counted loop (default 5 iterations). After each iteration, it invokes `gate.py <target> --json` to score the result. The loop halts on (a) oracle pass (composite ≥ threshold), or (b) iteration cap reached. Each iteration's JSON is emitted on stdout; the loop ends with a single summary JSON line. End-to-end value: any servo-scaffolded target can be put on a counted loop in one command — and the loop genuinely stops, on its own, with parseable output.

**DoR:**
- ✅ Spec 002 DONE (gate.py shipped with `--json` mode + closed exit codes per ADR-0002)
- ✅ Spike: `claude -p --output-format json` schema captured empirically (see [spike.md](spike.md))
- ✅ Decision: helper is a Python script (same shape as `scaffold.py` / `gate.py`), no shell wrapper. Resolves the `docs/architecture.md` open question "shell vs Python" in favor of Python — JSON parsing + state-file management in slice 003-04 is materially easier in Python than bash.
- ✅ Architecture default `max-iterations=5` (per `docs/architecture.md` "Project vs servo-core split")
- ✅ Decision: each iteration invokes `claude -p` as a **fresh subprocess**, not a long-lived process. The session is carried across iterations by `session_id` only (slice 003-04 wires resume; 003-01 forks a fresh session every iteration).

**Acceptance Criteria:**

1. **Iteration cap (default).** Against a target with a `composite < threshold` oracle and a prompt that does **not** make it pass, `loop.py <target> --prompt "<text>"` runs exactly 5 iterations, then exits 0 with a summary line carrying `terminal_reason=max_iterations_reached`.
2. **Iteration cap (override).** `loop.py <target> --prompt "<text>" --max-iterations 3` runs exactly 3 iterations.
3. **Early halt on oracle pass.** When the gate exits 0 at iteration K (1 ≤ K ≤ N), the loop stops at K and emits `terminal_reason=oracle_passed`. Iterations K+1..N are not invoked. (Tested with a fixture oracle that flips from below-threshold to pass after one iteration.)
4. **Refusal on missing target / oracle / manifest.** `loop.py` defers to `gate.py`'s refusal taxonomy on the first iteration's pre-flight: missing target → rc=2 / `target_missing`; missing manifest → rc=2 / `manifest_missing`; missing oracle → rc=2 / `oracle_missing`. The loop never enters iteration 1 in any of these cases.
5. **Per-iteration JSON.** Each completed iteration writes a single JSON object to stdout with at minimum: `iteration` (int, 1-indexed), `session_id` (string), `cost_usd` (float, from `total_cost_usd`), `terminal_reason` (string, from claude's JSON), `oracle_exit_code` (int, 0/1/2), `oracle_composite` (float or null), `oracle_threshold` (float or null).
6. **Summary line.** After the last iteration (whether by oracle-pass, iteration-cap, or refusal mid-loop in slices 003-02..05), the loop writes a final JSON line with: `terminal_reason` (`oracle_passed` / `max_iterations_reached`), `iterations_completed` (int), `cumulative_cost_usd` (float), `final_oracle_status` (`pass` / `below_threshold` / `env_error`), `run_id` (string, generated each invocation in 003-01 — `<target>/.servo/runs/<run-id>/` is reserved-only at this slice; the state file lands in 003-04).
7. **Helper is dependency-free.** Same rule as `scaffold.py` / `gate.py` — Python 3.10+, stdlib only.
8. **Mock-claude harness.** Tests use a fake `claude` binary (shell script that emits canned `--output-format json` output) injected via `PATH` to avoid actual Claude Code invocations in CI. The harness produces a `session_id`, `total_cost_usd`, `num_turns`, `terminal_reason="completed"`, etc. matching the captured schema from [spike.md](spike.md).
9. **`claude -p` invocation failure → rc=2 / `claude_invocation_failed`.** Per Clarifications Q8: any failure invoking `claude -p` (binary not on PATH, exit-non-zero without parseable JSON output, JSON parse error, OS-level error) maps to a uniform rc=2 with `reason=claude_invocation_failed`. The stderr breadcrumb names the specific cause (`loop: claude not on PATH`, `loop: claude -p exited <N> without JSON output`, `loop: claude JSON parse error: ...`). (Forward reference: slice 003-04 also persists `claude_invocation_failed` as `last_terminal_reason` in the state file for resume-time forensics.) Tested with a mock harness that variously: removes `claude` from PATH, returns rc=1 with empty stdout, returns invalid JSON.

**DoD:**
- [x] All ACs pass; full test suite green (no regressions in `test_gate.py` / `test_scaffold.py`).
- [x] Test coverage per AC under `skills/agent-loop/test_loop.py`: AC1→`IterationCapDefaultTests`, AC2→`IterationCapOverrideTests`, AC3→`EarlyHaltOnOracleTests`, AC4→`PreflightRefusalTests`, AC5→`PerIterationJsonTests`, AC6→`SummaryLineTests`, AC7→`DependencyFreeTests`, AC8→`MockClaudeHarnessTests`, AC9→`ClaudeInvocationFailedTests`.
- [x] Reviewed by `jig:reviewer` subagent.
- [x] Implementation review passed.
- [x] Deviation log produced under this slice heading.
- [x] Reconciliation review passed.
- [x] `docs/refinement-todo.md` updated if any decisions were deferred during implementation.

### Close-out (post-DONE)

- [x] `docs/specs/README.md` status board: spec 003 → `IN_PROGRESS (slice 003-01)`.
- [x] `README.md` skills table row for `agent-loop` flipped from "Future spec" to `Spec 003 — IN PROGRESS`.

**Anti-horizontal-phasing check:** After this slice, a user with a servo-scaffolded target can run `loop.py <target> --prompt "<text>"` and trust that a counted loop runs, halts on its own (either at oracle pass or iteration cap), and emits parseable JSON per iteration. That is end-to-end value — every subsequent slice is a brake, not a prerequisite for "the loop works."

**Spike-shape note:** This slice is **load-bearing spike-shape** for spec 003 as a whole. It validates the spike's central assumption — "loop driver subprocesses Claude Code via `claude -p --output-format json`, parses the JSON, and decides what to do next" — in the only place it can be validated cheaply (without yet wiring cost / context / resume / plateau). If `claude -p` behaves differently than the spike measured (e.g., the JSON schema drifts under a fresh release, `--max-budget-usd` interacts unexpectedly with `--output-format json`, the `session_id` returned isn't actually consumable by `--resume`), pause and re-plan slices 003-02..05 before proceeding. A re-plan here is cheaper than carrying a wrong shape through four more slices.

### Deviation log (after reconciliation)

**Slice 003-01 — implemented 2026-05-19.** 35 tests green via `python3 skills/agent-loop/test_loop.py` (28 AC-tests + 4 schema-version + 3 timeout); full regression suite still green (40/40 `test_scaffold.py`, 13/13 `test_skill_surface.py` scaffold, 75/75 `test_gate.py`, 18/18 `test_skill_surface.py` gate). Mock-claude harness via PATH-injection works end-to-end; the spike's central assumption (loop driver subprocesses `claude -p --output-format json`, parses JSON, decides) holds in vitro — empirical validation against a live `claude` invocation is deferred to slices 003-02 (cost ceiling) and 003-05 (subagent dispatch) where it has natural cover.

Deviations from spec text:

- **AC4 adds `target_not_directory` as a fourth preflight refusal reason.** The spec's AC4 enumerates three (`target_missing`, `manifest_missing`, `oracle_missing`); the implementation adds `target_not_directory` to mirror gate.py's full taxonomy. Tested via `PreflightRefusalTests.test_target_not_a_directory`. Spec's "defers to gate.py's refusal taxonomy" language covers it but the explicit enumeration is now stale by one entry.
- **`gate_invocation_failed` terminal_reason added as a defensive branch.** Per ADR-0002, gate.py always emits parseable JSON on stdout (even on env-error paths). The loop adds a defensive branch with a distinct `terminal_reason=gate_invocation_failed` for the case where gate.py emits unparseable output anyway — a forensic reader can tell loop / gate / claude failures apart. Not exercised by any test; gate.py is co-located in the same plugin and the branch is unreachable in practice. Documented for completeness rather than tested.
- **OS-error branch in `_invoke_claude` emits a non-AC9-pinned breadcrumb.** AC9 lists three literal stderr breadcrumbs (`claude not on PATH`, `claude -p exited <N> without JSON output`, `claude JSON parse error: ...`). The implementation also catches `OSError` (PermissionError, IsADirectoryError, etc.) other than FileNotFoundError, emitting `OS error invoking claude: <exc>` — covers AC9's parenthetical "OS-level error" but the breadcrumb format isn't in AC9's literal set. No test exercises this branch.
- **AC9 "without JSON output" breadcrumb keeps its wording even when stdout was non-empty-but-unparseable.** The current implementation emits `claude -p exited <N> without JSON output` for any non-zero claude exit, regardless of whether stdout contained text. AC9's wording suggests the more literal reading "stdout was empty"; the implementation chose the looser "we couldn't use the stdout as JSON" reading because 003-01 never invokes claude with flags that produce non-zero-with-JSON paths (`--max-budget-usd` lands in 003-02). Slice 003-02 will need to revisit when budget-exceeded paths surface a non-zero exit with parseable JSON — at that point the breadcrumb will split into "without JSON output" vs "with unparseable output" sub-cases. Until then the simplification is documented but not in the spec text.
- **Per-iteration JSON carries extras beyond AC5's minimum.** Each per-iteration line includes `cumulative_cost_usd`, `oracle_status`, and `run_id` beyond AC5's required minimum field set. AC5's "at minimum" language permits this; the extras are forward-references to surface that slices 003-02 (cumulative cost), 003-04 (run_id-keyed state), and (already in gate.py) status will need.
- **Run-id format uses second-precision, not millisecond.** ADR-0004's prose says "millisecond-precision timestamp prefix" but its own example `20260519T143205-a3f1` is second-precision. The implementation matches the example (`%Y%m%dT%H%M%S` → 15-char timestamp + 4-hex suffix) and the test regex (`^\d{8}T\d{6}-[0-9a-f]{4}$`). ADR-0004's internal inconsistency (prose vs example) is the upstream issue to reconcile when slice 003-04 lands the collision retry; today, the implementation and the example agree.
- **`claude_invocation_failed` summary carries prior-iteration counters.** When claude fails on iteration K, the summary's `iterations_completed` is K-1 (count of successfully-completed prior iterations) and `cumulative_cost_usd` includes only those prior iterations' costs. Spec doesn't pin this; the implementation chose "completed iterations only" (the failed iteration didn't produce a score). Tested implicitly via `ClaudeInvocationFailedTests` where `iterations_completed=0` on first-iteration failure.
- **`final_oracle_status` on mid-loop `claude_invocation_failed` is the "last known" oracle status, not `env_error`.** When iter 1 succeeds with `oracle_status=below_threshold` and iter 2's claude invocation then fails, the summary's `final_oracle_status` is `below_threshold` (from iter 1's gate scoring) — not `env_error` (the current loop state). The semantics chosen are "last successfully-scored state" for forensic value: a consumer correlating `terminal_reason=claude_invocation_failed final_oracle_status=below_threshold` can tell that the loop made progress before claude failed. Alternative ("reset to env_error on any failure") would lose that signal. Documented here so the surface contract is explicit when SKILL.md lands in 003-05.
- **Test PATH is `/bin:/usr/bin`.** Tests set PATH to `<mock_bindir>:/bin:/usr/bin` to ensure the mock claude shadows any host install. This reliably excludes the typical claude install locations (`/usr/local/bin`, NVM/asdf bin dirs, `~/.local/bin`); brittle if a future Linux packaging puts `claude` directly under `/bin` or `/usr/bin` (uncommon but possible). Flagged for portability monitoring; not blocking today.
- **`--max-iterations 0` explicitly rejected.** argparse `parser.error()` fires for `< 1` and exits with rc=2 (matching the closed `{0, 2}` exit-code contract). The spec doesn't pin behavior for zero/negative; rejecting upstream is cleaner than emitting a no-iteration summary.

PR-review follow-on additions (2026-05-19, after first reviewer caveats surfaced gaps the AC-focused review didn't probe):

- **`schema_version: 1` added to every JSON line on stdout.** Mirrors gate.py's ADR-0002 contract and ADR-0004's `state_schema_version`. Auto-injected by `_emit_json` so per-iteration, summary, and preflight-refusal lines all carry it as the first key. Cost: ~20 bytes per line. Benefit: forward-compat for spec 005 race driver and any external consumer that parses the JSON. Tested via `SchemaVersionTests` (4 cases). Not in AC5/AC6 literal field lists but covered by the "at minimum" language; the field is additive and gate-parallel.
- **`claude -p` per-invocation timeout enforced.** Default `DEFAULT_CLAUDE_TIMEOUT_SECONDS=1800` (30 min) — generous upper bound for substantial agentic turns with tool use. Tunable via `SERVO_CLAUDE_TIMEOUT` env var (mirrors gate.py's `SERVO_GATE_TIMEOUT` pattern); `0` disables; malformed values fall back to the default with a stderr breadcrumb. On `subprocess.TimeoutExpired`, Python sends SIGKILL to claude (grandchildren may leak — accepted spike-shape limitation). Routes to the uniform `claude_invocation_failed` terminal_reason per AC9's uniformity rule; the breadcrumb (`claude -p timed out after <X>s (killed)`) names the specific cause for forensics. Tested via `ClaudeTimeoutTests` (3 cases). The 30-min default is a guess flagged in `docs/refinement-todo.md` for tuning with real-world data.
- **Unused `SERVO_VERSION` constant removed.** First-pass implementation declared `SERVO_VERSION = "0.1.0"` in parallel with gate.py / scaffold.py but never referenced it. Reviewer flagged as dead code; removed. (`gate.py` has the same dead-code shape — flagged separately in `docs/refinement-todo.md` for a future cleanup pass.)
- **`_invoke_gate` stderr dump truncated to 500 chars each for stdout/stderr.** Previously dumped the full `proc.stdout` / `proc.stderr` strings on JSON parse failure — a misbehaving gate could spam megabytes into the loop's stderr. Now `[:500]` slice on both. Branch remains defensive (unreachable in practice per ADR-0002).
- **`test_max_iterations_zero_rejected` tightened from `assertNotEqual(0)` to `assertEqual(2)`** and now also asserts the literal `"--max-iterations must be >= 1"` text on stderr. Closes the loose-assertion gap the reviewer flagged.

**Spike-shape check:** The central assumption — loop driver subprocesses `claude -p`, parses JSON, calls gate.py, decides — holds in vitro against the mock-claude harness. The spike's captured JSON schema (session_id, total_cost_usd, terminal_reason, usage.*, modelUsage.<model>.contextWindow) is round-trippable end-to-end. The PATH-injected mock approach successfully isolates tests from any real `claude` binary on the host. Empirical drift between mock and live `claude -p` will surface during 003-02 (live `--max-budget-usd` interaction) and 003-05 (live `--agent <name>` dispatch). **Proceeding to 003-02 with no re-plan.**

**Reviewer caveats (non-blocking, not yet in `docs/refinement-todo.md` because all are addressed in slices 003-02..05):**
- `gate_invocation_failed` defensive branch is untested. Acceptable — gate.py is part of servo and ADR-0002 guarantees JSON output. A future refinement could add a fault-injection test, but the branch fires on broken-gate.py only.
- OS-error branch (non-FileNotFoundError OSError) in `_invoke_claude` is untested. Same posture — defensive, uncommon, would require contrived setup (permission-stripped claude, ENOTDIR on the binary path) to exercise.
- `_invoke_gate` doesn't handle FileNotFoundError on `sys.executable` or `GATE_PATH`. Both are resolved at module load time; failure modes are pathological.

**Reviewer verdict:** PASS (independent review, `jig:reviewer` subagent, 2026-05-19). All 9 ACs met with meaningful subprocess-driven tests; mock-claude harness validates the spike's central assumption; AC9's three literal stderr breadcrumbs are asserted; stdlib-only enforced by source inspection. Deviations are additive (extra refusal reasons, extra JSON fields, defensive branches) and stay within the spec's "at minimum" language. No regressions in `test_gate.py` / `test_scaffold.py`. PR-review follow-on (multi-perspective skill, 2026-05-19) surfaced two Should-Fix gaps (no claude timeout, no schema_version) and one tightening (max-iterations-zero assertion) — all three addressed in-slice with additive tests; 35/35 green post-fix.

---

## Slice 003-02 — cost-ceiling

**STATUS: DONE**

**Goal:** Add cumulative cost tracking from each iteration's `total_cost_usd`. Halt the loop when cumulative cost exceeds `--cost-ceiling` (default $2.00 per `docs/architecture.md`). Each `claude -p` invocation also receives `--max-budget-usd <remaining-budget>` for defense-in-depth (so a single runaway agentic turn within an iteration can't blow past the cumulative ceiling). End-to-end value: an unattended loop is now safe to fire-and-forget — the cost won't exceed the cumulative cap by more than one iteration's burn rate.

**DoR:**
- ✅ Slice 003-01 DONE
- ✅ Architecture default `cost-ceiling=$2` (per `docs/architecture.md`)
- ✅ `claude -p --max-budget-usd <amount>` flag verified in spike (works with `--print` only — matches loop usage)
- ✅ Decision: cumulative cost is summed from each iteration's `total_cost_usd`; no separate `--max-budget-usd` cumulative mode is requested from Claude Code (Claude's flag is per-invocation only)

**Acceptance Criteria:**

1. **Default cost-ceiling.** With no flag, loop halts when cumulative `total_cost_usd` first exceeds $2.00. (Tested by setting the mock `claude` to emit `total_cost_usd=0.75` per iteration → loop halts mid-iteration-3, emitting `terminal_reason=cost_ceiling_reached cumulative_cost_usd=2.25`.)
2. **Flag override.** `loop.py <target> --prompt "<text>" --cost-ceiling 0.50` halts on first iteration emitting > $0.50.
3. **Per-iteration cap.** Each `claude -p` invocation receives `--max-budget-usd <remaining-budget>`, where `remaining-budget = cost_ceiling - cumulative_cost_usd`. (Verified by capturing the args passed to the mock `claude`.)
4. **Per-iteration cap floor.** The per-iteration `--max-budget-usd` is never less than `MIN_BUDGET_FLOOR_USD = 0.01`; if cumulative is already within $0.01 of the ceiling, the loop halts without invoking another iteration (avoids invoking `claude` with a $0 budget).
5. **Terminal reason.** When cost-ceiling halts the loop, the summary line carries `terminal_reason=cost_ceiling_reached`, `cumulative_cost_usd=<X>`, `cost_ceiling_usd=<Y>`.
6. **Cumulative-cost in per-iteration JSON.** Each iteration's stdout JSON line carries both `cost_usd` (this iteration's burn) and `cumulative_cost_usd` (running total including this iteration).
7. **`--cost-ceiling 0` semantics.** Disables the cumulative ceiling entirely. (Useful for testing or when the caller is enforcing a budget out-of-band.) Per-iteration `--max-budget-usd` defaults to a sane upper bound (`DEFAULT_PER_ITER_BUDGET_USD = 1.00`) so a runaway agentic turn still has a brake.

**DoD:**
- [x] All ACs pass; full test suite green (no regressions in `test_loop.py` slice-003-01 cases, `test_gate.py`, `test_scaffold.py`).
- [x] Test coverage per AC under `skills/agent-loop/test_loop.py`: AC1→`CostCeilingDefaultTests`, AC2→`CostCeilingOverrideTests`, AC3→`PerIterationBudgetCapTests`, AC4→`PerIterationBudgetFloorTests`, AC5→`CostCeilingSummaryTests`, AC6→`CumulativeCostPerIterationTests`, AC7→`CostCeilingDisabledTests`. Plus `CostCeilingValidationTests` (CLI rejection of negatives) and `ClaudeNonzeroWithParseableJsonTests` (resolves the 003-01 deviation-log forward reference).
- [x] Reviewed by `jig:reviewer` subagent.
- [x] Implementation review passed.
- [x] Deviation log produced under this slice heading.
- [x] Reconciliation review passed.
- [x] `docs/refinement-todo.md` updated (`DEFAULT_PER_ITER_BUDGET_USD = $1.00` flagged as a tuning target alongside the existing 30-min claude-timeout entry).

### Close-out (post-DONE)

- [x] Cost-ceiling defaults documented in `docs/architecture.md` "Project vs servo-core split" table (already names "max-iterations=5, cost-ceiling=$2" — verified still accurate; implementation matches both values).

**Anti-horizontal-phasing check:** After this slice, a user can leave the loop running overnight and know the worst-case spend is bounded by the cost ceiling (modulo one iteration's burn rate over). The next three slices add stricter brakes; none is required for "the loop is safe to leave alone."

### Deviation log (after reconciliation)

**Slice 003-02 — implemented 2026-05-19.** 17 new tests under `skills/agent-loop/test_loop.py` (52/52 total green); full regression suite still green (75/75 `test_gate.py`, 40/40 `test_scaffold.py`, 18/18 `test_skill_surface.py` gate, 13/13 `test_skill_surface.py` scaffold). The 003-01 deviation-log forward reference ("Slice 003-02 will need to revisit when budget-exceeded paths surface a non-zero exit with parseable JSON") is now closed: `_invoke_claude` splits cleanly into four branches — zero/non-zero × parseable-dict/unparseable — with non-zero-plus-parseable treated as iteration completion (the budget-exceeded path) and non-zero-plus-unparseable retaining the AC9 `claude_invocation_failed` breadcrumb.

Deviations from spec text:

- **AC4 "within $0.01" is implemented as strict less-than (`<`), not inclusive (`≤`).** When the remaining budget equals exactly $0.01, the loop still invokes claude with `--max-budget-usd 0.01`; the floor check fires only when `(cost_ceiling - cumulative) < MIN_BUDGET_FLOOR_USD`. AC4's English wording is ambiguous; the strict reading aligns with the "avoid invoking claude with an effectively-zero budget" rationale (exactly-floor is still a meaningfully nonzero budget). Tests pin the strict reading via `test_passed_budget_never_below_floor` (`assertGreaterEqual(budget, 0.01)`).
- **`cost_ceiling_usd` is emitted in every summary line, not just on `cost_ceiling_reached` halts.** AC5 requires the field on the ceiling-halt path; the implementation includes it on all summary emissions (preflight refusal, `claude_invocation_failed`, `gate_invocation_failed`, `oracle_passed`, `max_iterations_reached`) so a forensic consumer can see the configured bound regardless of how the run ended. Additive beyond AC5's literal text; covered by AC5's "carries" / "at minimum" language. Tested via `test_cost_ceiling_usd_present_on_non_ceiling_halt`.
- **`gate_invocation_failed` defensive branch is forensically inconsistent.** The branch emits `cumulative_cost_usd` *after* iter K's cost has been summed, but `iterations_completed = K-1` (since the iteration didn't get to scoring). Surfaces as "iter K-1 spent K iters' worth of money" in the summary. Not tested — branch is unreachable in practice because gate.py is co-located with loop.py and ADR-0002 guarantees parseable JSON on stdout (the 003-01 deviation log documented the same defensive-only posture). Acceptable for a defensive/unreachable branch; flagged here for completeness rather than fixed.
- **`--max-budget-usd <value>` precision is 6 decimal places (`f"{budget:.6f}"`).** Each claude invocation receives a value like `2.000000` or `0.500000`. Round-trips cleanly through tests' `float()` parsing; downstream consumers (any external argparse-style CLI) accept this format. Documented as the precision contract with claude's CLI.
- **`DEFAULT_PER_ITER_BUDGET_USD = $1.00` (when `--cost-ceiling 0` disables cumulative tracking) is a guess.** Analogous to the 30-min `DEFAULT_CLAUDE_TIMEOUT_SECONDS` default flagged in `docs/refinement-todo.md`; should be tuned with real-world data once the loop has accumulated enough live runs. Flagged in `docs/refinement-todo.md` for review.
- **Negative `--cost-ceiling` values are explicitly rejected** via `parser.error("--cost-ceiling must be >= 0")` (exit code 2, mirroring the `--max-iterations < 1` rejection pattern). Not pinned by AC7; rejected for closed exit-code-contract cleanliness and to avoid silently inverting the per-iter budget arithmetic. Tested via `CostCeilingValidationTests`.
- **Non-zero exit + parseable-but-non-dict JSON (e.g., `[1,2,3]`) routes to the "without JSON output" breadcrumb.** The implementation's data-shape gate (`isinstance(data, dict)`) treats non-dict-but-parseable as "no usable data," falling through to the returncode-based breadcrumb. Slightly misleading wording in this pathological edge case (stdout *was* JSON, just not a dict), but consistent with the rest of the loop's "we need a dict to extract fields" expectation. Untested — pathological corner.
- **Exit 0 + parseable-but-non-dict JSON routes to "claude JSON parse error: output is not a JSON object".** Same data-shape gate, different branch. Consistent with 003-01's wording; untested.
- **`schema_version: 1` propagates to all new emission paths.** The auto-injection in `_emit_json` extends cleanly to the new `cost_ceiling_reached` summary, the cost-aware preflight summaries, and every per-iter line. Not re-asserted in 003-02 tests; `SchemaVersionTests` (003-01) cover the principle.

**Reviewer caveats (non-blocking):**
- AC4 inclusive-vs-strict interpretation is documented but not re-litigated. If the spec author wanted the inclusive reading, the fix is a one-character change (`<` → `≤`) plus updating `test_passed_budget_never_below_floor`.
- The `gate_invocation_failed` forensic mismatch could be tightened by moving `cumulative_cost_usd += cost_usd` after the gate call (the per-iter emission would still see the post-add value). Not fixed because the branch is unreachable.
- Pathological non-dict-JSON cases (both exit codes) are untested. Acceptable for spike-shape; revisit if a fault-injection harness lands later.

**Reviewer verdict:** PASS (independent review, `jig:reviewer` subagent, 2026-05-19). All 7 ACs met with dedicated test classes; the 003-01 forward reference is correctly resolved by the four-branch split in `_invoke_claude`; the two-stage brake (pre-iter floor + post-iter exceed) gives the documented behavior (the iteration that first crosses the ceiling is the last one to run, with no sub-cent budget calls). Deviations are additive (extra summary field, defensive branches) or wording-sharpening (strict `<` for "within"). No regressions in `test_loop.py` slice-003-01 cases, `test_gate.py`, `test_scaffold.py`, or either `test_skill_surface.py`.

---

## Slice 003-03 — context-fill-gate

**STATUS: DONE**

**Goal:** Compute the context-fill ratio from each iteration's JSON output (`(usage.input_tokens + usage.cache_read_input_tokens + usage.cache_creation_input_tokens) / modelUsage.<model>.contextWindow`) and refuse iteration N+1 when the ratio exceeds `--context-fill-threshold` (default 75%). This is the **hard refusal gate** cousin of jig's `jig-context-check.sh` soft warning. End-to-end value: an unattended loop won't run iteration N+1 with a context window already 95% full — it halts cleanly with a parseable terminal reason instead of producing garbage output.

**DoR:**
- ✅ Slice 003-02 DONE
- ✅ Spike: context-fill ratio is exposed via `usage` + `modelUsage.<model>.contextWindow` in the per-iteration JSON (no subprocess gymnastics needed)
- ✅ Decision: threshold default 0.75 (75%). Picked as the midpoint of the spike's 60–75% range. **Flagged in `docs/refinement-todo.md` for tuning** once real-world iteration data accumulates.
- ✅ Decision: ratio is computed from the **prior iteration's** JSON output; applied as a precondition to issuing the next `claude -p`. (Iteration 1 has no prior — always proceeds.)

**Acceptance Criteria:**

1. **Threshold gate (default).** With a synthetic mock `claude` returning `usage.input_tokens=160000` against `modelUsage.<model>.contextWindow=200000` (ratio = 0.80), the loop refuses to invoke iteration N+1 and exits 0 with `terminal_reason=context_full`, `context_fill_ratio=0.80`, `context_fill_threshold=0.75`.
2. **Threshold gate (override).** `loop.py <target> --prompt "<text>" --context-fill-threshold 0.50` refuses at ≥ 50%.
3. **No premature refusal.** Iterations with ratio below threshold continue normally; the ratio is logged per-iteration in stdout JSON under `context_fill_ratio`.
4. **Threshold equals threshold (≥, not >).** Exact-equal ratio `0.75` triggers refusal. Documented because off-by-one in the comparison direction is a classic bug.
5. **Iteration 1 unconditional.** With no prior iteration to read context from, iteration 1 always proceeds regardless of threshold setting.
6. **Refusal happens before `claude -p` invocation.** The loop driver inspects the prior iteration's JSON, decides "refuse," and never invokes `claude -p` for iteration N+1. Verified by counting mock-claude invocations.
7. **`--context-fill-threshold 0` disables the gate.** Useful for tests or callers enforcing the limit out-of-band. (Same shape as `--cost-ceiling 0`.)
8. **Missing `contextWindow` field tolerated.** If a future Claude Code release omits `modelUsage.<model>.contextWindow`, the gate refuses to enforce (logs a one-line breadcrumb to stderr, continues without the gate). This is fail-open for *this specific gate*; the iteration cap and cost ceiling still apply.

**DoD:**
- [x] All ACs pass; full test suite green (no regressions in `test_loop.py` slice-003-01/02 cases, `test_gate.py`, `test_scaffold.py`).
- [x] Test coverage per AC under `skills/agent-loop/test_loop.py`: AC1→`ContextFillThresholdDefaultTests`, AC2→`ContextFillThresholdOverrideTests`, AC3→`ContextFillBelowThresholdTests`, AC4→`ContextFillEqualThresholdTests`, AC5→`ContextFillIterationOneTests`, AC6→`ContextFillRefusalBeforeClaudeTests`, AC7→`ContextFillDisabledTests`, AC8→`ContextFillMissingContextWindowTests`.
- [x] Reviewed by `jig:reviewer` subagent.
- [x] Implementation review passed.
- [x] Deviation log produced under this slice heading.
- [x] Reconciliation review passed.
- [x] `docs/refinement-todo.md` updated (default threshold 0.75 flagged for tuning).

### Close-out (post-DONE)

- [x] Default threshold (0.75) flagged in `docs/refinement-todo.md` as a tuning target.
- [x] `docs/architecture.md` "Why this spec" framing updated to note that 003-03's refusal gate is the hard cousin of jig's `jig-context-check.sh` warning.

**Anti-horizontal-phasing check:** After this slice, the loop refuses to continue with a near-full context window — the single most common cause of degraded agent output. The slice is independently useful; it doesn't depend on checkpoint/resume or runner/judge to deliver its value.

### Deviation log (after reconciliation)

**Slice 003-03 — implemented 2026-05-19.** 31 new tests under `skills/agent-loop/test_loop.py` (83/83 total green: 8 AC test classes + `ContextFillValidationTests` + `ExtractContextFillRatioUnitTests`); full regression suite still green (75/75 `test_gate.py`, 40/40 `test_scaffold.py`, 18/18 `test_skill_surface.py` gate, 13/13 `test_skill_surface.py` scaffold). The context-fill refusal gate is now wired: each iteration's `(usage.input_tokens + cache_read + cache_creation) / modelUsage.<model>.contextWindow` ratio is computed externally; iteration N+1 refuses (rc=0, `terminal_reason=context_full`) when the prior ratio is ≥ threshold.

Deviations from spec text:

- **`_extract_context_fill_ratio` fail-opens on more shapes than AC8 enumerates.** AC8 names only "omits `modelUsage.<model>.contextWindow`"; the helper also fail-opens on (a) missing `usage` block, (b) non-dict `usage` block, (c) non-numeric token values, (d) missing `modelUsage` block, (e) empty `modelUsage` dict, (f) non-dict model entries (skipped, then if no good entry remains → fail-open), (g) `bool`-as-int `contextWindow` (explicit `isinstance(cw, bool)` exclusion at `loop.py:_extract_context_fill_ratio`), (h) zero or negative `contextWindow`. Each path emits a distinct stderr breadcrumb naming the specific cause. Pinned by `ExtractContextFillRatioUnitTests` (12 cases). Fits AC8's "fail-open for this specific gate" semantics — additive on top of the literal "omits contextWindow" case.
- **Pre-iteration gate order: context-fill check fires *before* cost-ceiling floor check.** When both brakes would fire on the same iteration boundary, the summary's `terminal_reason` is `context_full`, not `cost_ceiling_reached`. Not pinned by spec; documented here so a future structured-output consumer knows the precedence rule. Rationale: a high context-fill ratio means the *next* iteration would degrade regardless of budget; reporting `context_full` is the more informative cause.
- **`ContextFillValidationTests` adds CLI bounds rejection for `[0.0, 1.0]`.** Not pinned by spec ACs; mirrors the `--max-iterations < 1` (003-01) and `--cost-ceiling < 0` (003-02) rejection patterns. Negative thresholds always-fire (would gate iter-2 unconditionally); thresholds > 1.0 never-fire (ratio is bounded in `[0, 1]`). Both are user-error shapes; rejected upstream with `parser.error` + rc=2 + breadcrumb `--context-fill-threshold must be in [0.0, 1.0]`. Closed exit-code-contract cleanliness; `0` remains the documented disable value.
- **`context_fill_ratio` per-iter line is added beyond AC3's "logged per-iteration" wording.** AC3 says "logged per-iteration in stdout JSON under `context_fill_ratio`" — the implementation puts it on every per-iter line (success or failure to compute → null). Summary lines also carry `context_fill_ratio` (last observed, or null) for forensic continuity. Spec's "at minimum" language for the per-iter JSON (003-01 AC5) absorbs this additive emission.
- **`context_fill_threshold` is emitted on every summary line, not just on `context_full` halts.** AC1 specifies the field on the gate-halt summary; the implementation adds it to all summary paths (preflight refusal, `claude_invocation_failed`, `gate_invocation_failed`, `oracle_passed`, `max_iterations_reached`, `cost_ceiling_reached`, `context_full`). Mirrors how 003-02 generalized `cost_ceiling_usd` beyond its AC; downstream consumers see the configured bound regardless of how the run ended.
- **Multi-model `modelUsage` resolution: first dict entry with a positive non-bool numeric `contextWindow` wins.** Deterministic given Python 3.7+ dict insertion order — adequate for the single-model case the spike captured, documented in the helper's docstring as the explicit semantics for the (unlikely) multi-model hypothetical. Pinned by `ExtractContextFillRatioUnitTests.test_non_dict_model_entry_skipped`.
- **`input_tokens=null` (and `cache_*=null`) is mapped to zero, not fail-open.** The `.get(key, 0) or 0` idiom collapses both missing and explicit-null to zero; a future Claude Code release that emits `"input_tokens": null` is treated as "zero input tokens" rather than fail-open. Pinned by `ExtractContextFillRatioUnitTests.test_none_tokens_treated_as_zero`. Rationale: a null token count almost certainly means "no input was sent" rather than "the schema broke" — fail-open would be too aggressive here.
- **AC5 (iter 1 unconditional) is exercised by *two* complementary tests.** `test_iteration_one_runs_with_very_low_threshold` (max-iter=1 + threshold=0.05 → iter 1 runs, ends on `max_iterations_reached`) and `test_iter_one_runs_then_iter_two_gated` (max-iter=5 + threshold=0.05 → iter 1 runs, pre-iter-2 gate fires, ends on `context_full`). Either alone is necessary but not sufficient; the pair pins both "iter 1 unconditional" and "iter 2 is gated by iter 1's ratio."
- **`schema_version: 1` propagates to all new emission paths.** The auto-injection in `_emit_json` extends cleanly to the `context_full` summary, the context-aware preflight summaries, and the per-iter line's `context_fill_ratio` field. Not re-asserted in 003-03 tests; `SchemaVersionTests` (003-01) cover the principle.
- **Default cost (`$0.05` per iteration) in the context-fill mock is chosen to keep the cost ceiling out of the way.** The context-fill tests have an implicit cost-budget of $0.05 × 5 iterations = $0.25, well under the default $2.00 ceiling, so cost-ceiling halts can't mask context-fill behavior. Documented in the `_mock_claude_input_tokens_per_iter` helper.
- **`context_fill_threshold: 0` is emitted as the Python float `0.0`, displayed in JSON as `0` (no fractional part by `json.dumps` for clean integers).** A downstream consumer expecting `0.0` (with decimal) will need to round-trip via `float()`. The test `ContextFillDisabledTests.test_disabled_gate_runs_all_iterations` uses `assertEqual(..., 0)` which passes for both. Documented as the JSON-emission shape; not a contract violation.

**Reviewer caveats (non-blocking):**
- The pathological "both `usage` and `modelUsage` missing" case routes to the *first* failure path (missing `usage`). A consumer reading the breadcrumb would only see the `usage`-missing message and not learn that `modelUsage` was also absent. Acceptable for spike-shape — a forensic reader can re-inspect the iteration's full JSON if more detail is needed.
- Pre-iter gate ordering (context-fill before cost-floor) is documented in this log but not pinned by tests. A future refactor that reorders the brakes could change the precedence rule silently. Cheap to pin if it ever matters; today the two brakes are independent in practice (cost-floor fires near $2 cumulative; context-fill fires when ratio ≥ 0.75 — uncorrelated events).
- `_extract_context_fill_ratio`'s "first model with contextWindow wins" semantics for multi-model `modelUsage` is documented but uncovered by an end-to-end test (the unit test exercises non-dict-entry-skipping but not "two valid models, pick first"). Pathological corner; not gated.

**Reviewer verdict:** PASS (independent review, `jig:reviewer` subagent, 2026-05-19). All 8 ACs met with meaningful tests that exercise the spec's pinned behaviors (0.75 default, `>=` direction, iter-1 unconditional, refusal-before-claude via counter file, fail-open with stderr breadcrumb + null ratios). The reviewer's actionable caveats — (a) add unit tests for the helper's six internal failure paths, (b) document the bool-exclusion and pre-iter gate ordering — were addressed in-slice: `ExtractContextFillRatioUnitTests` (12 cases) lands, the bool/zero/negative `contextWindow` exclusions are pinned, and the deviation log captures the gate ordering. 83/83 green post-fix; no regressions in `test_gate.py` / `test_scaffold.py` / either `test_skill_surface.py`.

---

## Slice 003-04 — checkpoint-resume

**STATUS: DONE**

**Goal:** Per-run state at `<target>/.servo/runs/<run-id>/state.json` that records the current `session_id`, cumulative cost, iteration count, oracle-score history, and other run-level scoreboard fields. `loop.py <target> --resume <run-id>` reads the state file back, invokes `claude -p --resume <session_id>` against the carried session, and continues from iteration N+1 with cumulative counters preserved. ADR-0004 lands alongside, recording the state-file shape as a soft cross-plugin contract. End-to-end value: a loop that hit its iteration cap or cost ceiling can be resumed with a higher cap; a loop interrupted by Ctrl-C or machine reboot can pick up where it left off.

**DoR:**
- ✅ Slice 003-03 DONE
- ✅ Spike sketched state-file shape (see [spike.md](spike.md) "ADR-0004 implications")
- ✅ Decision: state-file path is `<target>/.servo/runs/<run-id>/state.json` — reserved in `docs/architecture.md` "Runtime artifacts"
- ✅ Decision: `run-id` is a millisecond-precision timestamp prefix + short random suffix (`20260518T143205-a3f1`) — human-readable, sortable, collision-resistant across parallel races (spec 005 will reuse)
- ✅ Decision: state is written **atomically** (write to `state.json.tmp`, then `os.replace`) so Ctrl-C mid-write can't corrupt the file
- ✅ Decision: state is written **after every iteration** (not just at exit) — so interruptions lose at most the in-progress iteration

**Acceptance Criteria:**

1. **State file written each iteration.** After every iteration's gate scoring (success or failure), `<target>/.servo/runs/<run-id>/state.json` is atomically updated. Verified by tearing down the loop mid-run (subprocess SIGTERM after iteration 2) and reading the state file: `iteration_count=2`, `cumulative_cost_usd` reflects 2 iterations, `current_session_id` is the iteration-2 session.
2. **Schema fields.** The state file carries at minimum: `state_schema_version` (int, starting at 1), `run_id`, `started_at` (ISO8601), `last_updated_at` (ISO8601), `target_path` (absolute), `current_session_id`, `iteration_count`, `max_iterations`, `cost_ceiling_usd`, `cumulative_cost_usd`, `cumulative_input_tokens`, `cumulative_output_tokens`, `context_fill_threshold`, `last_context_fill_ratio`, `oracle_score_history` (list of `{iteration, composite, threshold, status}`), `last_terminal_reason`, `claude_version` (captured via `claude --version` on first iteration for forensics).
3. **Resume from state file.** `loop.py <target> --resume <run-id>` reads the prior state, invokes `claude -p --resume <session_id> ...` for iteration N+1, and continues. Cumulative counters carry forward (cost, iteration count, oracle-score history are not reset).
4. **Resume preserves overrides.** Flags from the original run (e.g., `--max-iterations 10`, `--cost-ceiling 5.00`) are persisted in the state file and re-applied on resume. **Override on resume:** `--resume <run-id> --max-iterations 20` updates the state file's `max_iterations` and continues with the new cap.
5. **Refusal on stale schema.** State file with `state_schema_version` != current version → rc=2 / `state_schema_mismatch` with a stderr breadcrumb naming both versions. **Refusal on claude version drift:** `claude_version` recorded in state differs from current `claude --version` → rc=2 / `claude_version_mismatch` with a stderr breadcrumb. Both refusals are **escapable** via `--resume-anyway` (documented as risky in SKILL.md when slice 003-05 ships).
6. **Refusal on missing state.** `--resume <bogus-run-id>` (no such directory or no `state.json`) → rc=2 / `state_missing` with a stderr breadcrumb naming the expected path.
7. **Fresh run gets fresh run-id.** A new invocation (no `--resume` flag) generates a new `run-id`, creates `<target>/.servo/runs/<run-id>/`, writes initial state, and proceeds.
8. **`<target>/.servo/runs/` is created if absent.** First invocation against a fresh target lays down the parent directory.
9. **Signal handling (SIGINT / SIGTERM).** Per Clarifications Q9: the loop traps SIGINT and SIGTERM, finalizes the current `state.json` atomically, emits a final summary line with `terminal_reason=interrupted`, and exits 130 (standard SIGINT convention). If the signal arrives during `claude -p` (mid-iteration, before scoring), the in-flight iteration is treated as completed for state-file purposes — `iteration_count` reflects the partial iteration — and the summary line carries `final_oracle_status=unknown_interrupted` to flag that no gate scoring ran. If the signal arrives during `gate.py` (after claude completed but before scoring finished), the iteration is treated as completed with the partial gate output recorded and `final_oracle_status=unknown_interrupted`. A second SIGINT (Ctrl-C pressed twice) bypasses the cleanup and exits immediately — escape hatch for a hung trap handler.
10. **Run-id collision retry.** Per ADR-0004: fresh-run `mkdir(<target>/.servo/runs/<run-id>/, exist_ok=False)` failures trigger a bounded retry — the loop regenerates the random suffix (timestamp prefix preserved) and re-attempts, up to **3 attempts total** (initial + 2 retries). On the 4th conflict, refuse with rc=2 / `reason=run_id_collision` and a stderr breadcrumb naming the colliding run-id(s). Tested with `RunIdCollisionTests`: (a) single-collision case where retry succeeds and the loop proceeds; (b) triple-collision case where the loop refuses with the documented `reason` after exhausting attempts. The test harness seeds `<target>/.servo/runs/` with directories matching the next-generated run-ids using a deterministic PRNG seed.

**DoD:**
- [x] All ACs pass; full test suite green (no regressions in `test_loop.py` slice-003-01/02/03 cases, `test_gate.py`, `test_scaffold.py`).
- [x] Test coverage per AC under `skills/agent-loop/test_loop.py`: AC1→`StateFilePersistenceTests`, AC2→`StateFileSchemaTests`, AC3→`ResumeFlowTests`, AC4→`ResumePreservesOverridesTests`, AC5→`ResumeRefusalTests`, AC6→`ResumeMissingStateTests`, AC7→`FreshRunIdTests`, AC8→`RunsDirectoryAutoCreateTests`, AC9→`SignalHandlingTests` + `SignalHandlingDuringGateTests`, AC10→`RunIdCollisionTests`.
- [x] Reviewed by `jig:reviewer` subagent.
- [x] Implementation review passed.
- [x] Deviation log produced under this slice heading.
- [x] Reconciliation review passed.
- [x] `docs/refinement-todo.md` updated (`.gitignore` guidance gap filed).

### Close-out (post-DONE)

- [x] **ADR-0004 Accepted.** (Already Accepted pre-implementation per `docs/architecture.md` "Decisions" table.)
- [x] `docs/architecture.md` "Runtime artifacts" section adds an Agent-loop subsection pointing at the state-file schema (referencing ADR-0004).
- [x] `.gitignore` guidance for `<target>/.servo/runs/` — `scaffold-init` doesn't currently write `<target>/.gitignore`; gap filed in `docs/refinement-todo.md` per the close-out's stated path.

**Anti-horizontal-phasing check:** After this slice, the loop is survivable across interruptions — Ctrl-C, machine reboot, hitting an iteration cap that needs raising. The next slice adds plateau detection + agent dispatch, but resume is independently useful: a user can run `loop.py <target> --max-iterations 5`, see the result, and decide to `--resume` for 5 more.

### Deviation log (after reconciliation)

**Slice 003-04 — implemented 2026-05-20.** 43 new tests under `skills/agent-loop/test_loop.py` (126/126 total green: 10 AC test classes covering ACs 1–10 + 1 supplementary `SignalHandlingDuringGateTests` + `test_resume_prompt_override_replaces_persisted`). Full regression suite still green (75/75 `test_gate.py`, 40/40 `test_scaffold.py`, 18/18 `test_skill_surface.py` gate, 13/13 `test_skill_surface.py` scaffold). Per-run state at `<target>/.servo/runs/<run-id>/state.json` is atomically rewritten after every iteration; `loop.py --resume <run-id>` picks up from `iteration_count + 1` with cumulative counters preserved; SIGINT/SIGTERM trap finalizes state and emits `interrupted` with exit 130; run-id collision retry policy lands per ADR-0004.

Deviations from spec text and ADR-0004:

- **`prompt` is persisted in `state.json` as an additive field.** ADR-0004's canonical schema and AC2's literal field list do not include `prompt`. The implementation persists it so `--resume <run-id>` can replay the original seed without forcing the user to remember it. Permitted under ADR-0004's "pure additive changes MAY keep version at 1" clause; documented in `_build_initial_state`'s docstring. Pinned by `test_resume_omits_prompt_uses_persisted` (uses persisted on omit) and `test_resume_prompt_override_replaces_persisted` (CLI override replaces persisted).
- **`--resume-anyway` does NOT escape `state_missing`.** Spec AC5 lists schema-mismatch and version-mismatch as the escapable refusals; AC6's `state_missing` is unconditional. The implementation matches: `--resume-anyway` only short-circuits the schema and version checks; an absent or unparseable `state.json` still refuses with rc=2 / `state_missing` regardless. Documented in the `state_missing` refusal's message ("--resume-anyway does not bypass parse errors") and pinned by `ResumeMissingStateTests`.
- **Pre-iter-1 interrupt emits `final_oracle_status=unknown_interrupted`, not `env_error`.** AC9 explicitly pins `unknown_interrupted` for during-claude and during-gate cases. The pre-iter-1 case (signal arrives BEFORE iter 1 starts) is not pinned by spec; the implementation chooses `unknown_interrupted` for consistency with the during-iter cases — the run was interrupted, not env-errored. When resuming a run that already had successful iterations, the pre-iter interrupt uses the last successfully-scored iteration's status (not `unknown_interrupted`), since that scoring did complete before the interrupt arrived. Documented in the pre-iter-interrupt branch comment.
- **Pre-iter gate ordering: interrupt check fires *before* context-fill check fires *before* cost-floor check.** Three brakes all live at the top of each iteration; order is documented in the loop body. When multiple brakes apply simultaneously, the precedence is interrupt → context-fill → cost-floor. Not pinned by spec; documented here so the structured-output contract reader knows the precedence rule.
- **Pre-iter interrupt forwards to the active subprocess via `_signal_handler`.** AC9's literal wording doesn't require the signal handler to forward to claude / gate.py; the implementation does so that `proc.communicate()` returns promptly under interrupt instead of waiting for the subprocess to finish naturally. This mirrors real-terminal Ctrl-C behavior (the shell delivers SIGINT to every process in the foreground group). Documented in the `_signal_handler` docstring and pinned by `SignalHandlingTests` + `SignalHandlingDuringGateTests` (both use trap-aware mocks).
- **`_get_claude_version` registers as `_active_subprocess` (additive over reviewer feedback).** First-pass implementation used `subprocess.run` and would have made a SIGINT during the version capture wait the full 10-second timeout before being detected. The independent reviewer flagged the inconsistency; the implementation now uses `Popen + communicate` registered as the active subprocess, identical to `_invoke_claude` and `_invoke_gate`. Behavior on success is identical; under interrupt the version capture returns promptly.
- **`subprocess.Popen` registration race between Popen-return and `_active_subprocess = proc` assignment is non-blocking.** A SIGINT arriving inside this ~2-line window can't be forwarded to the new child (the handler reads `_active_subprocess` before the assignment lands). The iteration-boundary check catches the interrupt flag at the next safe point, so the race is a delivery-latency window, not a wedge. Documented as a known limitation in the `_signal_handler` docstring.
- **`_create_run_dir` uses `_generate_run_id` for collision attempts, but preflight refusals use `_generate_preflight_run_id`.** The split avoids consuming `SERVO_TEST_RUN_IDS` entries on the pre-allocation slot — without it, the triple-collision test seed would only force two real collisions before the third attempt fell through to normal random generation. Documented in `_generate_preflight_run_id`'s docstring. Production behavior is unchanged (both helpers use the wall clock + `secrets.token_hex` in the absence of the env var); only the test hook diverges.
- **`current_session_id` updates on every successful claude invocation.** Each iteration's claude response carries a `session_id`; the implementation overwrites the state's `current_session_id` with the new value. On resume, the resumed iteration uses `state["current_session_id"]` as `--resume <session_id>` to `claude -p`. Spec implies but does not pin "session id chain"; the implementation chose "latest known session" for forensic continuity. Pinned by `StateFilePersistenceTests.test_state_current_session_id_is_last_iter`.
- **`cumulative_input_tokens` / `cumulative_output_tokens` are accumulated from `usage.input_tokens + cache_read + cache_creation` and `usage.output_tokens` respectively.** ADR-0004's schema names the fields but doesn't pin the input-side aggregation; the chosen formula matches the slice 003-03 context-fill ratio computation (same denominator semantics) for consistency. Documented in the iteration body.
- **Atomic write contract uses `state.json.tmp` (not a random suffix per write).** ADR-0004 says "write to `state.json.tmp`, then `os.replace`"; the implementation matches literally. A concurrent loop run against the same `<run-id>` would race on the `.tmp` filename — but per ADR-0004's filesystem-only coupling + spec's "cross-run coordination is out of scope" framing, that's the user's problem to avoid (per-run-id directory isolation is the natural defense). No advisory lockfile is added.
- **`_invoke_claude` now accepts `session_id: Optional[str]` and passes `--resume <session_id>` when non-empty.** Spec implies but does not literally specify that within-loop iter 2+ also uses `--resume` (003-01's DoR said "session is carried across iterations by session_id only (slice 003-04 wires resume)"). The implementation interprets this as: ALL iterations after the first use `--resume <current_session_id>`, where the session updates each iteration. For fresh-run iter 1, `session_id` is empty → no `--resume`. For resumed-run iter N+1, `session_id` is the persisted value.
- **The pre-iter-1 interrupt branch dispatches on `history` (the persisted `oracle_score_history`).** When resuming a run that completed K iterations before being interrupted, then resumed and interrupted before iter K+1 starts, the `final_oracle_status` is the K-th iteration's status (not `unknown_interrupted`). Rationale: the K-th iteration WAS scored before the original interrupt; reporting `unknown_interrupted` would lose forensic signal. Pinned by code-level comments but not by an end-to-end test (would require a multi-step resume-then-interrupt scenario; acceptable spike-shape posture).
- **`oracle_score_history` carries `{iteration, composite, threshold, status}` per ADR-0004's literal schema.** No additional fields are written to history entries; the cumulative score history grows by one entry per gate-scored iteration. ADR-0004 flags the unbounded growth as a known cost (~80 bytes/entry × N iterations is well under a megabyte even at 10k iterations); no truncation logic was added.
- **AC1 verification path (`tear down with SIGTERM after iteration 2`) is satisfied in spirit by `SignalHandlingTests`, not literally by `StateFilePersistenceTests`.** The latter verifies the state file shape after a completed normal run; the former verifies the SIGTERM-during-iteration substrate (with `iteration_count=1` after a mid-iter-1 interrupt). The two together cover AC1's atomic-write-after-every-iteration contract; the literal "after iter 2" timing isn't pinned.

**Reviewer caveats (non-blocking):**
- The Popen-registration race (Popen → _active_subprocess assignment) is documented but not test-pinned. A test would have to inject a signal mid-`subprocess.Popen` call, which is inherently flaky. Acceptable for spike-shape.
- "First model with positive `contextWindow` wins" multi-model semantics from slice 003-03 carry forward unchanged; not re-litigated here.
- `_invoke_gate` does not pass `timeout=` to `communicate()` — gate.py's own internal timeout (per ADR-0002, 300s default + `SERVO_GATE_TIMEOUT`) is the brake. Acceptable; gate.py is co-located with loop.py and its timeout machinery is trusted.
- The "interrupt during gate.py" test uses a slow `oracle.sh` (sleep 3s) rather than slowing gate.py itself; this is enough to exercise the post-gate interrupt branch because gate.py is blocking on oracle.sh during that window. A direct slow-gate test would require either a fault-injected gate.py replacement or environment plumbing; not in scope here.
- Two unchecked spec close-out items remain (post-DONE work): the `docs/architecture.md` "Runtime artifacts" Agent-loop subsection (state-file schema reference) and the `.gitignore` guidance check. Both will land in the close-out commit after this reconciliation.

**Reviewer verdict:** PASS (independent review, `jig:reviewer` subagent, 2026-05-20). All 10 ACs implemented and exercised by the named test classes; ADR-0004 atomic-write contract holds (state at every iteration boundary via `.tmp + os.replace`); signal handler is allocation-light and defers writes to iteration boundaries; the `claude_version=None`/`None` resume case is explicitly designed not to trip mismatch; CLI shape validation correctly enforces `--resume-anyway` ⇒ `--resume` and `--prompt` required unless `--resume`. Reviewer's actionable recommendations addressed in-slice: (a) AC9 during-gate test added (`SignalHandlingDuringGateTests`), (b) `--prompt` override on resume test added (`test_resume_prompt_override_replaces_persisted`), (c) `_get_claude_version` migrated to Popen + `_active_subprocess` registration, (d) pre-iter-1 interrupt status switched to `unknown_interrupted`. 126/126 green post-fix; no regressions in `test_gate.py` / `test_scaffold.py` / either `test_skill_surface.py`.

---

## Slice 003-05 — stuck-loop-and-handoff

**STATUS: DONE**

**Goal:** Two final guardrails close the spec.

1. **Oracle-score plateau detection.** Halt the loop when the composite score does not improve over the last M iterations (default M=3). "Improvement" = strict greater-than. Halting on plateau prevents burning the rest of the budget on a clearly-stuck loop that won't converge.
2. **Subagent handoff.** Author full `agents/runner.md` and `agents/judge.md` prompts (currently placeholders); loop driver dispatches each iteration via `claude --agent <name> -p ...`. Each iteration's prompt is **assembled** by the driver from the seed prompt + the last oracle output + the last judge verdict. The runner produces work; the judge produces a structured verdict that feeds the next runner iteration.

End-to-end value: the spec's headline features are real — the loop halts cleanly on a stuck plateau, and the runner/judge roster is no longer placeholder. After this slice, `/servo:agent-loop` is shippable end-to-end.

**DoR:**
- ✅ Slice 003-04 DONE
- ✅ Spike verified `--agent <name>` flag exists on `claude -p` (corrected the initial research brief's false claim)
- ✅ Decision: plateau window default M=3. **Flagged in `docs/refinement-todo.md` for tuning** once real-world plateau data accumulates.
- ✅ Decision: per-iteration agent choice — runner and judge alternate, starting with runner. (Iteration 1: runner. Iteration 2: judge. Iteration 3: runner. Etc.) Configurable via `--agent-pattern` in a future refinement; today the alternation is hardcoded.
- ✅ Decision: `runner.md` and `judge.md` prompts are authored fresh, **not copied from jig's `implementer` / `reviewer`**. Per the existing placeholder files, jig's prompts assume supervised dev; servo's are unattended.

**Acceptance Criteria:**

1. **Plateau detection (default).** Three consecutive iterations with composite ≤ the highest score seen earlier → loop halts with `terminal_reason=oracle_plateau`, `plateau_window=3`, `oracle_score_history` in the summary. (Tested with a mock that emits the same composite for 3+ iterations.)
2. **Plateau detection (override).** `--plateau-window 5` requires 5 consecutive non-improving iterations.
3. **Plateau threshold semantics.** "Non-improving" means `composite ≤ max(prior_composites)`. Improvement = strict greater-than. Equality counts as non-improving. (Documented because the comparison direction is load-bearing.)
4. **Plateau detection (disable).** `--plateau-window 0` disables plateau detection entirely. (Same shape as the other `0` semantics for cost-ceiling / context-fill.)
5. **`runner.md` ships.** `agents/runner.md` is a real prompt that, given a target + last oracle output + last judge verdict, produces output ending with a fenced ```` ```verdict ```` block (per Clarifications Q7) carrying `schema_version: 1` (first field), `verdict: <one of CHANGES_MADE | NO_CHANGES | BLOCKED>`, optional `files_changed: <comma-separated paths>`, and `reasoning: <one-line summary>`. Placeholder banner removed. Prompt structure + block schema documented in the file body. Tested via mock-claude output that ends with the canonical block; `loop.py` parses the block and surfaces the parsed fields in the per-iteration JSON.
6. **`judge.md` ships.** `agents/judge.md` is a real prompt that, given a target + last runner output, produces output ending with a fenced ```` ```verdict ```` block carrying `schema_version: 1` (first field), `verdict: <one of PASS | FAIL | INCONCLUSIVE>`, `score: <float in [0.0, 1.0]>`, and `reasoning: <one-line summary>`. Placeholder banner removed. Output schema documented inline. The block parser shape is shared between `runner.md` and `judge.md` (single regex in `loop.py`); the `verdict:` field's allowed values differ by agent.
7. **Loop dispatch.** Each iteration invokes `claude --agent <runner|judge> -p ...` and captures the JSON. Agent alternation (runner → judge → runner → judge → ...) is verified by inspecting the args passed to the mock `claude` across iterations.
8. **Per-iteration prompt assembly.** The loop driver concatenates the seed prompt (from `--prompt <text>` or `--prompt-file <path>`) + the last `gate.py --json` output + the last judge verdict (if any) into a structured prompt block sent to the next agent. Format pinned in `loop.py` and documented in `runner.md` / `judge.md` so the agents know how to read it.
9. **SKILL.md surface (qa-wizard).** `skills/agent-loop/SKILL.md` exposes the loop to the LLM with trigger phrases ("run an agent loop", "iterate on this codebase", "head-less loop"), anti-greediness tests (does **not** fire on "score this code" → that's `/servo:quality-gate`), Q&A for the seed prompt / overrides, refusal-handling guidance. Surface tests under `skills/agent-loop/test_skill_surface.py`.
10. **Verdict-block `schema_version` enforced (ADR-0003).** The shared parser in `loop.py` extracts `schema_version` as the first key in every verdict block. Three refusal paths, each rc=2 with `reason=verdict_schema_mismatch` and a stderr breadcrumb naming the expected version (`1`) and the observed value: (a) field absent; (b) field present but ≠ 1 (e.g., `schema_version: 2`); (c) field present but wrong type (e.g., `schema_version: "1"` — string instead of int). The mismatch terminates the loop iteration the block belongs to; the loop's overall `terminal_reason` reflects the mismatch and the state file's `last_terminal_reason` captures it for resume forensics.

**DoD:**
- [x] All ACs pass; full test suite green (no regressions in `test_loop.py` slice-003-01..04 cases, `test_gate.py`, `test_scaffold.py`).
- [x] Test coverage per AC under `skills/agent-loop/test_loop.py`: AC1→`PlateauDetectionDefaultTests`, AC2→`PlateauWindowOverrideTests`, AC3→`PlateauThresholdSemanticsTests`, AC4→`PlateauDisabledTests`, AC5→`RunnerVerdictBlockTests`, AC6→`JudgeVerdictBlockTests`, AC7→`AgentAlternationDispatchTests`, AC8→`PromptAssemblyTests`, AC9→`skills/agent-loop/test_skill_surface.py`, AC10→`VerdictSchemaMismatchTests`.
- [x] Reviewed by `jig:reviewer` subagent.
- [x] Implementation review passed.
- [x] Deviation log produced under this slice heading.
- [x] Reconciliation review passed.
- [x] `docs/refinement-todo.md` updated (spike Q1/Q2/Q5/Q6 deferred for live-claude verification).

### Close-out (post-DONE)

- [x] **ADR-0003 Accepted.** (Already Accepted pre-implementation per `docs/architecture.md` "Decisions" table; this slice closes the prompt-authoring side of the ADR.)
- [x] SKILL.md anti-greediness tests pass (`python3 skills/agent-loop/test_skill_surface.py`).
- [x] `README.md` skills table row for `agent-loop` flipped to `Spec 003 — DONE`.
- [x] `docs/specs/README.md` status board: spec 003 → DONE.

**Anti-horizontal-phasing check:** After this slice, the user-facing surface is complete — typing a trigger phrase produces a real loop with all guardrails wired, a real subagent roster, and a parseable per-iteration log. This is the slice that closes the spec.

### Deviation log (after reconciliation)

**Slice 003-05 — implemented 2026-05-20.** 51 new tests under `skills/agent-loop/test_loop.py` (151 total) + 26 new tests under `skills/agent-loop/test_skill_surface.py`. Full regression sweep green across 6 suites (151 + 26 + 75 + 40 + 18 + 13 = 323 tests). Both `agents/runner.md` and `agents/judge.md` are authored prompts (previously placeholders) with verdict block schemas documented inline. Plateau detection, agent alternation, per-iteration prompt assembly, and verdict-block schema enforcement all wired into `loop.py`. `skills/agent-loop/SKILL.md` ships with anti-greediness surface tests; ADR-0003 already Accepted (pre-implementation framing) — this slice is the artifact-shipping side of that ADR.

Deviations from spec text and ADR-0003:

- **Lenient "no verdict block" parsing.** AC10 enumerates three refusal paths within a block that exists (field absent, ≠ 1, wrong type). `_parse_verdict_block` returns `(None, None)` when no fenced ```verdict``` block is present at all — treated as informational, not a refusal. The loop continues with `last_verdict=None`; the next iteration's prompt simply omits the verdict section. Rationale: an agent malfunction that produces narrative-only output is a soft failure (the loop can recover with the next runner), while a block-present-but-malformed verdict indicates a schema-incompatible agent that must terminate the run. Pinned by `VerdictSchemaMismatchTests.test_no_block_at_all_is_not_a_refusal`. ADR-0003 doesn't pin the "no block" case explicitly; the lenient interpretation is the more conservative one (refusing on missing-block could break any future agent revision that intentionally suppresses the block, e.g., a "thinking-only" pass).
- **Empty-block rejection added as an implicit fourth refusal path.** A fenced ```verdict``` block with no non-empty lines is rejected with breadcrumb `"verdict block is empty"`. AC10's "field absent" reading covers this implicitly (a block can't satisfy "schema_version as the first key" if there are no keys), but the literal AC text doesn't enumerate this sub-case. Pinned by `ParseVerdictBlockUnitTests.test_empty_block_is_an_error`.
- **Per-iter verdict fields are surfaced as raw strings, except `schema_version` (always cast to `int`).** AC10 only type-enforces `schema_version`. Other fields — `score` (judge), `files_changed` (runner) — pass through as strings (`"0.85"`, `"a.py, b.py"`). The judge prompt declares `score` as a float in `[0.0, 1.0]` but the parser doesn't enforce the range or cast. Documented for the spec 005 race driver, which will need to parse `score` as float and clip to range if it weights variants by judge confidence.
- **`AGENT_RUNNER` / `AGENT_JUDGE` constants and hardcoded alternation.** Iter 1=runner, iter 2=judge, iter 3=runner, etc. Per the slice DoR: "Configurable via `--agent-pattern` in a future refinement; today the alternation is hardcoded." No `--agent-pattern` flag in this slice. Pinned by `AgentAlternationDispatchTests`.
- **Per-iter JSON adds an `agent` field beyond the spec's literal field list.** AC7's text says the alternation is "verified by inspecting the args passed to the mock `claude`." The implementation additionally surfaces the agent name in each per-iter JSON line under key `agent`. Additive; downstream consumers can group lines by role without re-deriving from iteration parity. Pinned by `AgentAlternationDispatchTests.test_per_iter_json_carries_agent_field`.
- **`oracle_score_history` is emitted in every summary line, not just on `oracle_plateau` halts.** AC1's text names `oracle_score_history` in the plateau-halt summary. The implementation includes it on every summary path (matches the slice 003-04 pattern of "summary fields are present uniformly across all halt paths"). Mildly verbose but consistent. Forensic readers get the full history regardless of halt reason.
- **`plateau_window` is emitted in every summary line.** Same generalization as `oracle_score_history`: present even when the plateau brake didn't fire. Spec AC1 lists `plateau_window` as a required field on the `oracle_plateau` halt; emitting it universally is additive.
- **`_assemble_iteration_prompt` adds `Context from prior iteration:` framing header and `---` delimiters.** AC8 says "concatenates the seed prompt + the last `gate.py --json` output + the last judge verdict (if any) into a structured prompt block." The specific framing characters (`---` lines, "Context from prior iteration:" header) are implementation choices, not spec-pinned. Documented in `agents/runner.md` / `agents/judge.md` so the agents know how to read the prompt. Pinned by `PromptAssemblyTests.test_iter_two_prompt_includes_oracle_and_verdict`.
- **`session_id` chain: all iter 2+ invocations use `claude -p --resume <current_session_id>` carrying the most recently observed session.** Slice 003-04 introduced the resume mechanism; slice 003-05 reuses it for in-run iteration continuity (each iteration's response updates `current_session_id`). The spec's slice 003-04 wording is ambiguous about whether within-run iterations carry session; this slice commits to "yes, always" (mirrors the assumption that conversation continuity across iters is desirable). No additional tests added in 003-05 beyond what 003-04 covered.
- **Verdict-block last-match semantics for multi-block agents.** When `_VERDICT_BLOCK_RE.finditer` returns multiple matches, the LAST is parsed. Agent prompts say "the block must be the final content"; the parser is lenient about intermediate blocks. Pinned by `ParseVerdictBlockUnitTests.test_multiple_blocks_last_wins`.
- **Test infrastructure: `_run_loop` defaults `--plateau-window 0` unless the caller passes it.** Legacy 003-01..04 tests use constant-composite mocks that would otherwise trip the default plateau brake at iter 4 instead of running to the test's expected iteration count. Plateau-specific tests opt back in by passing their own `--plateau-window N`. This is purely a test-suite adjustment; production CLI default remains 3 via `DEFAULT_PLATEAU_WINDOW`. Documented in `_run_loop`'s docstring.
- **Test infrastructure: args-log delimiter scheme.** Slice 003-05's multi-line iteration prompts caused the prior `echo "$*"` mock to fragment a single invocation across multiple log lines. The new format uses U+001F (Unit Separator) between args and U+001E (Record Separator) between invocations, so embedded newlines in the prompt no longer confuse `_read_args_log`. Updated `_mock_claude_with_args_log` and `_mock_claude_costs_per_iter` to write the new format; `_read_args_log` parses on the new delimiters.
- **Test infrastructure: triple-backtick Unicode escaping.** The verdict block contains triple backticks. Bash unquoted heredocs trigger command substitution on backticks. To avoid this, test helpers encode triple backticks as ````` in the JSON `result` field; Python's `json.loads` in loop.py decodes them back to literal backticks before the verdict parser sees the block. `_BTICK = "\\u0060\\u0060\\u0060"`. Documented at the constant definition.

**Reviewer caveats (non-blocking):**
- `score` validation: a buggy judge that emits `score: 1.5` (outside `[0.0, 1.0]`) is accepted by the parser. Spec 005's race driver will likely want to clip; could optionally pin a `score`-range check in a future tightening.
- `files_changed` conditional shape: AC5 says it's optional when `verdict: CHANGES_MADE`. The parser doesn't enforce "files_changed must be absent on NO_CHANGES / BLOCKED." Acceptable — the runner prompt is the contract.
- Renderer of last-verdict back into the prompt (`_assemble_iteration_prompt`): if a future field is added to the verdict block (e.g., `confidence`), the renderer at `loop.py:355-358` will round-trip it correctly because it iterates the parsed dict. Documented for clarity.
- The slice description in spec.md's slice 003-05 text says "(iter 3+)" for the runner-reading-judge-verdict case; the implementation includes oracle+verdict on iter 2+ whenever EITHER is non-None. The "judge verdict absent until iter 3" framing in `agents/runner.md` is descriptive (iter 1=runner sees nothing; iter 2=judge sees iter-1 runner output; iter 3=runner sees iter-2 judge verdict).

**Reviewer verdict:** PASS (independent review, `jig:reviewer` subagent, 2026-05-20). All 10 ACs implemented and exercised by the named test classes per the DoD mapping. Plateau detection arithmetic correctly implements the spec's "≤ counts as non-improving" wording (`_check_plateau` at `loop.py:392-419`); verdict parser handles all three AC10 refusal paths with distinct breadcrumbs; agent alternation, prompt assembly, and `--agent` argv dispatch are all verified end-to-end; `agents/runner.md` and `agents/judge.md` are real prompts with their verdict block schemas documented inline; `SKILL.md` satisfies the anti-greediness pattern (positive triggers in scope, negative triggers excluded, sibling skills referenced, no-silent-retry guidance present). Twelve documented deviations from spec text — all non-blocking, all in the deviation log above.

---

## Spec-level Definition of Done

- [x] All five slices DONE (003-01 invoke-loop, 003-02 cost-ceiling, 003-03 context-fill-gate, 003-04 checkpoint-resume, 003-05 stuck-loop-and-handoff) — each reviewed by `jig:reviewer` subagent.
- [x] End-to-end dogfood (three scenarios) — covered by `EarlyHaltOnOracleTests` (convergence), `IterationCapDefaultTests` / `IterationCapOverrideTests` (iteration-cap), `ResumeFlowTests` (resume preserving cumulative cost / oracle history / session id).
- [x] [README.md](../../../README.md) skills table: `agent-loop` row reads `DONE`.
- [x] `docs/architecture.md` "Runtime artifacts" section adds an Agent-loop subsection documenting the state-file schema (referencing ADR-0004). The "Open questions" entry "agent-loop driver: shell vs Python" is resolved (Python; landed at slice 003-04 close-out).
- [x] Two ADRs recorded:
  - **ADR-0003** — Why a fresh subagent roster, not reused from jig (Accepted; this slice ships the runner + judge prompts).
  - **ADR-0004** — Servo's per-run state-file shape; filesystem-only coupling with Claude Code's session JSONL (Accepted at 003-04 close-out).
- [x] [docs/specs/README.md](../README.md) status board reflects DONE.
- [x] All six open questions from [spike.md](spike.md) "Open questions" are either resolved in the spec or moved to `docs/refinement-todo.md` with a resolution trigger. (Q3/Q4 resolved in-spec; Q1/Q2/Q5/Q6 deferred to `docs/refinement-todo.md` for live-claude empirical verification.)

## Critical files (when implementation starts)

In servo (already shipped by specs 001 + 002):
- `skills/scaffold-init/scaffold.py` — manifest schema source; loop.py reads it via gate.py
- `skills/quality-gate/gate.py` — the truth-source the loop invokes after every iteration (per ADR-0002)
- `docs/decisions/adr-0002-gate-caller-contract.md` — closed exit codes + JSON schema_version contract the loop relies on
- `templates/oracle.sh.template` — the contract source

In jig (reference patterns):
- `skills/tdd-loop/tdd.py` — counted-loop + structured-output pattern (mirror for 003-01)
- `skills/scaffold-init/SKILL.md` — Q&A surface pattern for 003-05

In this spec (to be created):
- `skills/agent-loop/loop.py` — new in 003-01, extended each slice
- `skills/agent-loop/test_loop.py` — new in 003-01, extended each slice
- `skills/agent-loop/SKILL.md` — new in 003-05
- `skills/agent-loop/test_skill_surface.py` — new in 003-05
- `agents/runner.md` — authored at 003-05 (placeholder replaced)
- `agents/judge.md` — authored at 003-05 (placeholder replaced)
- `docs/decisions/adr-0003-fresh-subagent-roster.md` — Accepted at 003-05
- `docs/decisions/adr-0004-session-state-file-format.md` — Accepted at 003-04

## Clarifications

> Q1–Q6 carry forward from the [spike](spike.md) and name the slice + verification path for each. Q7–Q10 were resolved 2026-05-18 via `/jig:clarify` and have been folded into the relevant slices (see the body sections referenced in each answer).

### Q1: `terminal_reason` taxonomy from `claude -p` JSON output

_(category: Edge Cases & Failure Modes; needed by slice 003-02)_

**Question:** The spike captured `terminal_reason="completed"` on the success path. What are the other values? `budget_exceeded`, `error`, `interrupted`, `timeout`? Slice 003-02 (cost-ceiling) needs to assert the exact string `claude -p` emits when `--max-budget-usd` is hit so the loop driver can map it to its own `terminal_reason=cost_ceiling_reached` (or pass it through verbatim).

**Verification:** Empirical — `claude -p "loop infinitely please" --max-budget-usd 0.001 --output-format json | jq '.terminal_reason'` before writing slice 003-02 ACs.

### Q2: `stop_reason` taxonomy

_(category: Edge Cases & Failure Modes; needed by slice 003-05)_

**Question:** The spike captured `stop_reason="end_turn"`. The Anthropic API docs name `max_tokens`, `tool_use`, `stop_sequence`, `pause_turn`. Which surface to the JSON output of `claude -p`? Less load-bearing than `terminal_reason` but informs the structured-summary slice 003-05 emits per iteration (so the per-iteration JSON line carries actionable diagnostics).

**Verification:** Empirical, during slice 003-05 implementation. Document the observed values; the rest can stay in the refinement-todo.

### Q3: Stream-JSON vs single-result-JSON semantics

_(category: Non-functional Requirements; tentatively answered)_

**Question:** `--output-format stream-json` emits multiple events; cost / usage may arrive at end or per-event. Spec 003 will probably stick with single-result JSON (one invocation = one summary line) but worth confirming once an iteration includes meaningful tool use.

**Tentative answer:** **Single-result JSON.** The loop driver wants one summary per iteration; stream-JSON would force per-event accounting in the loop driver that single-result already aggregates. Verify during slice 003-01 implementation that single-result JSON includes complete `usage` + `modelUsage` blocks after a multi-turn iteration; if it doesn't, switch to stream-JSON.

### Q4: Session JSONL portability

_(category: Scope & Boundaries; resolved out of scope)_

**Question:** Are session IDs portable across Claude Code versions / machines? Spec 003's checkpoint/resume contract says "across invocations" — does that include across machine reboots? Across `claude` version upgrades?

**Resolution:** **Within-machine, within-claude-version only.** The state file captures `claude_version` (slice 003-04 AC #2); resume refuses (rc=2 / `claude_version_mismatch`) when current version differs. `--resume-anyway` escapes the refusal. Cross-machine portability is out of scope (per Out-of-scope above). The spec's "across invocations" promise means "across `loop.py` invocations on the same machine, with the same claude binary."

### Q5: `--max-budget-usd` halt granularity

_(category: Edge Cases & Failure Modes; needed by slice 003-02)_

**Question:** Does `claude -p --max-budget-usd X` stop *before* the next API call would exceed the budget (clean halt), or partway through with a partial response? Affects whether the loop driver can rely on `total_cost_usd` being ≤ the budget on the budget-exhausted exit path.

**Verification:** Empirical, during slice 003-02 implementation. The loop's per-iteration safety doesn't actually depend on the answer (cumulative tracking handles it either way) but the per-iteration `--max-budget-usd` defense-in-depth needs to know whether to set the floor at `remaining_budget` or `remaining_budget * 0.9` (conservative).

### Q6: `--agent <name>` + permissions inheritance

_(category: Edge Cases & Failure Modes; needed by slice 003-05)_

**Question:** Does invoking `claude --agent runner -p "..."` inherit the parent shell's `--allowedTools` / `--disallowedTools`, or is the agent's own `tools:` frontmatter authoritative? Slice 003-05 (subagent dispatch) needs to know what `runner` can actually do when servo's loop spawns it.

**Verification:** Empirical, during slice 003-05 implementation. Document the observed behavior in `runner.md` / `judge.md` frontmatter so future agent authors know the constraint model.

### Q7: What output schema should runner and judge subagents produce so the loop driver can parse them reliably (slice 003-05 AC#5/#6)?

_(category: Acceptance Criteria Testability)_

**Structured markdown block.** Agents end output with a fenced ```` ```verdict ... ``` ```` block containing key:value fields (e.g., `verdict: PASS`, `score: 0.85`, `reasoning: ...`). Compromise between human-readable narrative and machine-parseable signal — matches the natural shape of LLM output without forcing the agent to emit pure JSON.

**Folded into:** slice 003-05 AC #5 and #6 are tightened to specify the fenced-block format and the required field set. The exact parser regex pins in `loop.py` during 003-05 implementation; the agent prompts (`runner.md` / `judge.md`) document the block shape for future authors. ADR-0003 captures the output-schema decision alongside the prompt-divergence rationale (unattended vs supervised).

### Q8: When `claude -p` itself fails (claude binary not on PATH, network error, invalid JSON output), what should the loop driver do?

_(category: Edge Cases & Failure Modes)_

**Uniform rc=2 / `claude_invocation_failed`.** All `claude -p` invocation failures map to rc=2 with `reason=claude_invocation_failed`; stderr breadcrumb names the specific cause (binary-missing, network, parse). Matches gate.py's consolidate-env-errors pattern from [ADR-0002](../../decisions/adr-0002-gate-caller-contract.md).

**Folded into:** slice 003-01 AC #4 extends its preflight refusal taxonomy to name `claude_invocation_failed` as a new closed-set reason. Slice 003-04 state-file persists `last_terminal_reason=claude_invocation_failed` for forensics on resume.

### Q9: When the user interrupts `loop.py` mid-iteration (Ctrl-C / SIGTERM), what should happen?

_(category: Edge Cases & Failure Modes)_

**Trap signal → finalize state → write summary → exit.** Catch SIGINT/SIGTERM, persist current `state.json` atomically, emit final summary line with `terminal_reason=interrupted`, exit 130. Best forensics for unattended use; user reading state.json + stdout knows exactly what happened.

**Folded into:** slice 003-04 adds AC #9 covering the signal-handling contract. If the signal arrives during the gate.py invocation (after `claude -p` completes but before scoring), the iteration is treated as completed for state-file purposes but the summary line's `final_oracle_status` is `unknown_interrupted`.

### Q10: What happens if two `loop.py` instances run against the same `<target>` simultaneously?

_(category: Non-functional Requirements)_

**Run-id isolation is enough.** Each instance gets its own `<target>/.servo/runs/<run-id>/`; no global lock. Side effects on target files (oracle.sh outputs, gate.py results, target-side mutations from `claude -p`) are the user's concern. Matches the per-run-id directory pattern already pinned in slice 003-04; lets spec 005 race driver run parallel loops cleanly (each variant has its own worktree, so the targets diverge anyway).

**Folded into:** the Out-of-scope section is extended with "cross-run coordination / locking / mutex on the target filesystem." If concurrent-run footguns surface in real use, a future refinement-todo entry can add an advisory lockfile.

### Coverage summary

| Category | Status |
|---|---|
| Scope & Boundaries | Clear |
| Acceptance Criteria Testability | Resolved (Q7 pinned runner/judge output schema) |
| Dependencies & Blockers | Clear (specs 001 + 002 DONE; ADR-0002 Accepted) |
| Non-functional Requirements | Resolved (Q10 pinned concurrent-run posture) |
| Edge Cases & Failure Modes | Partial (Q8 + Q9 resolved; Q1, Q2, Q5, Q6 await empirical verification at their slices) |
| Terminology Consistency | Clear (terms align with spike.md + spec 002) |

After the 2026-05-18 `/jig:clarify` pass, four of the six categories are Clear or Resolved; Edge Cases & Failure Modes remains Partial because four spike-surfaced questions (Q1, Q2, Q5, Q6) still require empirical verification against `claude -p` during their respective slices. The spec is **READY_FOR_REVIEW** at the spec-overview level and **READY_FOR_IMPLEMENTATION on slice 003-01** without further clarification — slice 003-01's spike-shape posture is the planned escape hatch if empirical observations contradict assumptions.
