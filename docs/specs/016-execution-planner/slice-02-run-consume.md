---
status: DEFERRED
dependencies: [016-01, 003, adr-0016]
last_verified:
---

## Slice 016-02 — run-consume

**Goal (pre-SPIDR — no ACs):** Teach Servo Run to *read defaults from a present
plan*. `loop.py` (and the heartbeat dispatcher's per-loop invocation) reads
`budget` / `driver` / `prompt_ref` from `<target>/.servo/plans/<spec-id>/plan.json`
when one exists; with **no** plan, behavior is byte-for-byte today's (CLI flags +
`loop.py` defaults). The plan is opt-in glue, not a precondition (ADR-0016).

**DEFERRED — resolution trigger:** activates once **016-01 is DONE** *and* a real
Compile→Run of a spec needs the plan to configure the run (rather than CLI flags)
— i.e. the first end-to-end "compile a plan, then run against it" path. Until a
consumer actually reads the plan, its read-contract ACs (precedence of plan vs
CLI flag, the no-plan-unchanged guarantee) cannot be pinned without guessing.

> Kept as a stub so the spec does not falsely roll up DONE on 016-01 alone.
> Heartbeat plan-reuse is **not** part of this slice (findings are spec-less;
> [ADR-0018](../../decisions/adr-0018-suitability-gates-compile-not-heartbeat.md)).
