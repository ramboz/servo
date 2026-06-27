---
status: Proposed
date: 2026-06-26
deciders: ramboz
supersedes:
superseded-by:
---

# ADR-0016: The execution plan is the Compile→Run handoff artifact

## Status

Proposed

## Context

[ADR-0014](adr-0014-evaluation-compiler.md) names the outputs of Servo Compile as
an *evidence model*, an *evaluation model*, an *oracle*, and an *execution plan*.
Three of those already exist on disk in some form:

- the **oracle** is `<target>/oracle.sh` (001);
- the **evaluation model** is the spec-oracle overlay at
  `<target>/.servo/spec-oracles/<spec-id>/` — `plan.md` (AC→check map) +
  `checks.json` (machine plan) + the installed component (006);
- the **evidence model** is partially the same overlay plus its append-only
  `ledger.jsonl`.

The **execution plan** has no home. Today the loop is invoked ad hoc: a human (or
the heartbeat dispatcher) passes `--prompt`, `--cost-ceiling`, `--max-iterations`,
`--driver`, etc. on the command line, and the per-run `state.json`
([ADR-0004](adr-0004-session-state-file-format.md)) records what *happened*, not
what was *planned*. That means "Execution Planning" — a named stage in the
pipeline — produces nothing durable, and the Compile→Run boundary is a bag of CLI
flags rather than an artifact. The heartbeat re-derives dispatch parameters each
pass; spec 016 (execution-planner) and 017 (adaptive planning) would have nothing
to read or rewrite.

We need the execution plan to be a **first-class, durable artifact** that Servo
Run consumes — the reciprocal of `state.json` (plan vs outcome), in the same
writer-owned filesystem-contract family as ADR-0004 and ADR-0010.

## Decision

Servo Compile emits an **execution plan** as a named, versioned, project-owned
artifact, and Servo Run consumes it. The plan is the durable Compile→Run handoff.

### Location and shape

```text
<target>/.servo/plans/<spec-id>/plan.json
```

```json
{
  "schema_version": 1,
  "spec_id": "...",
  "compiled_at": "<ISO8601>",
  "suitability_verdict": "suitable",
  "oracle": {"path": "oracle.sh", "components": ["..."], "threshold": 0.5},
  "evaluation_model": {"spec_oracle_id": "...", "ac_count": 7, "residual": 1},
  "budget": {"max_iterations": 5, "cost_ceiling_usd": 2.0,
             "context_fill_threshold": 0.75, "plateau_window": 3},
  "driver": "auto",
  "prompt_ref": "...",
  "provenance": "compiled" | "human_edited"
}
```

The plan references the other Compile artifacts (oracle path, spec-oracle id) by
identity rather than copying them — same discipline as ADR-0004 referencing the
Claude session by `session_id`. It is **reviewable and editable**: a human can
inspect or adjust the plan (`provenance: human_edited`) before Run consumes it,
the same approval posture as the spec-oracle freeze (006-04).

### Run consumes the plan; it does not replace the brakes

`loop.py` / the heartbeat dispatcher read defaults from the plan when one exists,
but the plan **cannot loosen a hard guardrail past its safe ceiling**: the
fail-closed brakes (ADR-0008/003) still bound the run. A plan with no ceiling, or
a ceiling above policy, is clamped — the plan is a *planning input*, never an
authority that can disable a brake. The oracle stays the authority
([ADR-0011](adr-0011-host-native-phase-hints.md)); the plan only configures
*how* Run optimizes against it.

### Relationship to existing artifacts

This ADR adds **one** new artifact (`plans/<spec-id>/plan.json`) and names the
umbrella; it does **not** restructure the oracle or the spec-oracle overlay. The
evidence/evaluation models remain where 001/006 already put them; the plan points
at them. `.servo/plans/` joins `runs/` / `races/` / `triage/` / `dispatch/` under
the git-ignored `.servo/`.

## Consequences

**Positive.**

- "Execution Planning" becomes a real stage with a durable, reviewable output.
- The Compile→Run boundary is an artifact, not a flag bag — adaptive planning
  (017) has something to rewrite; the heartbeat has something to reuse across
  passes; runs become reproducible from a plan.
- Reuses the established writer-owned, versioned, git-ignored `.servo/` pattern;
  no new trust model.

**Negative.**

- A third planning-ish artifact alongside `state.json` (outcome) and the
  spec-oracle `plan.md` (AC map); the names must be kept distinct in docs
  (execution **plan** vs spec-oracle **plan**).
- One more schema to version and migrate.

**Neutral.**

- Backward compatible: when no `plan.json` exists, Run behaves exactly as today
  (CLI flags + defaults). The plan is opt-in glue, not a precondition.
- No change to oracle/gate/loop *behavior* — only a new input source for Run's
  configuration.

## Alternatives considered

- **Keep planning implicit (CLI flags + `state.json`).** Rejected: leaves
  "Execution Planning" with no artifact, so adaptive planning and heartbeat reuse
  have nothing to operate on — the gap ADR-0014 created.
- **Extend `state.json` to hold the plan.** Rejected: conflates *plan* (Compile
  output, stable, reviewable) with *outcome* (Run output, rewritten every
  iteration). ADR-0004 is explicitly a per-run scoreboard; overloading it muddies
  both.
- **Put the plan inside the spec-oracle overlay.** Rejected: the overlay is the
  *evaluation model* (scoped to one spec's ACs); the execution plan spans the
  whole run (oracle + budget + driver) and exists even for targets with only a
  baseline oracle and no spec-oracle.

## Verification

To be established by spec 016. At minimum: a compiled `plan.json` carries
`schema_version` and references (not copies) the oracle + spec-oracle; Run with no
plan is byte-for-byte today's behavior; a plan ceiling above the safe bound is
clamped, not honored; `.servo/plans/` is git-ignored.

## References

- [ADR-0014](adr-0014-evaluation-compiler.md) — names the execution plan as a
  Compile output.
- [ADR-0004](adr-0004-session-state-file-format.md) — the reciprocal per-run
  *outcome* artifact; same writer-owned filesystem contract.
- [ADR-0008](adr-0008-loop-on-autonomy-primitives.md) / [ADR-0011](adr-0011-host-native-phase-hints.md)
  — the brakes the plan cannot loosen; the oracle stays the authority.
- [Spec 016 — execution-planner](../specs/016-execution-planner/spec.md) — the
  producer; [Spec 017 — evaluation-intelligence](../specs/017-evaluation-intelligence/spec.md)
  — the adaptive-planning consumer that rewrites it.
