# Specs

Status board for servo's spec-driven development. Each spec lives in `NNN-<name>/spec.md` with vertical slices and a state lifecycle: `DRAFT → READY_FOR_REVIEW → READY_FOR_IMPLEMENTATION → IN_PROGRESS → REVIEWED → RECONCILED → DONE`.

## Active specs

| Spec | Status | Description |
|---|---|---|
| [001-scaffold-init](001-scaffold-init/spec.md) | **DONE** | Probe target signals, run Q&A, drop tailored `oracle.sh` (+ optional Tier-1/2 stubs) into target |

## Planned specs

| Spec | Description |
|---|---|
| 002-quality-gate | Runtime invocation of scaffolded `oracle.sh`; normalized exit codes |
| 003-agent-loop | Headless iteration driver (iteration cap, cost ceiling, checkpoint/resume) |
| 004-oracle-hook | Claude Code hook installer (idempotent install/uninstall/status) |
| 005-variant-race | N-worktree parallel race with quality-gate scoring and winner selection |

Sequencing rationale: 001 is the foundation everything else depends on; 003 before 005 because race reuses loop primitives; 004 is parallelizable with 003 (depends only on 001).
