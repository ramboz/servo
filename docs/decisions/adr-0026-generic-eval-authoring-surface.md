---
status: Accepted
date: 2026-07-11
deciders: ramboz
supersedes:
superseded-by:
last_verified: 2026-07-11
---

# ADR-0026: Eval authoring generalizes to one kind-agnostic authoring surface

## Status

Accepted (2026-07-11). Frame-critique pass recorded (pass, round 3, after two
amendment rounds — see [reviews/adr-0026-frame-critique.md](reviews/adr-0026-frame-critique.md)).

Activates [spec 008 (eval-authoring)](../specs/008-eval-authoring/spec.md)
and shapes its slices 008-01..06. Paired with
[ADR-0027](adr-0027-goal-to-eval-assisted-authoring.md) (the goal→eval front-end
this surface grows).

## Context

Three ADRs already bound the non-deterministic eval story:

- [ADR-0005](adr-0005-eval-oracle-component.md) fixed the *contract* — a
  non-deterministic eval enters the composite only as a frozen, hashed
  `score_<name>` with n-sample lower-bound scoring, a plateau noise floor, and
  `env_error` never a silent zero.
- [ADR-0019](adr-0019-eval-authoring-servo-owned.md) settled *ownership* — eval
  authoring (triage, rubric, reference set, frozen params) is entirely servo's
  job, shipped as one guided skill "the same shape as `/servo:design-eval`," jig
  attest-only.
- [ADR-0024](adr-0024-extract-frozen-eval-harness.md) extracted the shared
  freeze/hash/n-sample/lower-bound/ledger/install-splice machinery into
  `skills/_common/fidelity_eval.py`, and shipped `content-fidelity` as a **second
  per-kind sibling** of `design-eval`, explicitly choosing "two sibling skills,
  not one skill with a mode flag."

But both shipped evals are **bespoke per-kind**: each bundles a modality-specific
capture step (`design-eval` — a Playwright screenshot; `content-fidelity` — a
file-or-command text source) and a specialized, pre-tuned judge payload. For any
`residual_judgment` AC *outside* {design fidelity, content fidelity}, servo has
no authoring path at all — it falls off a cliff to "hand-write a bash
`score_<name>`." Spec 008, the general bridge ADR-0019 anticipated, has stayed
`DRAFT`/parked awaiting a first consumer.

