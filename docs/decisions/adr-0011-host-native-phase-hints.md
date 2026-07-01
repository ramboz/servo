---
status: Accepted
date: 2026-06-17
deciders: ramboz
supersedes:
superseded-by:
last_verified: 2026-07-01
---

# ADR-0011: Host-native phase hints stay advisory under servo's oracle authority

## Status

Accepted (2026-07-01)

## Context

Servo orchestrates autonomous coding loops by keeping deterministic authority
outside the LLM host: `gate.py` invokes the project-owned `oracle.sh`, loop
state is written under `.servo/runs/`, and heartbeat triage state is written
under `.servo/triage/`. [ADR-0008](adr-0008-loop-on-autonomy-primitives.md)
already rebased part of the loop onto Claude Code autonomy primitives
(`/goal`, `/background`, Routines), but kept `gate.py` as the authority and
kept the external-driver path for hosts where Claude-specific primitives are
not available.

A parallel jig design discussion on 2026-06-17 raised whether jig should make
better use of host-native planning and implementation modes in Codex and
Claude. The proposed jig posture is "mode-aware, not mode-dependent": host
modes can improve the interaction shape, but specs, slices, ADRs, and review
evidence remain the durable workflow truth.

Servo has the same issue through a different lens. Host modes could make servo
loops safer and clearer:

- plan before spending loop budget;
- implement during the runner phase;
- evaluate with the judge / design-eval phase;
- keep heartbeat discovery and dispatch from blurring into one long
  self-directed run.

But servo's value is the opposite of trusting the host transcript: the oracle
and state files are the record. If host mode state becomes authoritative,
servo inherits a host-specific, non-portable control plane.

## Decision

Servo may consume host-native phase modes only as **advisory adapter hints**.
They may shape prompts, command guidance, and host-specific dispatch behavior,
but they do not replace or weaken servo's existing authority surfaces.

Concretely:

1. **`gate.py` and `oracle.sh` remain authoritative.** A host claiming to be in
   planning, implementation, or evaluation mode never counts as pass/fail
   evidence. The oracle result is still the pass/fail/env-error contract.
2. **State files remain canonical.** `.servo/runs/<run-id>/state.json`,
   `.servo/triage/inbox.jsonl`, and any frozen eval ledgers remain the durable
   record. Host mode state is not serialized as workflow truth unless a future
   spec adds a purely diagnostic field.
3. **Mode hints degrade to prose.** If a host cannot select or observe native
   plan/implementation modes, servo keeps running with the existing prompt and
   oracle behavior. Missing mode support is not an `env_error`.
4. **The portable vocabulary is small.** Servo recognizes host-neutral phase
   intent: `plan`, `run`, `evaluate`, and `triage`. Host adapters map those to
   Claude or Codex concepts when useful.
5. **Design-eval remains frozen-eval first.** A planning phase may help author
   a rubric or screen set, and an implementation phase may drive UI work, but
   the design-fidelity score still comes from the frozen eval component and
   ledger defined by ADR-0005 / ADR-0009.
6. **Heartbeat remains conservative.** Planning hints may help summarize
   candidates before dispatch, but dispatch still requires `actionable AND
   open`, oracle preflight, cost ceilings, and the inbox merge semantics from
   ADR-0010.

This keeps servo aligned with a future jig host-mode adapter without making
servo depend on jig internals. Servo can accept phase hints from jig, from its
own CLI flags, or from generated host-specific prompts; all are advisory.

## Consequences

**Positive.**

- Servo can use native Codex / Claude planning UX before expensive loop runs
  without creating a second source of truth.
- The design maps cleanly onto ADR-0008: use host autonomy where it helps, keep
  deterministic oracle authority outside the host.
- Servo stays portable. Codex, Claude, and any later host can share the same
  phase intent while rendering different local instructions.

**Negative.**

- Host adapters gain another layer of prose and tests.
- Users may expect Plan mode to be a safety guarantee; docs must be explicit
  that it is only a hint unless the oracle/state contract records something.
- The exact Codex and Claude mode surfaces must be re-verified before any code
  consumes them.

**Neutral.**

- This ADR does not add any runtime field or CLI flag by itself. The parked
  implementation work lives in [Spec 013](../specs/013-host-phase-aware-loops/spec.md).
- The terms `plan`, `run`, `evaluate`, and `triage` are host-neutral intent,
  not a new servo lifecycle.

## Alternatives considered

- **Ignore host modes.** Rejected because it misses a useful interaction and
  budget-control affordance, especially before autonomous loops and
  design-eval work.
- **Make host modes authoritative.** Rejected because it would put servo's
  control plane in non-portable chat/UI state. It also conflicts with
  ADR-0002's closed gate contract and ADR-0008's hard rule that host-native
  judge signals never replace `oracle.sh`.
- **Serialize host mode state into every run.** Deferred. It might be useful
  as diagnostics later, but it is not required to preserve the idea and risks
  creating misleading evidence before a concrete consumer exists.

## Verification

When Spec 013 resumes, verification must include:

- a fresh read/probe of the current Codex and Claude host-mode behavior;
- tests proving missing host-mode support degrades to existing behavior;
- tests proving host-mode hints do not affect `gate.py` pass/fail/env-error
  interpretation;
- docs or surface tests stating that the oracle and state files remain the
  authority.

## References

- [ADR-0002](adr-0002-gate-caller-contract.md) - closed exit codes and JSON
  schema for the gate caller contract.
- [ADR-0005](adr-0005-eval-oracle-component.md) - frozen eval component
  contract.
- [ADR-0008](adr-0008-loop-on-autonomy-primitives.md) - use Claude autonomy
  primitives, but keep `gate.py` as authority.
- [ADR-0009](adr-0009-design-fidelity-eval-recipe.md) - design-fidelity as a
  first-class frozen eval recipe.
- [ADR-0010](adr-0010-triage-inbox-schema.md) - heartbeat triage state spine.
- [Spec 013](../specs/013-host-phase-aware-loops/spec.md) - parked
  implementation work.
