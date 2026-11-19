---
status: Proposed
dependencies: []
last_verified:
frame_review: true
---

# ADR-0050: a reviewed eval is a signal, not an evaluability basis

## Status

Proposed (2026-11-18)

## Context

Servo's suitability gate (`/servo:edd-suitability`, ADR-0015) calls a spec
`suitable` only when **both** legs hold: `has_signal` — an executable gate the
oracle can run at all — **and** `n_evaluable >= 1` — the spec-006 classifier
(`oracle_plan.py classify`) mapped at least one acceptance criterion to a
**deterministic** check family, not `residual_judgment`. The two legs guard
different things: `has_signal` asks "is there a gate to run"; `n_evaluable` asks
"is there at least one criterion we can verify *deterministically*." The gate is
fail-closed because EDD's risk is asymmetric (ADR-0015): running the loop against
a spec that cannot be meaningfully evaluated burns budget and produces a green
oracle that means nothing — a **false pass**, the worst failure for an
unattended system. ADR-0018 names the exact shape of that risk at Compile:
**"all-residual ACs + a vacuous oracle."**

Spec 030-01 (ADR-0036) widened the **`has_signal`** leg to
`tests OR ci OR reviewed_frozen_eval` — a reviewed, frozen eval component now
counts as a signal. It deliberately left `n_evaluable` untouched: ADR-0036 scopes
itself to the `has_signal` input set, and its guardrail 5 keeps a
deterministic-counterweight advisory **non-blocking** precisely so the judge
cannot stand alone — "servo's posture has always been to pair non-deterministic
evaluation with deterministic checks rather than let a single judge carry the
oracle."