The strategic driver (2026-07-11): a decision to make **general non-deterministic
eval authoring servo's differentiated capability** — the thing `/goal` structurally
cannot do and that no attended workflow replaces. That requires a *kind-agnostic*
path, not an ever-growing catalogue of per-kind siblings. A study of a mature
external eval system (Adobe's Mystique, read as inspiration, not a target) confirmed
the shape worth borrowing — template-first authoring UX, structured judge output,
local-dataset-as-truth — and confirmed servo already ships the two things Mystique
openly lacks (statistical stabilization; goal→eval). The missing piece is purely
servo's own: a general authoring surface. And that surface is not a guess ahead of
a consumer — `content-fidelity` (spec 020, DONE) is a real, shipped text-in /
text-judge eval of exactly this shape; the generic surface generalizes it by
removing its baked prompt and capture, rather than inventing a shape no consumer
has exercised.

**The tension this ADR must resolve.** ADR-0024 rejected "one skill with a `--kind`
flag." Does a *generic* authoring surface reopen that rejected door?

## Decision

**Spec 008 activates as one kind-agnostic eval-authoring surface,
`/servo:eval-authoring`.** Given any eval-able `residual_judgment` AC, it guides
the author through triage → rubric-shaping → reference-set collection →
frozen-parameter setting, and emits a definition `/servo:spec-oracle`'s
eval-family compile step turns into a frozen `score_<name>` per ADR-0005. It
authors; spec-006 compiles and freezes (ADR-0022/ADR-0023); `gate.py` runs.

1. **It reuses the ADR-0024 harness — mechanism, not free honesty.** The emitted
   component is built on `skills/_common/fidelity_eval.py` for
   freeze/hash/n-sample/lower-bound/ledger/install-splice, inheriting ADR-0005's
   freeze/aggregate **mechanism**. The genuinely new work is (i) the *authoring UX*
   (guided flow + templates) and (ii) a **configurable multi-field dataset schema**:
   content-fidelity today hardcodes a fixed two-slot reference-comparison judge
   (`_prompt(generated, reference)`), so expressing a 1-slot property check ("the
   error message names the offending field") or a 3-slot grounding judgment
   ("grounded in the retrieved context") requires generalizing it to arbitrary
   named input fields — real, if modest, runtime work, not "just unbake the prompt."
   And the honesty guarantees are **not free**: each new field needs a per-field
   freeze classification (hash its content vs. pin by value vs. exclude as a moving
   target — content-fidelity hand-codes this in
   `_REFERENCE_FILE_FIELDS`/`_CASE_PIN_FIELDS` today), an honesty-critical authoring
   responsibility this ADR hands to spec 008 (008-03/008-04) and names as a risk
   below.

2. **Scope: text-judged evals. Why this does NOT contradict ADR-0024.** ADR-0024's
   "siblings, not a flag" governs the axis that genuinely differs between design
   and content fidelity, and that axis is **two** things (ADR-0024's "what stays
   forked"): the modality-specific **capture step** *and* the **judge payload**
   (the runtime wire format — image content blocks vs. a text-only message; both
   live in each preset's own `score.py`, not in `fidelity_eval.py`). The generic
   surface addresses each honestly:
   - **capture — removed.** No built-in capture; the human supplies the dataset of
     inputs (or a generator command, generalizing content-fidelity's
     file-or-command source), so there is no modality-specific capture to fork.
   - **judge payload — generalized only for text.** content-fidelity already ships
     a text-judge payload; the generic surface lifts it to be prompt-configurable.
     A **non-text judge payload** (vision/audio wire format) is genuinely runtime
     code that stays forked — so the generic surface is kind-agnostic **across
     text-judged ACs**, not across all modalities.
   This is narrower than "any residual AC," and deliberately so: the vast majority
   of `residual_judgment` ACs ("is the summary faithful to the source," "is the
   tone right," "is the answer grounded in the retrieved context") are text-judged.
   A `--kind visual|text` flag would have forked capture + payload for no savings
   (ADR-0024's finding); the generic surface removes capture and generalizes only
   the text payload, so it is *orthogonal* to the presets on the text axis and
   explicitly **defers** non-text modalities to the presets (design-eval) —
   see point 3.

3. **design-eval and content-fidelity stay as-is — ergonomic presets.** They
   remain opinionated, first-class skills for their common cases, bundling capture
   + a tuned judge prompt so a user need not hand-author them. The generic surface
   is the fallback for everything else **text-judged**. Non-text-judged evals
   (design-eval's vision payload) stay **preset-only**; extending the generic
   surface to a new judge-payload modality is itself a future rule-of-three call,
   not this MVP. **Reframing the two presets as thin configs over the generic
   surface is likewise a non-goal here** — no forced refactor; if it ever pays off
   it is a separate rule-of-three call (ADR-0003), exactly as ADR-0024 handled the
   first extraction.

4. **Authored artifacts are project-owned and inspectable; the human approves
   before any freeze.** The rubric and dataset are local files (source of truth,
   in the project's git, not plugin state). Nothing is auto-frozen — spec 008
   goal 6 unchanged.

## Consequences

### Positive
- Turns servo's non-deterministic eval story from "two hardcoded verticals" into
  "any **text-judged** residual acceptance criterion can become a trustworthy
  frozen eval" — the general capability the strategic bet requires, honestly scoped
  to the modality the shared harness already serves.
- Minimal new infrastructure: sits on the existing harness (ADR-0024), the existing
  compiler (spec 006), and the existing suitability gate (spec 015); the new code
  is authoring UX.
- Composes with [ADR-0027](adr-0027-goal-to-eval-assisted-authoring.md)'s goal→eval
  front-end to give a full lifecycle (goal → criteria → suitability → author → run)
  no single tool in the surveyed prior art offers.

### Negative
- A generic judge driven by a user-authored prompt is less tuned than a preset's
  baked prompt — more authoring burden and more room for a weak rubric. Mitigated
  by borrowed prompt archetypes/templates (008-02) and, decisively, by ADR-0027's
  independent-review + human-curation gate on the frame.
- **Per-field freeze classification is a new honesty risk, not inherited free.** A
  configurable multi-field dataset means the author must classify each field's
  freeze semantics (hash-content / pin-by-value / exclude-as-moving-target).
  Misclassifying — content-hashing a moving target, or failing to pin a swapped
  reference — silently defeats staleness detection. content-fidelity makes this call
  in code once; the generic surface must surface it as a guided, defaulted authoring
  step (008-03/008-04). Named here so spec 008 owns it, not the harness.
- One more skill in the catalogue, and a reader now has three entry points
  (design-eval, content-fidelity, eval-authoring) into ADR-0005's contract.

### Neutral
- The two presets coexist with the generic surface indefinitely; this ADR does not
  deprecate them.
- The exact subcommand surface (`from-goal` / `triage` / `rubric` / `dataset` /
  `emit` / `audit`) is the implementing spec's call, sketched in spec 008, not
  fixed here.

## Alternatives considered

- **Keep adding per-kind siblings** (a third, fourth… bespoke skill as new eval
  kinds arrive). Rejected: unbounded proliferation, and it never produces the
  *general* capability the moat needs — each sibling is another demo, not a path.
- **A `--kind` mode flag over design/content fidelity.** Rejected per ADR-0024, and
  moot: the generic surface removes the capture/judge-payload axis rather than
  switching over it, so it is not the design that ADR rejected.
- **Stay parked until a "first real EDD spec" arrives** (spec 008's original
  trigger). Rejected: the strategic decision to invest in eval authoring *is* that
  trigger, made deliberately rather than waiting for an accidental one — and
  `content-fidelity` (spec 020, DONE) already supplies a real shipped text-judge
  consumer whose shape the generic surface generalizes, so this is not guessing
  ahead of a consumer but generalizing the one that exists — with the honest caveat
  that the reused harness + text-judge wire format are consumer-validated, while the
  configurable multi-field schema (Decision #1) is deliberate strategic-bet scope,
  exercised by the Verification obligation rather than by a shipped consumer. (The
  Mystique study only informs the authoring UX.)
- **Build a heavy eval framework** (a Langfuse/pipeline-style system like
  Mystique's older stack). Rejected: over-built and infra-coupled; the light path
  on the existing harness is strictly cheaper and inherits ADR-0005's guarantees.

## Verification

Implemented by spec 008 (slices 008-01..06). Obligations:

- The generic skill authors, end-to-end, a frozen eval for a **text-judged**
  `residual_judgment` AC whose criterion is neither design-fidelity nor
  content-fidelity's baked rubric (e.g. "the error message names the offending
  field and suggests a fix"), and `gate.py` runs the resulting `score_<name>`
  under the ADR-0002 exit contract — proving generality *within the text-judged
  scope*, not a hollow re-run of content-fidelity minus its prompt. This case is
  single-input / no-reference, so it necessarily exercises the multi-field
  dataset-schema generalization (point 1), not just a prompt swap.
- The emitted component's freeze/stale/`env_error`/lower-bound behavior is exercised
  through the shared `fidelity_eval.py` (ADR-0024), not a re-copy.
- `design-eval` and `content-fidelity` test suites pass unmodified — no preset is
  refactored by this ADR.

## References
- [ADR-0005](adr-0005-eval-oracle-component.md) — the frozen-eval contract this surface authors into.
- [ADR-0009](adr-0009-design-fidelity-eval-recipe.md) — design-eval, the first preset.
- [ADR-0019](adr-0019-eval-authoring-servo-owned.md) — eval authoring is servo-owned, one guided skill.
- [ADR-0024](adr-0024-extract-frozen-eval-harness.md) — the shared harness this reuses; the "siblings not a flag" call this reconciles with.
- [ADR-0022](adr-0022-freeze-against-parsed-acs.md) / [ADR-0023](adr-0023-colocate-durable-spec-oracle-artifacts.md) — the compile/freeze boundary this hands off to.
- [ADR-0027](adr-0027-goal-to-eval-assisted-authoring.md) — the goal→eval front-end grown on this surface.
- [Spec 006 — spec-oracle](../specs/006-spec-oracle/spec.md), [Spec 008 — eval-authoring](../specs/008-eval-authoring/spec.md), [Spec 012 — design-eval](../specs/012-design-eval/spec.md), [Spec 020 — content-fidelity-eval](../specs/020-content-fidelity-eval/spec.md), [Spec 015 — edd-suitability](../specs/015-edd-suitability/spec.md).
- Mystique (`/Users/ramboz/Projects/spacecat/mystique`) — external inspiration only; not vendored, not a dependency. Its template-first authoring UX is borrowed; its Langfuse/blackboard-coupled infra is not.
