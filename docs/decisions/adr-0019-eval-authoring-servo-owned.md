---
status: Accepted
date: 2026-07-01
deciders: ramboz
supersedes:
superseded-by:
last_verified: 2026-07-01
---

# ADR-0019: Eval authoring stays entirely servo-owned

## Status

Accepted (2026-07-01)

## Context

[Spec 008 (eval-authoring)](../specs/008-eval-authoring/spec.md) is the
human-in-the-loop bridge [ADR-0005](adr-0005-eval-oracle-component.md)
anticipated: given a spec's `residual_judgment` AC (from
[spec 006](../specs/006-spec-oracle/spec.md)'s classifier), triage which ones
are eval-able, shape a rubric, collect a statistical reference set, set the
frozen `n`/`δ`/threshold/judge-model, and emit a definition
`/servo:spec-oracle` compiles into a frozen `score_<name>` component. It is
still DRAFT and parked — no spec-text `residual_judgment` AC has yet forced
the question — but its own text carries an unresolved open question that
blocks shaping its slices with confidence:

> **Where does authoring live — jig or servo?** Shaping evaluable ACs is
> spec-*authoring*-time, which is jig's territory (sibling to `/jig:clarify`;
> jig's research note 05 already names a deferred `eval-harness` skill). But
> the dataset, frozen params, and emitted artifact are servo-runtime concerns
> that match `/servo:spec-oracle`. Likely outcome: a split — jig helps author
> the evaluable AC + rubric intent; servo collects the reference set, sets
> frozen params, and emits.

