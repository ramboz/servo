# Specs

Status board for servo's spec-driven development. Each spec lives in `NNN-<name>/spec.md` with vertical slices and a state lifecycle: `DRAFT → READY_FOR_REVIEW → READY_FOR_IMPLEMENTATION → IN_PROGRESS → REVIEWED → RECONCILED → DONE`.

## Active specs

| Spec | Status | Description |
|---|---|---|
| [001-scaffold-init](001-scaffold-init/spec.md) | **DONE** | Probe target signals, run Q&A, drop tailored `oracle.sh` (+ optional Tier-1/2 stubs) into target |
| [002-quality-gate](002-quality-gate/spec.md) | **DONE** | Runtime invocation of scaffolded `oracle.sh`; normalized exit codes (0 = ≥threshold, 1 = <threshold, 2 = env error). The truth-source every other servo runtime skill depends on. |

## Planned specs

Descriptions name the cross-cutting AI-native concerns each spec addresses —
not just the skill it ships — so the gap inventory stays visible during
spec authoring.

| Spec | Description |
|---|---|
| 003-agent-loop | Headless iteration driver. Hard guardrails: **iteration cap**, **cost / token ceiling**, **context-fill refusal gate** (refuses next iteration once context window exceeds N% — the hard-gate cousin of jig's soft `jig-context-check.sh` warning), **checkpoint/resume** across invocations, **stuck-loop detection** (no oracle-score improvement over M iterations → halt). Owns the subagent-handoff state machine across iterations: what context each spawn receives, what it returns, what survives. |
| 004-oracle-hook | Claude Code hook installer (idempotent install/uninstall/status). Installs a **meta-judge `Stop` hook** that grades every assistant turn against the scaffolded oracle and emits retry hints as `additionalContext` — the structured replacement for ad-hoc transcript-regex scans. |
| 005-variant-race | N-worktree parallel race with quality-gate scoring and winner selection. Owns worktree-race coordination, variant-lease management, and winner promotion (the unattended cousin of jig's parallel-spec-number reservation). |

Sequencing rationale: 001 is the foundation everything else depends on; 003 before 005 because race reuses loop primitives; 004 is parallelizable with 003 (depends only on 001).

## How these specs close jig's long-running-session gaps

Servo's planned specs intentionally close the gaps that surface when an
agent runs without a human — gaps that jig's supervised workflow doesn't
need to solve at the same severity. Source: 2026-05-18 AI-native review
of jig.

| Gap surfaced in jig review | Servo home | Notes |
|---|---|---|
| Context-fill hard refusal gate | 003-agent-loop | Hard refusal; jig keeps a soft warning in `jig-context-check.sh` |
| Session checkpoint / resume across invocations | 003-agent-loop | On-disk state at `<target>/.servo/runs/<run-id>/`; format decided at 003 authoring (candidate ADR) |
| Stuck-loop detection | 003-agent-loop | Oracle-score-plateau heuristic |
| Token / cost ceiling enforcement | 003-agent-loop | Hard guardrail (defaults: max-iterations=5, cost-ceiling=$2 per architecture.md) |
| Subagent handoff state across iterations | 003-agent-loop | What `runner` / `judge` receive each spawn, what survives |
| `Stop`-hook grading (oracle-scored, structured retry hints) | 004-oracle-hook | The original meta-judge pattern; structured replacement for ad-hoc Stop-hook regex |
| Worktree-race coordination + winner selection | 005-variant-race | Variant-lease pattern; same family as jig's spec-number reservation but for ephemeral worktrees |

Gaps that stay with jig (primer-doc hygiene, supervised slice-level drift
detection, parallel-worktree spec-numbering, memory-recall, PostToolUse
edit verification) are tracked in jig's own spec series and refinement-todo.
