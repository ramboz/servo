---
status: IN_PROGRESS
dependencies: [006, 015, adr-0005, adr-0019, adr-0024, adr-0026, adr-0027]
last_verified:
---

# Spec 008 — eval-authoring

> The generic (text-judged) eval-authoring front-end that lets an engineer turn a goal — or a
> single non-deterministic acceptance criterion — into a *frozen eval component*
> they can actually trust. It expands a free-form goal into curated, tagged ACs
> (independently reviewed, human-approved); triages which residual-judgment ACs
> are eval-able; shapes the scoring rubric; collects the statistical reference
> set; sets the frozen parameters (`n`, `δ`, threshold, judge model) that
> [ADR-0005](../../decisions/adr-0005-eval-oracle-component.md) requires; and
> freezes + installs the resulting `score_<name>` component that `gate.py` runs.
> A light advisory judge-audit reports whether the judge can be trusted. All on
> the shared
> [ADR-0024](../../decisions/adr-0024-extract-frozen-eval-harness.md) harness —
> no parallel infrastructure.

> **Status: READY_FOR_IMPLEMENTATION** (all six slices reviewed clean via a jig:analyze pass — 8 findings resolved; activated 2026-07-11) by the eval-authoring thrust
> ([ADR-0026](../../decisions/adr-0026-generic-eval-authoring-surface.md),
> [ADR-0027](../../decisions/adr-0027-goal-to-eval-assisted-authoring.md)). The
> former "parked until a first EDD spec" trigger is retired: the decision to make
> general non-deterministic eval authoring servo's differentiated capability *is*
> the trigger, made deliberately, with a mature external system (Mystique, studied
> as inspiration — not a target, not a dependency) supplying the grounding a
> hypothetical single consumer would have. Slices 008-01..06 are cut as real,
> buildable work; ACs below are first-draft, to be sharpened during this review.

## Why this spec

[ADR-0005](../../decisions/adr-0005-eval-oracle-component.md) settled the
*contract*: a non-deterministic eval enters servo's oracle only as a frozen
`score_<name>` (definition hashed/approved, confidence-lower-bound scoring,
plateau noise floor, `env_error` never a silent zero).
[Spec 006 (spec-oracle)](../006-spec-oracle/spec.md) settled the *upstream*: it
classifies a spec's ACs into deterministic check families and drops everything
else into `residual_judgment`. [ADR-0024](../../decisions/adr-0024-extract-frozen-eval-harness.md)
built the *backend*: a shared `skills/_common/fidelity_eval.py` harness that
freezes, hashes, n-samples, lower-bounds, ledgers, and splices — already backing
two per-kind evals (`design-eval`, `content-fidelity`).

Two gaps remain, and they are the whole of this spec:

1. **No general authoring path.** The two shipped evals are *bespoke per-kind*
   (each bundles a modality-specific capture step + tuned judge prompt). For any
   `residual_judgment` AC outside {design fidelity, content fidelity}, servo falls
   off a cliff to "hand-write a bash `score_<name>`." Between "this AC is residual
   judgment" and "here is a frozen component that scores it," a human does the
   genuinely hard part of EDD with no help — decide *which* residual ACs are even
   eval-able, turn a fuzzy sentence into a repeatable **rubric**, assemble the
   **reference set** (~80% of the real work; an eval with no dataset is just
   vibes), and choose `n`/`δ`/threshold/model with no intuition for what's safe.
   [ADR-0026](../../decisions/adr-0026-generic-eval-authoring-surface.md) resolves
   this into one authoring surface over the ADR-0024 harness — kind-agnostic across
   **text-judged** ACs; non-text modalities stay preset-only (ADR-0026).

2. **No goal→eval, so the pipeline is spec-centric.** `edd-suitability` (015) and
   `spec-oracle` (006) both consume a spec with acceptance criteria; a free-form
   *goal* has none, so you can't point servo at "make the summary faithful to the
   source" without first hand-writing the ACs — restating the very setup cost this
   spec exists to lower.
   [ADR-0027](../../decisions/adr-0027-goal-to-eval-assisted-authoring.md) adds a
   goal→criteria front-end that expands a goal into tagged ACs, gated by an
   independent reviewer + human curation so it cannot manufacture a false criterion.

