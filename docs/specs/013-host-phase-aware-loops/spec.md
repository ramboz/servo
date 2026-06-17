---
status: DRAFT
dependencies: [003, 006, 012]
last_verified: 2026-06-17
---

# Spec 013 - host-phase-aware servo loops

> Parked follow-up to [ADR-0011](../../decisions/adr-0011-host-native-phase-hints.md):
> let servo consume host-native planning / implementation phases as advisory
> hints while keeping `gate.py`, `oracle.sh`, run state, triage state, and
> frozen eval ledgers authoritative.

## Overview

Servo's loop machinery is already split between host autonomy and deterministic
authority. [ADR-0008](../../decisions/adr-0008-loop-on-autonomy-primitives.md)
lets Claude Code own `/goal`, `/background`, and Routines where available, but
keeps the external driver and `gate.py` as the portable control plane. A new
jig direction - mode-aware but not mode-dependent host adapters - creates a
parallel opportunity for servo:

- plan before spending loop budget;
- run implementation turns under the host's implementation/editing rhythm;
- evaluate with the judge or frozen design-eval component;
- triage heartbeat candidates without dispatching every discovered signal.

This spec is intentionally parked. It records the shape now so the idea is not
lost, but it should not start until there is a concrete consumer: a jig
host-mode adapter, a second design-eval project, or repeated servo-loop
friction where users need an explicit plan/run/evaluate split.

## Assumptions

- Servo's authority boundaries are unchanged: `gate.py` and project-owned
  `oracle.sh` decide pass/fail/env-error; state files record loop and triage
  truth.
- Exact Codex and Claude phase-mode behavior must be re-verified when work
  resumes. This spec records intent, not current product API guarantees.
- Missing host-mode support must remain a graceful degradation path, not an
  environment error.

## Decomposition

SPIDR - primarily **Interface** plus **Rules**:

- **Interface:** phase hints may arrive from Claude, Codex, jig-generated
  prompts, or servo-specific command flags.
- **Rules:** hints may shape prompting/dispatch, but never replace oracle
  authority or state-file contracts.

No spike is needed yet. Each deferred slice begins with a verification step
for the current host surfaces.

## Slices

- [013-01 - phase-hint contract](slice-01-phase-hint-contract.md)
- [013-02 - agent-loop adapter hints](slice-02-agent-loop-adapter-hints.md)
- [013-03 - design-eval and heartbeat guidance](slice-03-design-eval-and-heartbeat-guidance.md)
