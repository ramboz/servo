---
status: DRAFT
dependencies: [001, 003, 006]
last_verified:
---

# Spec 016 — execution-planner

> The last step of Servo Compile: turn the compiled evaluation (oracle +
> spec-oracle overlay + suitability verdict) into a durable, reviewable
> **execution plan** that Servo Run consumes — the Compile→Run handoff artifact
> at `<target>/.servo/plans/<spec-id>/plan.json`, per
> [ADR-0016](../../decisions/adr-0016-execution-plan-artifact.md). Provisional
> skill: `/servo:execution-plan`.

> **Status: DRAFT — scope capture, parked.** Recorded as the stage that makes
> "Execution Planning" (named in
> [ADR-0014](../../decisions/adr-0014-evaluation-compiler.md)) produce something
> durable instead of a bag of CLI flags. It activates when a consumer needs to
> *read or rewrite* the plan — the heartbeat reusing dispatch parameters across
> passes, or 017's adaptive planning. Until then this is captured intent; the
> slice sketch is pre-SPIDR (goals only, no ACs).

## Why this spec

[ADR-0014](../../decisions/adr-0014-evaluation-compiler.md) names the execution
plan as a Servo Compile output, but it has no home. The loop is invoked ad hoc —
a human or the heartbeat dispatcher passes `--prompt` / `--cost-ceiling` /
`--max-iterations` / `--driver` on the command line — and the per-run
`state.json` ([ADR-0004](../../decisions/adr-0004-session-state-file-format.md))
records what *happened*, not what was *planned*. So the Compile→Run boundary is a
flag bag, "Execution Planning" produces nothing, and downstream consumers
(heartbeat reuse, 017 adaptive planning) have nothing to read or rewrite.

[ADR-0016](../../decisions/adr-0016-execution-plan-artifact.md) settles the
*contract*: a named, versioned, project-owned `plan.json` that references (not
copies) the other Compile artifacts, is reviewable/editable before Run, and
**cannot loosen a hard guardrail past its safe ceiling**. This spec builds the
planner that emits it and teaches Run to consume it.

## Goals (provisional)

1. **Compile an execution plan.** Assemble `plan.json` from the suitability
   verdict (015), the oracle (001), and the spec-oracle overlay (006): oracle
   reference + components + threshold, evaluation-model reference, budget
   (iterations / cost ceiling / context-fill / plateau window), driver, and
   prompt reference. Per the ADR-0016 schema.
2. **Reference, don't copy.** Point at the oracle and spec-oracle by identity
   (path / id), the way `state.json` references the Claude session — one source
   of truth per artifact.
3. **Stay reviewable and editable.** A human can inspect and adjust the plan
   before Run consumes it (`provenance: human_edited`), mirroring the spec-oracle
   freeze/approval posture (006-04).
4. **Teach Run to consume it.** `loop.py` / the heartbeat dispatcher read
   defaults from a present plan; with no plan, behavior is byte-for-byte today's
   (CLI flags + defaults) — the plan is opt-in glue, not a precondition.
5. **Clamp, never loosen.** A plan budget above the safe ceiling is clamped to
   the guardrail bound, not honored; the plan configures *how* Run optimizes, the
   brakes (ADR-0008/003) and the oracle authority (ADR-0011) are untouched.
6. **Be reproducible.** A run is reconstructable from its plan; the plan records
   `compiled_at` and `provenance`.

## Non-goals

- **Not running the loop.** That stays 003; this spec stops at an emitted plan +
  Run's ability to read it.
- **Not adaptive re-planning.** Rewriting the plan mid-flight from convergence
  signals is 017 (evaluation intelligence); 016 produces the *initial* plan and
  the read/clamp contract it rewrites against.
- **Not a new authority.** The plan can never disable a brake or override the
  oracle.
- **Not replacing `state.json`.** Plan (Compile output, stable) and state (Run
  outcome, rewritten per iteration) stay distinct artifacts (ADR-0016).

## Core model

The Compile→Run handoff the plan makes durable:

```
[015 suitability: suitable]
        │
[001 oracle] ─┐
[006 overlay]─┼─→ [016: compile execution plan] ──→ .servo/plans/<spec-id>/plan.json
[budget/driver/prompt]                                        │  (reviewable, editable)
                                                              ▼
                                          [Servo Run: loop.py / heartbeat dispatch]
                                          reads defaults, clamps to safe ceilings,
                                          oracle stays authority → state.json (outcome)
```

`plan.json` (Compile, stable) and `state.json` (Run, per-iteration outcome) are
reciprocal — plan vs result.

## Provisional slice sketch (pre-SPIDR — not ready for implementation)

> Goals only, no ACs. A grounding consumer (heartbeat reuse or 017 adaptive
> planning) is needed to pin acceptance criteria.

| Slice | Title | Goal |
|---|---|---|
| 016-01 | plan-emit | Compile `plan.json` from suitability + oracle + overlay + budget/driver/prompt; ADR-0016 schema; references not copies; `schema_version`; git-ignored `.servo/plans/`. |
| 016-02 | run-consume | `loop.py` / dispatcher read defaults from a present plan; no plan ⇒ today's behavior unchanged. |
| 016-03 | clamp-and-review | Clamp over-ceiling budgets to the safe bound; support `human_edited` provenance + a review/approve step before Run. |
| 016-04 | skill-and-heartbeat | `/servo:execution-plan` surface; heartbeat reuses a plan across passes instead of re-deriving flags. |

## Open questions

- **One plan per spec, or per run?** `plans/<spec-id>/plan.json` assumes a stable
  per-spec plan; a per-run variant (or a plan→many-runs fan-out for variant-race,
  005) may be needed.
- **Plan/overlay/state naming.** Three "plan"-ish things now (execution **plan**,
  spec-oracle **plan.md**, run **state**); keep the docs disambiguation tight.
- **Where the suitability verdict lives** — inline in `plan.json` (current
  ADR-0016 `suitability_verdict` field) or a standalone artifact 015 owns.
- **Variant-race interaction (005).** Does each variant get its own plan, or one
  plan with N executions? Decide when 005 activates.

## References

- [ADR-0016 — the execution plan is the Compile→Run handoff artifact](../../decisions/adr-0016-execution-plan-artifact.md)
  — the contract this spec implements.
- [ADR-0014 — evaluation compiler](../../decisions/adr-0014-evaluation-compiler.md)
  — names the execution plan as a Compile output.
- [ADR-0004 — session-state file format](../../decisions/adr-0004-session-state-file-format.md)
  — the reciprocal Run-outcome artifact.
- [Spec 015 — edd-suitability](../015-edd-suitability/spec.md) (upstream verdict),
  [Spec 003 — agent-loop](../003-agent-loop/spec.md) (the Run consumer),
  [Spec 017 — evaluation-intelligence](../017-evaluation-intelligence/spec.md)
  (the adaptive-planning rewriter).