That setup cost is the actual barrier to EDD adoption — a new concept, hard to set
up properly, not hard to run once set up. This spec is the human-in-the-loop
authoring surface that lowers the barrier end to end.

## Goals

0. **Expand a goal into curated criteria (opt-in front-end).** Turn a free-form
   goal into a *proposed* AC set, each tagged `deterministic | judged | human-only`
   with a rationale; a fresh independent-reviewer subagent runs an advisory fresh-eyes pass —
   reliable on *structural* defects (wording-obvious mis-tags, unmeasurable
   predicates, goal-restatement, surface-literal gaps), with faithfulness and
   implicit coverage left to the human, who is the sole per-AC gate and approves
   each. Never autonomous, never a false criterion silently frozen
   ([ADR-0027](../../decisions/adr-0027-goal-to-eval-assisted-authoring.md)).
1. **Triage residual judgment.** Given a spec-006 plan (or the curated ACs from
   goal 0), sort each `residual_judgment` AC into *eval-able* vs *human-residual*
   (taste / policy / ADR — stays waived), with a recorded rationale. Never
   silently promote a taste call into an eval.
2. **Shape the rubric.** Convert an eval-able AC into a concrete rubric — scoring
   criteria, scale, and the judge prompt (the artifact ADR-0005 clause 2 freezes) —
   with borrowed prompt archetypes and a structured judge output.
3. **Collect the reference set.** Scaffold and grow the dataset of inputs (and
   labels where ground-truthed), seeded from the spec's examples and edge cases,
   with minimum-viable-size guidance. Project-owned artifact; the author owns the
   truth; the skill never fabricates ground truth.
4. **Set the frozen parameters.** Pick `n`, `δ`, threshold, and judge model+params
   with sane defaults and plain-language trade-off guidance.
5. **Emit a frozen, installable component.** Produce the eval definition in the
   shape the shared harness ([ADR-0024](../../decisions/adr-0024-extract-frozen-eval-harness.md))
   freezes + splices into a `score_<name>` `oracle.sh` component per
   [ADR-0005](../../decisions/adr-0005-eval-oracle-component.md) — self-freezing
   and self-installing via `fidelity_eval.py` exactly as the two presets
   (`design-eval` / `content-fidelity`) do. This skill **authors + freezes +
   installs** the component; `gate.py` **runs** it. **Correction (008-04):** an
   earlier draft of this goal routed the freeze through "`/servo:spec-oracle`'s
   eval-family compile step," but spec-006 has no such step — its
   `oracle_overlay.py` freezes only *deterministic* overlays
   (`score_spec_oracle_<id>`). The frozen-eval path is the ADR-0024 harness the
   presets already ride; spec-006 still *classifies* the ACs (the
   `residual_judgment` bucket 008-01 triages) but does not compile judged evals.
6. **Stay honest and reviewable.** The authored rubric + dataset are inspectable
   project artifacts; the human approves before anything is frozen.
7. **Report judge trust (light advisory audit).** Sample judged cases for human
   spot-checking, compute judge-trust metrics (fail-precision, pass-miss-rate,
   drift), and recommend `auto` vs `confirmed-only` — **advisory only**; it does not
   gate the composite in this MVP.

## Non-goals

