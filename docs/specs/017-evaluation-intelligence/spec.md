---
status: DRAFT
dependencies: [002, 003, 006]
last_verified:
---

# Spec 017 — evaluation-intelligence

> Phase 3 of the EDD roadmap: make the compiled evaluation *smarter and
> explainable*. A scope-capture umbrella over five capabilities the brief named —
> oracle debugging, convergence analysis, adaptive planning, evaluation
> explainability, and cost optimization — each already seeded in the tree but
> none owned by a spec. **Expected to split** into per-capability specs once a
> grounding consumer forces real acceptance criteria.

> **Status: DRAFT — scope capture, parked.** This is the "evaluation
> intelligence" tier of [ADR-0014](../../decisions/adr-0014-evaluation-compiler.md)'s
> roadmap. The seeds (plateau detection, the gate reason taxonomy, the heartbeat
> cost ceiling) shipped as side-effects of other specs; this spec captures them
> as a coherent direction so the intent stays visible. It activates capability by
> capability, on demand — the slice sketch is pre-SPIDR (goals only, no ACs), and
> several slices are ADR-gated (see Open questions).

## Why this spec

Servo can compile evaluation (Phase 2) and execute against it (Phase 1). What it
cannot yet do is reason *about* the evaluation: explain why a loop isn't
converging, debug an oracle that disagrees with itself, adapt the plan when
progress stalls, or spend budget where it moves the score most. The brief calls
this **Evaluation Intelligence**, and the pieces already exist as disconnected
seeds:

- **Convergence analysis** — the oracle-score plateau / noise-floor heuristic
  (003-05; [ADR-0005](../../decisions/adr-0005-eval-oracle-component.md) plateau δ)
  halts a stuck loop, but doesn't *explain* the stall or suggest a next move.
- **Oracle explainability** — `gate.py --json`'s closed `reason` taxonomy
  (ADR-0002) and the spec-oracle `ledger.jsonl` evidence trail are raw material
  for explanation, never assembled into one.
- **Cost optimization** — the heartbeat whole-pass ceiling
  ([ADR-0012](../../decisions/adr-0012-heartbeat-whole-pass-cost-ceiling.md)) caps
  spend but doesn't *allocate* it intelligently.
- **Oracle debugging** and **adaptive planning** have no seed at all.

Without this tier, every non-convergence is opaque: the loop halts, the human
re-reads the transcript by hand, and the lesson is lost. Phase 3 turns the
compiled evaluation from a pass/fail oracle into something that can be
interrogated.

## Goals (provisional)

1. **Convergence analysis.** Beyond plateau-halt: characterize *why* a run isn't
   converging (oscillating component, single dominant failing check, residual-eval
   noise vs real regression) and surface it as a structured diagnosis.
2. **Evaluation explainability.** Assemble the gate reason taxonomy + spec-oracle
   ledger + per-iteration score history into a human-readable **evaluation
   report** — the Servo Run output ADR-0014 named — that says what passed, what
   didn't, and why.
3. **Oracle debugging.** Detect and explain a *misbehaving* oracle: a component
   that always returns the same score, a check that can't fail (the spec-006
   negative-control idea, generalized), threshold/weight pathologies, disagreement
   between the baseline oracle and the spec-oracle overlay.
4. **Adaptive planning.** Rewrite the 016 execution plan from convergence signals
   — re-weight components, raise/lower the budget, switch driver, narrow the
   prompt — within the same clamp-don't-loosen contract (the plan never disables a
   brake; the oracle stays authority).
5. **Cost optimization.** Allocate budget where it moves the composite most
   (e.g. stop iterating a maxed component), under the existing hard ceilings —
   spend *smarter*, never *more*.
6. **Stay honest.** Diagnoses and adaptations are explainable and auditable; an
   adaptation that can't be justified from evidence isn't made.

## Non-goals

- **Not loosening any guardrail.** Adaptive planning operates inside the
  fail-closed brakes (ADR-0008) and never overrides the oracle (ADR-0011).
