---
status: Accepted
date: 2026-06-26
deciders: ramboz
supersedes:
superseded-by:
---

# ADR-0016: The execution plan is the Compile→Run handoff artifact

## Status

Accepted (2026-06-30)

_Refined 2026-06-30 before acceptance, on review against [ADR-0018](adr-0018-suitability-gates-compile-not-heartbeat.md): (1) the plan's consumer is **Compile → Run for a real spec**, not the heartbeat — heartbeat findings are spec-less, so a per-`spec-id` plan does not serve them (the same spec-less-finding fact ADR-0018 established); (2) the plan **references** the suitability artifact by identity rather than **inlining** the verdict string, per this ADR's own reference-don't-copy principle._

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
flags rather than an artifact. A spec compiled today cannot be re-run
reproducibly, and spec 017 (adaptive planning) would have nothing to read or
rewrite.

The plan's consumer is **Compile → Run for a real spec** — a spec with ACs, an
oracle, and a suitability verdict. It is deliberately *not* the heartbeat:
[ADR-0018](adr-0018-suitability-gates-compile-not-heartbeat.md) established that
heartbeat findings are spec-less (a CI failure / issue / commit carries no
`spec-id`), so a plan keyed by `spec-id` has nothing to bind to at the dispatch
boundary. Heartbeat plan-reuse is therefore out of scope here (see Decision).

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
  "suitability_ref": ".servo/suitability/<spec-id>.json",
  "oracle": {"path": "oracle.sh", "components": ["..."], "threshold": 0.5},
  "evaluation_model": {"spec_oracle_id": "...", "ac_count": 7, "residual": 1},
  "budget": {"max_iterations": 5, "cost_ceiling_usd": 2.0,
             "context_fill_threshold": 0.75, "plateau_window": 3},
  "driver": "auto",
  "prompt_ref": "...",
  "provenance": "compiled" | "human_edited"
}
```

The plan references the other Compile artifacts — oracle path, spec-oracle id,
and the **suitability verdict** (`.servo/suitability/<spec-id>.json`, spec 015) —
by identity rather than copying them, same discipline as ADR-0004 referencing the
Claude session by `session_id`. Referencing the suitability artifact (not copying
its `verdict` string into the plan) keeps a single source of truth: the verdict
cannot go stale relative to a re-analysis, and the reference is the natural seam
for the Compile precondition (spec 015-03) — Compile emits a plan only for a
`suitable` verdict, so the presence of a `plan.json` already implies a `suitable`
reference. It is **reviewable and editable**: a human can inspect or adjust the
plan (`provenance: human_edited`) before Run consumes it, the same approval
posture as the spec-oracle freeze (006-04).

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
  (017) has something to rewrite, and a run becomes reproducible from its plan.
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
`schema_version` and references (not copies) the oracle + spec-oracle + the
suitability artifact; Run with no plan is byte-for-byte today's behavior; a plan
ceiling above the safe bound is clamped, not honored; `.servo/plans/` is
git-ignored. Heartbeat plan-reuse is explicitly **not** in scope (findings are
spec-less; ADR-0018).

## References

- [ADR-0014](adr-0014-evaluation-compiler.md) — names the execution plan as a
  Compile output.
- [ADR-0004](adr-0004-session-state-file-format.md) — the reciprocal per-run
  *outcome* artifact; same writer-owned filesystem contract.
- [ADR-0008](adr-0008-loop-on-autonomy-primitives.md) / [ADR-0011](adr-0011-host-native-phase-hints.md)
  — the brakes the plan cannot loosen; the oracle stays the authority.
- [ADR-0018](adr-0018-suitability-gates-compile-not-heartbeat.md) — establishes
  that heartbeat findings are spec-less, which scopes the plan's consumer to
  Compile→Run for a real spec (not the heartbeat).
- [Spec 015 — edd-suitability](../specs/015-edd-suitability/spec.md) — the
  suitability artifact the plan references by identity.
- [Spec 016 — execution-planner](../specs/016-execution-planner/spec.md) — the
  producer; [Spec 017 — evaluation-intelligence](../specs/017-evaluation-intelligence/spec.md)
  — the adaptive-planning consumer that rewrites it.

## Amendments

### 2026-07-04 — "ceiling above policy" narrowed to the disable-sentinel; no numeric magnitude ceiling introduced

The Decision and Verification sections above name **two** clamp triggers: "a
plan with no ceiling, **or a ceiling above policy**, is clamped." Implementing
this in **016-03 (clamp-and-review)** surfaced a gap this ADR did not
anticipate: **no numeric "policy ceiling" exists anywhere in `loop.py`, and
inventing one collides with this same ADR's human-review goal.**

016-02 (run-consume) already recorded, in its own framing, that "no separate
'policy ceiling' exists in loop.py" — the `DEFAULT_MAX_ITERATIONS` /
`DEFAULT_COST_CEILING_USD` / `DEFAULT_CONTEXT_FILL_THRESHOLD` /
`DEFAULT_PLATEAU_WINDOW` constants are documented CLI *defaults* (per
`docs/architecture.md` "Project vs servo-core split"), not a safety maximum
anyone decided on — and a CLI flag can already exceed them uncapped today
(`loop.py`'s flag-shape validation only enforces lower bounds). A 016-03
frame-critique pass caught the consequence directly: clamping a
`human_edited` plan to `DEFAULT_*` would silently defeat the very capability
this ADR asks for — a human reviewing a plan and raising its budget (the
single most likely edit) would have that edit clawed back to the out-of-the-box
default, making "review and adjust" close to "review and be ignored" for the
budget dimension.

**Effective status:** the **"no ceiling" clause is implemented as written** —
a plan (`compiled` or `human_edited`) may never request the documented `0`
("disable this brake") sentinel on `cost_ceiling_usd`, `context_fill_threshold`,
or `plateau_window`; that sentinel is clamped up to the knob's `DEFAULT_*`
(a live brake) rather than honored as disabled. The **"ceiling above policy"
clause is narrowed to mean exactly this disable-sentinel case** — there is no
separate numeric magnitude a plan-sourced value is clamped against; a plan
value that *raises* a knob above `DEFAULT_*` is honored exactly like an
explicit CLI flag. Introducing a genuine magnitude policy ceiling (distinct
from a knob's own default) remains open and is deferred to a future decision
if a real need for one surfaces — it is not invented here to satisfy this
ADR's letter at the cost of the review workflow this ADR itself asks for.

**Disclosed trade-off (persistence, not just a one-shot flag).** A CLI flag
is re-asserted, and re-scrutinized, at every invocation; a `human_edited`
plan is a **persistent, reusable artifact** (this spec's Goal 6: "a run is
reconstructable from its plan") that a raised `cost_ceiling_usd` /
`max_iterations` governs **silently across every future unattended run**
against that spec-id until the plan is recompiled or re-edited. Equating
"raise it once via CLI" with "bake a raised value into a plan consumed
indefinitely" is not a hidden gap — it is a deliberate, disclosed choice not
to invent an undecided re-approval/expiry policy on top of an already-narrow
amendment. If real use surfaces a need for one (e.g. a `human_edited` plan
that goes stale after N days, mirroring 006-04's `stale` approval state),
that is its own future decision, not a reason to fall back to an arbitrary
`DEFAULT_*` cap that this same ADR already rejected above for defeating the
review workflow.