- **Not running evals.** This skill authors, freezes, and installs the
  `score_<name>` component (the ADR-0005 clause-2 approval + the ADR-0024
  harness splice); **execution** is `gate.py`/`loop.py`. It stops at an
  approved, installed component (plus the advisory audit) — it never runs the
  eval itself. (The freeze/install is the shared-harness path the two presets
  ride, not a spec-006 step — see Goal 5's correction.)
- **Not autonomous goal→eval.** Goal expansion is an assist gated by independent
  review + human curation (ADR-0027); it never freezes a criterion on its own.
- **Not a heavy eval framework.** No Langfuse/pipeline/dashboard stack (the
  Spacecat-coupled parts of the inspiration are explicitly left behind); the light
  path rides the existing harness.
- **Not refactoring the presets.** `design-eval` / `content-fidelity` stay as-is;
  reframing them as configs over the generic surface is a future rule-of-three call
  (ADR-0026), out of scope here.
- **No composite gating from the judge-audit (MVP).** Auto-demoting an untrusted
  judge would touch the ADR-0005 gate contract; the MVP audit is advisory, and
  demotion is deferred (Open questions).
- **No universal semantic judge** (inherited from spec 006); **no fabricated ground
  truth**; **no eval for deterministic ACs** (those stay in spec-006 check
  families); **no jig-side authoring step** (ADR-0019 — jig stays attest-only).

## Core model

The pipeline this skill spans (new stages marked `*`):

```
GOAL (free text)                                           human-only ACs
  → * [008-05: goal→criteria]  propose (tagged) ─────────────→ (hand off,
        → * independent review (frame sanity)                   out of scope)
        → * human curate + approve
  → curated AC set (spec-shaped, project-owned)
  → [015: criteria split]  evaluable vs human-residual  (FULL verdict deferred:
                               needs target signals + reference set — ADR-0018)
  → [006: spec-oracle classify]   deterministic families │ residual_judgment
                                                          │
  → [008-01: triage]                    eval-able ────────┤   human-residual
  → [008-02: shape rubric]                                │   (stays waived)
  → [008-03: collect reference set]                       │
  → [008-04: set n/δ/threshold/model + emit]              │
  → eval definition (human-approved)                      │
  → [008-04 emit: freeze + install, per ADR-0005, on ADR-0024 harness]
  → frozen score_<name> spliced into oracle.sh
  → [gate.py composite / loop.py halting]
  → * [008-06: judge-audit]  advisory trust metrics + auto/confirmed-only rec
```

008 is the human-in-the-loop authoring span; everything from freeze/install onward
is the ADR-0005 contract operating mechanically on what 008 produced. The independent
review (008-05) and the judge-audit (008-06) both live in the authoring/agent
layer — advisory, never an oracle gate (ADR-0021 / ADR-0011 / ADR-0005).

Ships as **one guided skill, `/servo:eval-authoring`** (ADR-0019's "one skill"
honored; ADR-0026's kind-agnostic surface), with subcommands per stage
(`from-goal` / `triage` / `rubric` / `dataset` / `emit` / `audit`) over a
`skills/eval-authoring/eval_authoring.py` helper that reuses
`skills/_common/fidelity_eval.py`.

**Test surface:** all slices' tests live in
`skills/eval-authoring/test_eval_authoring.py` (servo's `skills/<name>/test_*.py`
convention). **Terminology:** one capability, three role-names — the *capability*
is goal→eval, the *slice* is 008-05 (goal-to-criteria), the CLI *subcommand* is
`from-goal`.

## SPIDR split

**Path-first**, same axis specs 016 and this spec's original sketch used: the
pipeline in "Core model" is a sequential dependency chain, so the natural split is
by stage. No Spike: ADR-0005 settled the eval-component contract, ADR-0024 built
the harness these author onto, and ADR-0026/0027 settled the surface shape and the
goal→eval trust model. The MVP is 008-01..05 (the authoring path + goal→eval);
008-06 is the light advisory judge-audit the thrust explicitly scoped in.

Goal→eval (008-05) is *upstream* of triage in the pipeline but is cut as a later
slice number because triage (008-01) is the smaller, self-contained core that
008-02..04 build on directly; 008-05 produces ACs that re-enter the chain at 015 →
006 → 008-01, so it depends on the classify+triage path existing, not the reverse.

| Slice | Title | Axis | Status | Goal |
|---|---|---|---|---|
| [008-01](slice-01-residual-triage.md) | residual-triage | Path | DRAFT | Classify each `residual_judgment` AC as eval-able vs human-residual, with rationale; never auto-promote a taste call. |
| [008-02](slice-02-rubric-shaping.md) | rubric-shaping | Path | DRAFT | Turn an eval-able AC into a rubric + structured judge prompt (borrowed archetypes), human-reviewed. |
| [008-03](slice-03-reference-set.md) | reference-set | Path | DRAFT | Scaffold + grow the dataset (local-file-as-truth, `happy/edge/skip` taxonomy, min-size guidance); the big lift; never fabricate ground truth. |
| [008-04](slice-04-frozen-params-and-emit.md) | frozen-params-and-emit | Path | DRAFT | Set `n`/`δ`/threshold/model with defaults; freeze + install the ADR-0005-shaped `score_<name>` component via the ADR-0024 harness (self-install like the presets — not a spec-006 step; see Goal 5). |
| [008-05](slice-05-goal-to-criteria.md) | goal-to-criteria | Path | DRAFT | Expand a goal → proposed tagged ACs → independent review → human curate; emit a spec-shaped AC artifact into 015 + 006 ([ADR-0027](../../decisions/adr-0027-goal-to-eval-assisted-authoring.md)). |
| [008-06](slice-06-judge-audit.md) | judge-audit | Path | DRAFT | Light advisory judge-trust audit: spot-check sample, fail-precision / pass-miss / drift, recommend auto vs confirmed-only; no composite gating (MVP). |

## Open questions

- ~~**Where does authoring live — jig or servo?**~~ — RESOLVED 2026-07-01 by
  [ADR-0019](../../decisions/adr-0019-eval-authoring-servo-owned.md): entirely
  servo-owned, one guided skill. Jig attest-only.
- ~~**Per-kind sibling or a general surface?**~~ — RESOLVED 2026-07-11 by
  [ADR-0026](../../decisions/adr-0026-generic-eval-authoring-surface.md): one
  kind-agnostic surface over the ADR-0024 harness; the two fidelity skills stay as
  presets.
- **Minimum viable dataset size**, and how to seed it (spec examples? existing
  fixtures? sampled logs?) — pin against the first real authored eval (008-03).
- **Goal→eval AC-artifact shape** — **RESOLVED 2026-07-11** (analyze review): the curated AC set is a
  **minimal spec-shaped Markdown artifact** (frontmatter + a tagged
  `## Acceptance criteria` list), consumed by 006's classify and read by 015 for its
  criteria split via the existing spec-AC parser — no new format. Note: goal→eval feeds 006's classify + 015's
  *criteria split*, not a full 015 verdict at expansion time (a signal-less
  synthesized spec degenerates to `needs_evidence` — ADR-0018).
- **Independent-reviewer sourcing** — `jig:independent-review` when co-installed vs
  the built-in prompt: confirm the built-in fallback is strong enough alone (008-05).
- **Judge-audit → composite gating (deferred).** Whether an `confirmed-only`
  (untrusted-judge) verdict should *demote* the eval's composite contribution
  rather than only advise. Touches the ADR-0005 gate contract → a future ADR + slice
  if a real audit shows an untrustworthy judge; logged to `docs/refinement-todo.md`.
- **Reuse of the per-iteration `judge` agent infra** for the eval scorer vs a
  separate scorer (ADR-0005 keeps the *roles* distinct; the invocation machinery
  might be shared).

## References

- [ADR-0005 — eval as a frozen oracle component](../../decisions/adr-0005-eval-oracle-component.md) — the contract this skill authors into.
- [ADR-0024 — extract the frozen-eval harness](../../decisions/adr-0024-extract-frozen-eval-harness.md) — the shared `fidelity_eval.py` backend this reuses.
- [ADR-0026 — generic kind-agnostic eval authoring surface](../../decisions/adr-0026-generic-eval-authoring-surface.md) — activates this spec; the surface shape.
- [ADR-0027 — goal→eval assisted authoring](../../decisions/adr-0027-goal-to-eval-assisted-authoring.md) — the goal→criteria front-end + independent-review/human-curation gate (008-05).
- [ADR-0019 — eval authoring stays entirely servo-owned](../../decisions/adr-0019-eval-authoring-servo-owned.md) — one servo skill, jig attest-only.
- [ADR-0009 — design-fidelity eval recipe](../../decisions/adr-0009-design-fidelity-eval-recipe.md) / [Spec 012](../012-design-eval/spec.md) / [Spec 020 — content-fidelity](../020-content-fidelity-eval/spec.md) — the two presets the generic surface sits beside.
- [ADR-0015 — EDD suitability gate](../../decisions/adr-0015-edd-suitability-gate.md) / [Spec 015](../015-edd-suitability/spec.md) — the eval-compatibility verdict the curated ACs feed.
- [Spec 006 — spec-oracle](../006-spec-oracle/spec.md) — the classifier whose `residual_judgment` bucket 008-01 triages. (It classifies ACs; it does **not** compile judged evals — those self-install via the ADR-0024 harness. See Goal 5's correction.)
- Mystique (`/Users/ramboz/Projects/spacecat/mystique`) — external inspiration only (template-first authoring UX, structured judge output, local-dataset-as-truth, judge-audit metrics); its Langfuse/blackboard-coupled infra is deliberately not borrowed. Not vendored, not a dependency.