That framing treats rubric-shaping as spec-authoring (jig's home) and
everything downstream of it as servo-runtime. This ADR tests that framing
against a decision servo already made for a structurally identical problem,
and settles it now — even though 008 is still parked — because it will shape
how 008's slices are cut whenever a real consumer arrives, and because the
next servo eval-authoring workflow is a small blast radius to decide today
versus after code exists that assumes a split.

**The design-eval precedent.** [Spec 012](../specs/012-design-eval/spec.md) /
[ADR-0009](adr-0009-design-fidelity-eval-recipe.md) already resolved an
analogous authoring-home question for the *other* path into ADR-0005's
contract: "does the built UI match the design mockup?" That work is at least
as spec-authoring-adjacent as 008's rubric-shaping — someone has to decide
which screens matter, what the fidelity rubric criteria are, and how many
samples are enough — yet ADR-0009 shipped the entire mechanism *and* the
guided authoring flow (screen dataset, rubric, judge model, `n`/`k`/`δ`/
threshold, frozen `config.json`) inside a single servo skill,
`/servo:design-eval`. Jig has no role in it. ADR-0009's own alternatives
considered rejected "jig grows the eval runner" on scope, citing this
ADR-0005 and jig ADR-0019(jig)'s attest-only boundary. ADR-0005's alternatives
considered say the same thing independently. Two separate ADRs, arriving at
one conclusion: authoring a frozen eval component — rubric included — is
servo's job, not jig's.

**Why the "authoring is spec-time, so it's jig's" framing doesn't hold.**
Spec 006 already draws the line jig actually cares about: jig authors the
spec's *acceptance criteria* (the fuzzy sentence — "the response is grounded
in the retrieved context"). What 008 does next — turning that sentence into a
rubric, a judge prompt, and a hashed, frozen scoring definition — is not
spec-authoring, it is **compile-target authoring**: producing an artifact
that only servo's compiler (the spec-006 eval-family extension) consumes,
that only servo's runtime (`gate.py`/`loop.py`) executes, and that ADR-0005
requires servo to hash, freeze, and ledger. It has the same relationship to
the spec AC that a hand-written test has to a spec's DoD line: adjacent in
time, but a different artifact owned by a different tool. jig's actual
boundary (ADR-0019(jig)/ADR-0022(jig), restated for servo's half in
ADR-0005 and ADR-0009) is **attest-only**: jig records that an oracle ran; it
does not author the oracle's scoring logic. Splitting rubric-authoring into
jig would be the first exception to that boundary, made for no reason this
ADR can find beyond a surface-level "sounds like authoring, sounds like
jig."

**Practical cost of a split, independent of the boundary argument.** A split
means the rubric intent lives in a jig-authored artifact that a servo skill
must then read, re-validate, and combine with servo-collected data and
servo-frozen params before compiling — a cross-repo/cross-tool handoff for an
artifact with exactly one consumer (servo's own compiler). Keeping it
one-sided removes that handoff with no loss of capability: a human still
authors the rubric's *content* by hand either way, inside a guided servo
skill instead of a guided jig skill.

## Decision

**Eval authoring — triage, rubric-shaping, reference-set collection, and
frozen-parameter setting — is entirely servo's job.** Spec 008 ships as a
single guided servo skill, the same shape as `/servo:design-eval` (ADR-0009):
servo owns the mechanism and the guided-authoring flow; the human/project
owns the policy content (which ACs are eval-able, the rubric wording, the
dataset, the frozen values). Jig's role is unchanged from its existing
attest-only boundary (ADR-0019(jig)/ADR-0022(jig)) — it may reference or
attest that a frozen eval component exists and ran; it does not author rubric
or scoring content. This closes spec 008's open question: there is no split
to design, and spec 008's slices (008-01..04) should each land as ordinary
servo-skill slices, not as a jig-side + servo-side pair.

This does not touch spec 006's `residual_judgment` classification (still
jig-authored-spec-text-in, servo-classified) or ADR-0005's contract; it only
resolves *which tool hosts the authoring step between them*.

## Consequences

**Positive.**

- Removes a design fork that was blocking confident slicing of spec 008 —
  008-01..04 can now be scoped as servo-only work whenever a real consumer
  arrives.
- Consistent with the only precedent servo has for this exact question
  (ADR-0009/spec 012): one tool owns mechanism + guided authoring; the
  boundary with jig stays attest-only, not authoring-split.
- No cross-repo/cross-tool handoff for an artifact (rubric + dataset + frozen
  params) that only servo's own compiler and runtime ever consume.
- Keeps jig's attest-only posture (ADR-0019(jig)/ADR-0022(jig)) uniform
  across both eval-authoring paths (design-eval and spec-008's bridge)
  instead of uniform for one and split for the other.

**Negative.**

- If a future case genuinely needs spec-authoring-time input to the rubric
  (e.g. the AC's author has context a later servo session lacks), that
  context has to be captured in the spec text or ledgered evidence for the
  servo skill to consume — there is no jig-side authoring step to carry it
  forward implicitly.
- Does not by itself extract the shared `validate_freeze`/
  `aggregate_lower_bound`/`definition_hash` primitives design-eval already
  has in `score.py` — spec 008 building its own copy first, then extracting
  on the second real eval kind (ADR-0003 rule-of-three), is unchanged by this
  ADR and still the plan.

**Neutral.**

- Spec 008 stays parked; this ADR settles *how* it will be scoped when its
  own trigger (a real spec-text `residual_judgment` AC) fires, not that it is
  activated now.
- jig's research note 05's deferred `eval-harness` skill is not this ADR's
  concern — if jig later wants a *spec-authoring-time* nudge toward
  eval-able ACs (e.g. flagging a fuzzy AC as a spec-008 candidate while the
  spec is being written), that is jig deciding its own attest-adjacent
  tooling, not an authoring split with servo. This ADR only rules out jig
  authoring rubric/dataset/param *content*.

## Alternatives considered

- **Split: jig authors the evaluable-AC + rubric intent; servo collects the
  reference set, sets frozen params, and emits** (spec 008's own "likely
  outcome" framing). Rejected: no precedent for it (ADR-0009 chose the
  opposite for a structurally identical problem), it is the first exception
  to jig's attest-only boundary, and it adds a cross-tool handoff for an
  artifact with one consumer.
- **Defer this ADR until spec 008's trigger fires**, on the grounds that
  deciding ahead of a real consumer risks guessing wrong (the same risk
  ADR-0005 named for itself). Rejected: the design-eval precedent is a real,
  Accepted decision on the identical question, not a guess — waiting adds
  no information this ADR doesn't already have, and it leaves 008's slice
  sketch unable to be shaped with confidence in the meantime.
- **Converge spec 008 and spec 012 into one general eval-authoring
  framework now**, resolving the authoring-home question as a side effect of
  a bigger unification. Rejected on ADR-0003 grounds (also ADR-0009's own
  call): extract shared primitives on the *second* real eval kind, not
  before either has a real consumer exercising it.

## Verification

No slice implements this yet (008 is still parked). When 008's trigger fires
and its slices are cut:

- 008-01..04 (or whatever slices replace them) must each be scoped as
  ordinary servo skill work — no slice should require a jig-side
  authoring step, a jig-owned artifact consumed by servo, or a jig plugin
  change.
- Any jig involvement in a future 008 slice should be limited to attesting
  that the frozen eval component exists/ran (the existing ADR-0019(jig)/
  ADR-0022(jig) shape), never to authoring rubric, dataset, or parameter
  content.

## References

- [ADR-0005 — eval as a frozen oracle component](adr-0005-eval-oracle-component.md)
  — the contract spec 008 authors into; its alternatives considered
  independently rejected "jig grows the eval runner."
- [ADR-0009 — design-fidelity as a first-class eval recipe](adr-0009-design-fidelity-eval-recipe.md)
  — the precedent this ADR generalizes: one servo skill owns mechanism +
  guided authoring for the *other* path into ADR-0005's contract.
- [Spec 008 — eval-authoring](../specs/008-eval-authoring/spec.md) — the spec
  whose open question this ADR resolves.
- [Spec 006 — spec-oracle](../specs/006-spec-oracle/spec.md) — the upstream
  classifier that produces `residual_judgment`; the actual jig/servo line
  (spec-text AC in, classification out) this ADR leaves untouched.
- [Spec 012 — design-eval](../specs/012-design-eval/spec.md) — the shipped
  sibling this ADR's Decision mirrors the shape of.
- jig **ADR-0019 (refactor workflow)** / **ADR-0022 (pluggable oracle
  boundary)** in the jig repo — the attest-only posture this ADR keeps
  uniform across both eval-authoring paths. (Not vendored into this repo;
  summarized here via ADR-0005's and ADR-0009's restatements of them.)
