---
status: IN_PROGRESS
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
| 003-06 | goal-driven-loop | **(ADR-0008 rebase)** `/goal`-driven continuation alongside the hand-rolled loop; loop body prints the `SERVO_ORACLE_VERDICT` sentinel, `/goal` fact-checks it, hard caps (`--max-turns` + `--max-budget-usd`) on the outer call, final `gate.py` is authority. |
| 003-07 | portable-guardrails | **(ADR-0008 rebase)** Vendor `gate.py` (clone-portability); `refuse-on-dirty-tree` preflight; host-scope routing (primitives vs external driver). |
| 003-08 | detach-and-schedule | **(ADR-0008 rebase)** `/background` detachment + Routine-ready target; `gate.py`-authority in Routines (meta-judge moot per V4). |

Five slices, sized to match the spec 001 / 002 cadence. The vertical-value rule still applies — after every slice the loop driver is end-to-end usable on its own.

**Amendment (2026-06-12):** slices 003-06..08 add the **ADR-0008 rebase phase** (see [## Amendments](#amendments)). The original five slices (003-01..05) remain DONE and are **retained as the external-driver / portable layer**; they are not invalidated.

---

## Slices

- [003-01 — invoke-loop](slice-01-invoke-loop.md)
- [003-02 — cost-ceiling](slice-02-cost-ceiling.md)
- [003-03 — context-fill-gate](slice-03-context-fill-gate.md)
- [003-04 — checkpoint-resume](slice-04-checkpoint-resume.md)
- [003-05 — stuck-loop-and-handoff](slice-05-stuck-loop-and-handoff.md)
- [003-06 — goal-driven-loop](slice-06-goal-driven-loop.md) — DRAFT (ADR-0008 rebase)
- [003-07 — portable-guardrails](slice-07-portable-guardrails.md) — DRAFT (ADR-0008 rebase)
- [003-08 — detach-and-schedule](slice-08-detach-and-schedule.md) — DRAFT (ADR-0008 rebase)


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

---

## Amendments

### 2026-06-12 — ADR-0008: rebase orchestration onto Claude Code autonomy primitives

[ADR-0008](../../decisions/adr-0008-loop-on-autonomy-primitives.md) (Accepted
2026-06-12) reframes agent-loop's architecture. Since this spec shipped, Claude
Code shipped autonomy primitives — `/goal` (across-turn continuation),
`/background` (detached sessions), Routines (scheduled unattended runs) — that
overlap the hand-rolled driver. The decision: **delegate continuation /
detachment / scheduling / turn-capping to the primitives where available, and
keep servo's deterministic guardrail + oracle layer as the sole value-add.**
Implemented by new DRAFT slices **003-06..08** (added to the slice index above).

**What changes (new slices):**

- **003-06 goal-driven-loop** — a `/goal`-driven continuation mode alongside the
  hand-rolled loop. The loop body runs `servo:quality-gate` and prints a
  `SERVO_ORACLE_VERDICT` sentinel; the `/goal` condition only *fact-checks* it; a
  **final `gate.py` run is the authority**. `oracle.sh` is never replaced by
  `/goal`'s transcript judge (hard constraint).
- Hard caps move to the **outer** invocation: `--max-budget-usd` (cost ceiling)
  AND `--max-turns` (iteration cap) — both **verified to bind a `/goal` run**
  (ADR-0008 V2).
- **003-07 portable-guardrails** — vendor `gate.py` into the target
  (clone-portability, V4); `refuse-on-dirty-tree` preflight (scheduled-run
  state-pollution, V4); host-scope routing (V3).
- **003-08 detach-and-schedule** — `/background` + Routine-ready targets; in a
  Routine (continuous invocation) `gate.py` is the authority — the meta-judge
  `Stop` hook is moot there (V4).

**What does NOT change:**

- **The five DONE slices (003-01..05) are retained, not invalidated.** The
  hand-rolled `loop.py` driver becomes the **external-driver / portable layer** —
  the supported path for hook-restricted environments and **non-Claude-Code
  hosts (e.g. Codex)**, where the primitives don't exist and hooks are blocked by
  default (ADR-0008 Assumption 7, V3). It is demoted from default to one of two
  first-class paths, not removed.
- The `gate.py` `0/1/2` exit-code contract (ADR-0002) and `oracle.sh`'s authority
  are unchanged.

**Correction of record — "Pre-spec research" / spike.** That section states "no
`--max-turns` flag exists." ADR-0008 verification (claude 2.1.142 + 2.1.175)
found `--max-turns` **is** a real, runtime-enforced flag — merely **hidden from
`claude --help`** (confirmed by an acceptance probe vs. a bogus-flag control: it
halts a run with `error_max_turns` at the cap and binds a `/goal` run). The
original prose is **preserved above** per
[ADR-0010](../../decisions/adr-0010-amendment-scope-records-vs-live-prose.md)
(closed-spec records are amended, not rewritten); this note is the correction.

**Cross-spec follow-up (not a 003 slice):** repositioning the meta-judge (spec
004 / ADR-0006) as the *interactive-only* backstop — since it does not fire in a
continuous-invocation Routine — is tracked as an amendment to **spec 004**, which
owns the meta-judge deliverable.

**Verification harness:** the V1–V4 probes backing this rebase live at
[`docs/decisions/adr-0008-experiments/`](../../decisions/adr-0008-experiments/).
