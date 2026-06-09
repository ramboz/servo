---
status: DRAFT
dependencies: [006]
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
> ADR-0005 and jig ADR-0019 ("integrate on signal"). Until then this is
> captured intent, not queued work, and the slice sketch below is
> pre-SPIDR (no ACs yet, deliberately).

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
- **Does not resolve the jig-vs-servo authoring-home question** (see Open
  questions) — that needs its own ADR once a real case forces the call.

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

## Provisional slice sketch (pre-SPIDR — not ready for implementation)

> Goals only, no ACs. A real EDD spec is needed to ground acceptance criteria;
> until then this just bounds scope.

| Slice | Title | Goal |
|---|---|---|
| 008-01 | residual-triage | From a spec-006 plan, classify each `residual_judgment` AC as eval-able vs human-residual, with rationale. No dataset work yet. |
| 008-02 | rubric-shaping | Turn an eval-able AC into a concrete rubric + judge prompt the author reviews. |
| 008-03 | reference-set | Scaffold + grow the dataset (seed from spec examples/edge cases; minimum-size guidance); the big lift. |
| 008-04 | frozen-params-and-emit | Set `n`/`δ`/threshold/model with defaults; emit the ADR-0005-shaped definition for `/servo:spec-oracle` to compile. |

## Open questions

- **Where does authoring live — jig or servo?** Shaping evaluable ACs is
  spec-*authoring*-time, which is jig's territory (sibling to `/jig:clarify`;
  jig's research note 05 already names a deferred `eval-harness` skill). But the
  dataset, frozen params, and emitted artifact are servo-runtime concerns that
  match `/servo:spec-oracle`. Likely outcome: a split — jig helps author the
  evaluable AC + rubric intent; servo collects the reference set, sets frozen
  params, and emits — mirroring the attest-only boundary of jig ADR-0019/0022
  (jig authors, servo runs). **This split is itself ADR-worthy** and should be
  decided when the first EDD spec forces it, not here.
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
- [Spec 006 — spec-oracle](../006-spec-oracle/spec.md) — the upstream classifier
  (the `residual_judgment` bucket) and the compiler this hands off to.
- jig **ADR-0022 (pluggable oracle boundary)** / **ADR-0019 (refactor workflow)**
  and jig's research note 05 (eval-driven development; the deferred
  `eval-harness` skill) — prior art and the attest-only boundary that shapes the
  jig-vs-servo open question.