This leaves a real gap, now measured. A pure **build-to-redline** design target
(e.g. vellum's workflow) is **all-residual**: its acceptance criteria are
fidelity/measurement matches against a redline, scored by the model-judge
(`servo:design-eval`). Running servo's actual classifier on vellum's own worked
timer redline maps **6/6 of those criteria to `residual_judgment`**
(`n_evaluable = 0`); only appended build/structural ACs (`npm run build` exits 0
→ `command`; `dist/index.html` present → `file_presence`) are evaluable. So after
030-01 such a target has a `has_signal` (the eval) but `n_evaluable = 0`, and
suitability returns **`needs_evidence`, never `suitable`**.

The question this ADR settles: **should a reviewed, frozen eval also credit the
`n_evaluable` (evaluability) leg**, so an all-residual design target can be
`suitable`? Structurally, an all-residual target is *exactly* the shape ADR-0018
built the gate to refuse — so the decision turns on one thing: **is a reviewed,
frozen model-judge a "vacuous oracle," or a real evaluability basis?**

The judge is genuinely more than taste. `servo:design-eval` is frozen and
hashed (`definition_hash` pins judge, decoding, samples, threshold, case set),
n-sampled with a conservative lower bound (`mean − k·stderr`), env-error-honest
(never a silent zero), reference-anchored, and reviewed-provenance-gated
(`approval_provenance: "reviewed"`, a distinct-approver re-enumeration). But it
carries servo's own **documented, un-closed** residuals: a frozen, n-sampled,
hashed design-eval once scored a **nine-divergence UI at 0.7998 vs 0.80**
(ADR-0033) — "the machinery lends a rigged rubric the appearance of rigor"; the
omission path has **no reviewer-free floor** ("in a detached loop with none, a
rigged score still passes"); and `reviewed` is a **self-reported** string
(ADR-0036 guardrail 4; OQ6 open). These residuals bite hardest in exactly the
**autonomous, no-distinct-reviewer** mode where the suitability gate matters
most.

## Decision Options Considered

### Option A: the eval credits `has_signal` only; evaluability needs a deterministic rung (chosen)
A reviewed, frozen eval remains a **signal and a composite component**; it does
**not** satisfy `n_evaluable`. A design-led target reaches `suitable` by pairing
the eval with a **deterministic rung** — servo's judge-free static-source-contract
observer (`skills/design-eval/static_contract.py`), a token-lint, or a DOM/CSS
assertion — whose ACs classify deterministically and satisfy `n_evaluable`. A
pure fidelity-only target (no deterministic rung) stays `needs_evidence` until
instrumented.
- **Pros:** keeps a deterministic floor under every `suitable` verdict — the
  exact thing `n_evaluable` guards (ADR-0018); upholds servo's on-record posture
  that the judge is one component, never the sole gate (ADR-0005, ADR-0033,
  ADR-0036 guardrail 5); the judge's gameability residuals never become the sole
  thing the loop optimizes against; closes the gap with machinery servo already
  ships; no change to the gate's trust model.
- **Cons:** a pure fidelity-only target — where the design match is genuinely the
  *only* acceptance and no deterministic rung is meaningful — is refused until an
  author adds one; shifts an instrumentation burden onto design-target authors.

### Option B: credit the reviewed, frozen judge toward `n_evaluable`
Admit an all-residual target on the judge alone.
- **Pros:** admits the thinnest design targets with no extra instrumentation;
  symmetric with ADR-0036's motivation (removing false refusals of design-led
  targets); the eval is falsifiable, not taste, so refusing it arguably
  mis-describes it; ADR-0005 foresaw "promoting a triaged subset of
  `residual_judgment` into frozen eval components."
- **Cons:** removes the **last deterministic anchor** — the loop would optimize
  against a stochastic judge with no deterministic floor, which *is* the
  "all-residual + vacuous oracle" false-pass shape ADR-0018 refuses; contradicts
  servo's composite posture; puts the full weight of the gate on the most
  gameable surface in the autonomous mode where its defenses are weakest (the
  0.7998 field report is a *judged-only* false pass); leans the evaluability leg
  on the self-reported `reviewed` string (OQ6); and moves opposite to ADR-0036's
  kill criteria, which are built to tighten against false *passes*, not to loosen.

### Option C: credit `n_evaluable` from a deterministic *component*, not the judge
Let a deterministic component installed in the oracle (e.g. a static-source-contract
component in `install.json`) satisfy `n_evaluable`, even when the spec's AC text is
all-residual — as 030-01 did for `has_signal`.
- **Pros:** admits a design target instrumented with a deterministic rung-component
  without forcing the author to phrase it as AC text; keeps a real deterministic
  check as the anchor (same posture as A).
- **Cons:** a gate change that drifts `n_evaluable` from "a deterministic AC in the
  spec" to "a deterministic component installed" — a subtle widening; only helps
  the narrow case of a rung-component present but not surfaced as an AC. A
  refinement of A, not a different posture.

## Recommended Decision

**Option A.** A reviewed, frozen eval credits `has_signal` (ADR-0036) and is a
first-class composite component, but it does **not** satisfy the `n_evaluable`
leg. Evaluability requires a deterministic check. A design-led target reaches
`suitable` by pairing the vision eval with a **deterministic rung** — the
judge-free static-source-contract observer servo already ships, a token-lint, or
a DOM/CSS assertion — whose criteria classify deterministically. A pure
fidelity-only target stays `needs_evidence` — correctly: an all-residual spec
whose only oracle is a lone stochastic judge is the false-pass shape ADR-0015 and
ADR-0018 built the gate to refuse, and the judge's un-closed gameability residuals
land hardest in exactly the unattended mode the gate protects. This is not a new
restriction; it is the gate working as intended, with ADR-0036's signal-leg
widening left fully intact.

Option C (crediting `n_evaluable` from a deterministic component) is a possible
future refinement if real design targets commonly carry a deterministic
rung-component that is not surfaced as an AC; it is deferred until that is
observed, because it changes the `n_evaluable` semantics and the AC-text path
(Option A) already admits a properly-instrumented design target today.

## Consequences

**Becomes easier:**
- Every `suitable` verdict keeps a deterministic floor, so a green oracle still
  means something — the loop never optimizes against a lone model-judge.
- servo's composite posture stays coherent: the judge is a signal and component,
  never the evaluability basis, so no new, more-gameable trust surface is opened.
- Design-led targets have a clear, supported path to `suitable`: add a
  deterministic rung (static-source-contract), with the vision eval as the
  fidelity component.

**Becomes harder:**
- A pure fidelity-only design target (no meaningful deterministic rung) is
  refused (`needs_evidence`) until an author instruments one — real friction for
  the thinnest design targets.
- Design-target authors carry the burden of adding a deterministic rung; docs and
  tooling should point them at the static-source-contract observer so the path is
  discoverable.

## Assumptions

- `servo:design-eval`'s gameability residuals are real and bite hardest in the
  autonomous, no-distinct-reviewer mode — grounded in ADR-0033's field report
  (0.7998 vs 0.80 on a nine-divergence UI), ADR-0036 guardrail 4, and the
  ADR-0036 frame-critique, not asserted here.
- servo ships a judge-free deterministic rung usable by a design target
  (static-source-contract observer, `skills/design-eval/static_contract.py`), and
  its criteria classify as a deterministic family in `oracle_plan.py classify`.
  Confirm both at implementation time — if no deterministic rung is actually
  reachable for a real design target, the first Kill criterion fires.

## Kill criteria

- A real class of design-led targets has **no meaningful deterministic rung**
  (fidelity is irreducibly the only acceptance; static-source-contract /
  token-lint / DOM assertions add nothing checkable), so refusing them is a pure
  false refusal with no constructive path. Then crediting the judge (Option B) or
  a deterministic component (Option C) becomes the lesser evil. Trigger: field
  evidence that instrumenting a deterministic rung is infeasible for a real
  target class.
- The design-eval's gameability residuals are **closed** — a structural,
  reviewer-free anti-omission floor, enforced distinct-reviewer re-enumeration,
  and doctoring detection. Then "too gameable to be an evaluability basis"
  weakens and Option B/C should be revisited.

## Open questions

- Is Option C (credit `n_evaluable` from a deterministic component) worth the
  gate change, or does requiring a deterministic AC (Option A) suffice? Deferred
  until usage shows design targets carry rung-components not surfaced as ACs.
- Should servo's docs/skills for design targets actively prescribe the
  static-source-contract rung so the "add a deterministic rung" path is
  discoverable? A docs/skill follow-up, not part of this decision.
