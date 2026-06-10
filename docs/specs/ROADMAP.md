# Servo spec roadmap

> Planned specs and the jig-gap inventory. Moved out of the status board
> (`docs/specs/README.md`) so `workflow.py status-board` can own that
> file's table without destroying this hand-maintained content.

## Planned specs

Descriptions name the cross-cutting AI-native concerns each spec
addresses — not just the skill it ships — so the gap inventory stays
visible during spec authoring.

| Spec | Description |
|---|---|
| [004-oracle-hook](004-oracle-hook/spec.md) | Claude Code hook installer (idempotent install/uninstall/status). Installs a **meta-judge `Stop` hook** that grades every assistant turn against the scaffolded oracle and feeds back a **structured retry hint** (block + reason) — the deterministic replacement for ad-hoc transcript-regex scans. Fails **open** so a broken oracle never traps a session. |
| 005-variant-race | N-worktree parallel race with quality-gate scoring and winner selection. Owns worktree-race coordination, variant-lease management, and winner promotion (the unattended cousin of jig's parallel-spec-number reservation). |
| [008-eval-authoring](008-eval-authoring/spec.md) | **DRAFT scope-capture, parked.** Human-in-the-loop front-end that turns an eval-able `residual_judgment` AC into an [ADR-0005](../decisions/adr-0005-eval-oracle-component.md) frozen eval component: triage, rubric shaping, statistical reference-set collection, and frozen `n`/`δ`/threshold/judge-model — then hands off to `/servo:spec-oracle`. Activates on the first real EDD spec (same trigger as ADR-0005). |

Sequencing rationale: 001 is the foundation everything else depends
on; 003 before 005 because race reuses loop primitives; 004 is
parallelizable with 003 (depends only on 001). 008 is parked behind the
first real EDD spec and depends on 006 + ADR-0005.

## How these specs close jig's long-running-session gaps

Servo's planned specs intentionally close the gaps that surface when an
agent runs without a human — gaps that jig's supervised workflow doesn't
need to solve at the same severity. Source: 2026-05-18 AI-native review
of jig.

| Gap surfaced in jig review | Servo home | Notes |
|---|---|---|
| Context-fill hard refusal gate | 003-agent-loop | Hard refusal; jig keeps a soft warning in `jig-context-check.sh` |
| Session checkpoint / resume across invocations | 003-agent-loop | On-disk state at `<target>/.servo/runs/<run-id>/state.json` (ADR-0004) |
| Stuck-loop detection | 003-agent-loop | Oracle-score-plateau heuristic |
| Token / cost ceiling enforcement | 003-agent-loop | Hard guardrail (defaults: max-iterations=5, cost-ceiling=$2 per architecture.md) |
| Subagent handoff state across iterations | 003-agent-loop | What `runner` / `judge` receive each spawn, what survives |
| `Stop`-hook grading (oracle-scored, structured retry hints) | 004-oracle-hook | The original meta-judge pattern; structured replacement for ad-hoc Stop-hook regex |
| Worktree-race coordination + winner selection | 005-variant-race | Variant-lease pattern; same family as jig's spec-number reservation but for ephemeral worktrees |
| Spec-specific judging | 006-spec-oracle | Turns acceptance criteria into deterministic evidence overlays so loops optimize against the spec, not just the baseline suite |
| Install surface drift | 007-install-surfaces | Two install layers kept distinct — *servo runtime install* (plugin root / release zip / project-local `.claude/` scaffold) vs *project oracle install* (`/servo:scaffold-init` → `oracle.sh` + `.servo/install.json`). All three runtime surfaces share one data-driven contract (`.claude-plugin/install-contract.json`) and one verifier (`scripts/verify_install.py`); `scripts/verify_install_surfaces.sh` runs them in CI |

Gaps that stay with jig (primer-doc hygiene, supervised slice-level drift
detection, parallel-worktree spec-numbering, memory-recall, PostToolUse
edit verification) are tracked in jig's own spec series and refinement-todo.
