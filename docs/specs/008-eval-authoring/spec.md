---
status: DRAFT
dependencies: [006, adr-0019]
last_verified:
---

# Spec 008 — eval-authoring

> Help an engineer turn a non-deterministic acceptance criterion into a
> *frozen eval component* they can actually trust: triage which
> residual-judgment ACs are eval-able, shape the scoring rubric, collect the
> statistical reference set, and set the frozen parameters (sample count `n`,
> stability margin `δ`, threshold, judge model) that
> [ADR-0005](../../decisions/adr-0005-eval-oracle-component.md) requires — then
> hand a compilable definition to `/servo:spec-oracle`.

> **Status: DRAFT — scope capture, parked.** Recorded ahead of its first
> consumer, exactly like ADR-0005. It activates when the first real
> non-deterministic (EDD) servo spec exists — the same demand trigger as
> ADR-0005 and jig's own ADR-0019 ("integrate on signal", in the jig repo —
> not to be confused with servo's [ADR-0019](../../decisions/adr-0019-eval-authoring-servo-owned.md)
> below, an unrelated number reused across the two projects' independent ADR
> series). Until then this is captured intent, not queued work. The slices
> below (008-01..04) are fleshed to name a resolution trigger each, mirroring
> spec 016's deferred slices — deliberately without concrete ACs, since
> authoring those now would guess at a boundary only a real consumer can pin.

## Why this spec

ADR-0005 settled the *contract*: a non-deterministic eval may enter servo's
oracle only as a frozen `score_<name>` component (definition hashed/approved,
confidence-lower-bound scoring, plateau noise floor, `env_error` never a silent
zero). [Spec 006 (spec-oracle)](../006-spec-oracle/spec.md) settled the
*upstream*: it classifies a spec's ACs into deterministic check families, and
drops everything else into `residual_judgment` — surfaced, waived, sent to a
human.

Nothing bridges the two. Between "this AC is residual judgment" and "here is a
frozen eval component that scores it," a human has to do the genuinely hard
part of EDD, with no help:

- decide *which* residual ACs are even eval-able (vs genuine taste/policy/ADR
  calls that must stay human);
- turn a fuzzy sentence ("the response is grounded in the retrieved context")
  into a concrete scoring **rubric** a judge can apply repeatably;
- assemble the **statistical reference set** — the dataset of inputs the eval
  scores over. This is ~80% of the real work and the easiest thing to get
  wrong; an eval with no dataset is just vibes;
- choose the frozen parameters `n` / `δ` / threshold / judge model with no
  intuition for what's safe.

That setup cost is the actual barrier to EDD adoption — it is a new concept and
hard to set up properly, not hard to run once set up. This spec is the
human-in-the-loop **authoring front-end** that lowers that barrier: it shapes
the eval and helps collect the reference work, then emits something
`/servo:spec-oracle` can compile into the ADR-0005 frozen component.

## Goals (provisional)

1. **Triage residual judgment.** Given a spec-006 plan, sort each
   `residual_judgment` AC into *eval-able* (rubric + dataset can score it) vs
   *human-residual* (taste / policy / ADR — stays waived), with a recorded
   rationale per AC. Never silently promote a taste call into an eval.
2. **Shape the rubric.** Interactively help the author convert an eval-able AC
   into a concrete rubric: scoring criteria, scale, and the judge prompt — the
   thing whose hash ADR-0005 freezes.
3. **Collect the reference set.** Scaffold and help grow the dataset of inputs
   (and expected behaviours / labels where the eval is ground-truthed), seeded
   from the spec's own examples and the slice's listed edge cases, with
   minimum-viable-size guidance. The dataset is a project-owned artifact, not
   plugin state.
4. **Set the frozen parameters.** Pick `n`, `δ`, threshold, and judge
   model+params with sane defaults and plain-language guidance on the
   trade-offs ADR-0005 named (too-wide `δ` never passes; too-narrow flaps).
5. **Emit a compilable definition.** Produce the eval definition in the exact
   shape `/servo:spec-oracle`'s eval-family extension compiles into a frozen
   `score_<name>` per ADR-0005. This skill **authors**; spec-006 **compiles**;
   `gate.py` **runs**. It does not freeze or score.
6. **Stay honest and reviewable.** The authored rubric + dataset are inspectable
   project artifacts; the human approves before anything is frozen.

## Non-goals

- **Not running or freezing evals.** Compilation + freeze is spec-006 +
  ADR-0005; execution is `gate.py`/`loop.py`. This skill stops at an approved,
  compilable definition.
- **No universal semantic judge** (inherited from spec 006).
- **No fabricated ground truth.** The skill scaffolds and assists dataset
  collection; it does not invent labels or claim synthetic data is a reference
  set. The author owns the truth.
- **No eval for deterministic ACs.** Those stay in spec 006's deterministic
  check families — this skill only touches the eval-able residual subset.
- **No jig-side authoring step.** [ADR-0019](../../decisions/adr-0019-eval-authoring-servo-owned.md)
  settled the jig-vs-servo authoring-home question: this skill's mechanism and
  guided-authoring flow are entirely servo-owned, the same shape as
  `/servo:design-eval` (ADR-0009). Jig's role stays attest-only, unchanged.