- **Not replacing the oracle with a smarter judge.** Intelligence reasons *about*
  the oracle's output; it does not become the source of truth (ADR-0008 hard
  constraint).
- **Not one monolith.** This spec is an umbrella; each capability is expected to
  graduate to its own spec with its own ACs (and likely its own ADR) when grounded.

## Core model

Phase 3 wraps a feedback loop around Servo Run's existing seeds:

```
Servo Run (loop.py)
   │  per-iteration: oracle status, composite, reason taxonomy, score history
   ▼
[017 evaluation intelligence]
   ├─ convergence analysis ──→ diagnosis (why not converging)
   ├─ oracle debugging ──────→ oracle health findings
   ├─ explainability ────────→ evaluation report (Servo Run output)
   └─ adaptive planning ─────→ rewrite .servo/plans/<id>/plan.json  (clamp, don't loosen)
                                      │
                                      ▼  (next iteration / next pass reads the rewritten plan)
                                Servo Run
```

The seeds (plateau δ, gate reasons, ledger, cost ceiling) are the inputs; the
outputs are diagnoses, reports, and plan rewrites — all within the existing
authority + brake contracts.

## Provisional slice sketch (pre-SPIDR — likely splits into separate specs)

> Goals only, no ACs. Each row is a candidate standalone spec once a grounding
> consumer forces acceptance criteria.

| Slice / future spec | Title | Goal |
|---|---|---|
| 017-a | convergence-diagnosis | Structured "why not converging" from score history + reason taxonomy (extends 003-05 plateau). |
| 017-b | evaluation-report | Assemble the human-readable Servo Run evaluation report (gate reasons + ledger + history). |
| 017-c | oracle-debugging | Detect can't-fail / always-same / baseline-vs-overlay-disagreement oracle pathologies. |
| 017-d | adaptive-planning | Rewrite the 016 plan from convergence signals, clamp-don't-loosen. **ADR-gated.** |
| 017-e | cost-allocation | Spend budget where it moves the composite most, under existing ceilings. **ADR-gated.** |

## Open questions

- **ADR candidates.** Adaptive planning that *rewrites* the execution plan, and
  cost *allocation* policy, are both hard-to-reverse, multi-consumer contracts —
  each likely its own ADR (next free number is `0017`+ at authoring time) when a
  real run forces the call. Not pre-written here, matching the 005/008 convention.
- **Report format & home.** Is the evaluation report a `.servo/` artifact, stdout
  JSON, or both? Does it reuse the spec-oracle ledger or aggregate it?
- **Deterministic vs model-assisted diagnosis.** Convergence diagnosis from
  structured signals is deterministic; richer "why" may want a model pass (bounded
  per ADR-0005). Where's the line?
- **Adaptive planning vs human review.** If 016 plans are human-reviewable, does
  an adaptive rewrite need re-approval, or is it bounded enough to auto-apply
  within the brakes?

## References

- [ADR-0014 — evaluation compiler](../../decisions/adr-0014-evaluation-compiler.md)
  — names this Phase 3 tier.
- [ADR-0016 — execution plan artifact](../../decisions/adr-0016-execution-plan-artifact.md)
  — what adaptive planning rewrites.
- [ADR-0005 — eval as a frozen oracle component](../../decisions/adr-0005-eval-oracle-component.md)
  (plateau noise floor), [ADR-0002 — gate caller contract](../../decisions/adr-0002-gate-caller-contract.md)
  (reason taxonomy), [ADR-0012 — heartbeat whole-pass cost ceiling](../../decisions/adr-0012-heartbeat-whole-pass-cost-ceiling.md)
  — the seeds this spec builds on.
- [Spec 003 — agent-loop](../003-agent-loop/spec.md) (plateau/score-history
  source), [Spec 006 — spec-oracle](../006-spec-oracle/spec.md) (ledger +
  negative-control idea).