## Core model

The pipeline this skill slots into:

```
spec ACs
  → [spec 006: classify]            deterministic families │ residual_judgment
                                                            │
  → [008: triage]                         eval-able ────────┤   human-residual
  → [008: shape rubric]                                     │   (stays waived)
  → [008: collect reference set]                            │
  → [008: set n / δ / threshold / model]                    │
  → eval definition (approved)                              │
  → [spec 006 eval-family: compile + freeze, per ADR-0005]  │
  → frozen score_<name>                                     │
  → [gate.py composite / loop.py halting]
```

008 is the only human-in-the-loop authoring stage; everything downstream is the
ADR-0005 contract operating mechanically on what 008 produced.

## SPIDR split

**Path-first**: the pipeline in "Core model" above is a sequential dependency
chain (triage → rubric → dataset → frozen params/emit), so the natural split
is by stage, same axis 016 used for its Compile→Run chain. No Spike: ADR-0005
already settled the eval-component contract these slices author into, and
ADR-0019 already settled that all four stay servo-only with no jig-side step.

Unlike 016-01 (pinnable from ADR-0016's schema alone, independent of a
consumer), none of 008-01..04 are consumer-independent: even 008-01's triage
rule operates on spec 006's stable `residual_judgment` schema today, but
committing to a concrete eval-able/human-residual boundary without a real AC
to triage would still be a guess. All four stay `DEFERRED` — this is prep
work (naming the resolution trigger per slice), not a decision to build any
of them now.

| Slice | Title | Axis | Status | Goal |
|---|---|---|---|---|
| [008-01](slice-01-residual-triage.md) | residual-triage | Path | DEFERRED | From a spec-006 plan, classify each `residual_judgment` AC as eval-able vs human-residual, with rationale. Trigger: a real `residual_judgment` AC a human wants scored. |
| [008-02](slice-02-rubric-shaping.md) | rubric-shaping | Path | DEFERRED | Turn an eval-able AC into a concrete rubric + judge prompt the author reviews. Trigger: 008-01 DONE. |
| [008-03](slice-03-reference-set.md) | reference-set | Path | DEFERRED | Scaffold + grow the dataset (seed from spec examples/edge cases; minimum-size guidance); the big lift. Trigger: 008-02 DONE. |
| [008-04](slice-04-frozen-params-and-emit.md) | frozen-params-and-emit | Path | DEFERRED | Set `n`/`δ`/threshold/model with defaults; emit the ADR-0005-shaped definition for `/servo:spec-oracle` to compile. Trigger: 008-01..03 DONE. |

## Open questions

- ~~**Where does authoring live — jig or servo?**~~ — RESOLVED 2026-07-01 by
  [ADR-0019](../../decisions/adr-0019-eval-authoring-servo-owned.md): entirely
  servo-owned, one guided skill (mechanism + authoring flow), same shape as
  `/servo:design-eval` (ADR-0009). Jig's role stays attest-only
  (jig's own ADR-0019/ADR-0022, in the jig repo), unchanged. No split.
- **Minimum viable dataset size**, and how to seed it (spec examples? existing
  fixtures? sampled production logs?).
- **Ground-truthed vs reference-free evals** — does the skill support both
  labeled datasets (assertion-style) and rubric-only judging, or start with one?
- **Reuse of the per-iteration `judge` agent infra** for the eval scorer, or a
  separate scorer? (ADR-0005 keeps the *roles* distinct, but the underlying
  invocation machinery might be shared.)
- **Defaults for `n` / `δ`** — deferred to the first real EDD spec (same as
  ADR-0005).

## References

- [ADR-0005 — eval as a frozen oracle component](../../decisions/adr-0005-eval-oracle-component.md)
  — the contract this skill authors into.
- [ADR-0009 — design-fidelity as a first-class eval recipe](../../decisions/adr-0009-design-fidelity-eval-recipe.md)
  — the precedent servo's ADR-0019 (below) generalizes: one servo skill owns
  mechanism + guided authoring for the sibling path into ADR-0005's contract.
- [ADR-0019 — eval authoring stays entirely servo-owned](../../decisions/adr-0019-eval-authoring-servo-owned.md)
  (servo's own ADR series) — resolves this spec's former jig-vs-servo open
  question; grounds why 008-01..04 have no jig-side authoring step.
- [Spec 006 — spec-oracle](../006-spec-oracle/spec.md) — the upstream classifier
  (the `residual_judgment` bucket) and the compiler this hands off to.
- [Spec 012 — design-eval](../012-design-eval/spec.md) — the shipped sibling
  ADR-0019's decision mirrors the shape of.
- jig's own **ADR-0022 (pluggable oracle boundary)** / **ADR-0019 (refactor
  workflow)** in the jig repo — an unrelated number reused across the two
  projects' independent ADR series; the attest-only boundary ADR-0019 (servo)
  keeps unchanged. jig's research note 05 (eval-driven development; the
  deferred `eval-harness` skill) is prior art but not this spec's concern
  post-ADR-0019.
