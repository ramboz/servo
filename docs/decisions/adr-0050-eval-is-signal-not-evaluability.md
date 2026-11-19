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
oracle can run at all — **and** `n_evaluable >= 1` — at least one acceptance
criterion backed by a **deterministic** check, not a stochastic judge. The two
legs guard different things: `has_signal` asks "is there a gate to run";
`n_evaluable` asks "is there at least one criterion we can verify
*deterministically*." The gate is fail-closed because EDD's risk is asymmetric
(ADR-0015): running the loop against a spec that cannot be meaningfully evaluated
produces a green oracle that means nothing — a **false pass**, the worst failure
for an unattended system. ADR-0018 names the exact shape of that risk at Compile:
**"all-residual ACs + a vacuous oracle."**

Spec 030-01 (ADR-0036) widened the **`has_signal`** leg to
`tests OR ci OR reviewed_frozen_eval`. It deliberately left `n_evaluable`
untouched: ADR-0036 scopes itself to the signal input set, and its guardrail 5
keeps a deterministic counterweight **non-blocking** precisely so the judge
cannot stand alone — "servo's posture has always been to pair non-deterministic
evaluation with deterministic checks rather than let a single judge carry the
oracle."

This leaves a real, measured gap. A pure **build-to-redline** design target
(e.g. vellum's workflow) is **all-residual**: its acceptance criteria are
fidelity/measurement matches against a redline, scored by the model-judge
(`servo:design-eval`). So after 030-01 it has a `has_signal` (the eval) but
`n_evaluable = 0`, and suitability returns **`needs_evidence`, never
`suitable`**. The question this ADR settles: **how should a design-led target
earn evaluability** — by crediting the stochastic judge, or some other way?

Two facts about the deterministic landscape, both verified by running servo's
real classifier (`oracle_plan.py classify`) and reading the code, shape the
answer:

1. **AC text alone cannot carry design fidelity.** Of eight natural redline ACs
   run through the classifier, only presence (`"the start button is present"` →
   `file_presence`) and text (`"the timer text contains '00:00'"` →
   `text_invariant`) classify deterministically; **all six fidelity-substantive
   phrasings** (font-family, background-color, font-size, width, color-match,
   visual-faithfulness) fall through to `residual_judgment`. So a deterministic
   *AC-text* rung on a design target is a **presence/text anchor orthogonal to
   visual fidelity** — a page can pass every presence/text AC while being
   visually broken. A text-AC rung satisfies `n_evaluable` on paper without
   putting any deterministic floor under *fidelity*.

2. **Servo already has a judge-free deterministic fidelity check — but it lives
   in a component, not in AC text.** The static-source-contract observer
   (`skills/design-eval/static_contract.py`) runs deterministic
   (`family: command`) checks of a build against a redline source contract — real
   fidelity verification with no model judge. But it is installed as an oracle
   **component**, and today only *deterministic AC text* counts toward
   `n_evaluable`; the observer's deterministic value is therefore **uncounted**.
   (It also hard-requires a `vellum-confirmed-source` producer closure that
   ships with vellum, not servo — so it is reachable for targets that carry that
   closure, vellum today, not for an arbitrary design target.)

The decision thus turns on two linked questions: should the **stochastic vision
judge** satisfy `n_evaluable` (reject — see below), and should a **deterministic
component** like the static-source-contract observer satisfy it so its real
fidelity floor counts?

The vision eval is genuinely more than taste — frozen/hashed, n-sampled with a
conservative lower bound, env-error-honest, reference-anchored,
reviewed-provenance-gated. But it carries servo's own **documented, un-closed**
residuals: a frozen, n-sampled, hashed design-eval once scored a
**nine-divergence UI at 0.7998 vs 0.80** (ADR-0033) — "the machinery lends a
rigged rubric the appearance of rigor"; the omission path has **no reviewer-free
floor** ("in a detached loop with none, a rigged score still passes"); and
`reviewed` is a **self-reported** string (ADR-0036 guardrail 4; OQ6 open). These
residuals bite hardest in exactly the autonomous mode the suitability gate
protects — which is why the judge must not become the evaluability basis.

## Decision Options Considered

### Option A: `n_evaluable` keeps requiring a deterministic *AC*; design targets add one
No gate change. A design target reaches `suitable` by writing a deterministic AC.
- **Pros:** simplest; no new gate surface; the deterministic floor is a real,
  author-reviewed criterion in the spec.
- **Cons:** on a design target the only deterministic AC text available is
  **presence/text** (fact 1) — a thin anchor **orthogonal to fidelity**, so
  fidelity still rests entirely on the stochastic judge; and the one real
  judge-free fidelity check servo ships (the static-source-contract observer,
  fact 2) stays **uncounted** because it is a component, not AC text. A target
  that *is* properly instrumented with a deterministic fidelity rung is still
  refused unless its author also writes a fig-leaf presence AC.

### Option B: credit the stochastic vision judge toward `n_evaluable`
Admit an all-residual target on the model-judge alone.
- **Pros:** admits the thinnest design targets with no extra instrumentation;
  the eval is falsifiable, not taste; ADR-0005 foresaw "promoting a triaged
  subset of `residual_judgment` into frozen eval components."
- **Cons:** removes the **last deterministic anchor** — the loop would optimize
  against a stochastic judge with no deterministic floor, which *is* the
  "all-residual + vacuous oracle" false-pass shape ADR-0018 refuses; puts the
  gate's full weight on the most gameable surface in the autonomous mode where
  its defenses are weakest (the 0.7998 field report is a *judged-only* false
  pass); leans the evaluability leg on the self-reported `reviewed` string
  (OQ6); and moves opposite to ADR-0036's kill criteria, which tighten against
  false *passes*, not loosen.

### Option C: a deterministic *component* satisfies `n_evaluable`; the stochastic judge never does (chosen)
`n_evaluable` is satisfied by at least one **deterministic check**, expressed
**either** as a deterministic AC (classified by `oracle_plan`) **or** as a
deterministic **component** installed in the oracle — one whose checks are in
deterministic families (e.g. the static-source-contract observer's
`family: command` checks). A **stochastic model-judge** component (the vision
eval) **never** satisfies `n_evaluable`; it stays a `has_signal` source and a
fidelity component only. This mirrors how 030-01 widened `has_signal` to read
components, applied to the evaluability leg — but strictly for *deterministic*
components.
- **Pros:** gives a design target a **real deterministic fidelity floor** (the
  static-source-contract observer) that actually counts toward evaluability —
  not the presence/text fig leaf of Option A; keeps the stochastic judge out of
  the evaluability leg entirely (upholds ADR-0005/0033/0036-guardrail-5); counts
  deterministic value wherever it lives (AC text *or* component), closing the
  fact-2 gap where a well-instrumented target's deterministic rung went
  uncounted.
- **Cons:** a gate change — the gate must read `install.json` components and
  **classify each component's checks as deterministic vs stochastic**, correctly
  excluding the vision eval; that classification is new surface and a new place
  to get the judge/deterministic line wrong. And the static-source-contract
  observer needs the vellum producer closure, so C admits *vellum-style* design
  targets, not every design target — a closure-less target still needs a
  deterministic AC (Option A's path).

## Recommended Decision

**Option C.** Evaluability (`n_evaluable >= 1`) is satisfied by at least one
**deterministic check** — a deterministic AC *or* a deterministic component
installed in the oracle (checks in deterministic families; the static-source-
contract observer is the design-fidelity instance). A **stochastic vision eval
never satisfies `n_evaluable`** — it remains a `has_signal` source and a fidelity
*component*, never the evaluability basis (this rejects Option B). A design-led
target reaches `suitable` by pairing the vision eval (fidelity signal/component)
with a deterministic static-source-contract component (the deterministic floor),
which is reachable for targets that carry the producer closure (vellum today).

This preserves the deterministic anchor the `n_evaluable` leg exists to guard
(ADR-0015/0018) and servo's "the judge is one component, never the sole gate"
posture (ADR-0005/0033/0036), while giving design targets a path to `suitable`
that puts a **real, judge-free fidelity floor** under the verdict — not the
presence/text fig leaf Option A would. The honest limit stands: an all-residual
target with **no** deterministic check of any kind — neither a deterministic AC
nor a deterministic component — stays `needs_evidence`, correctly, because a spec
whose only oracle is a lone stochastic judge is exactly the false pass the gate
exists to refuse.

Implementation is a follow-up spec/slice: teach the gate to credit `n_evaluable`
from a component whose checks are in deterministic families, and to exclude a
model-judge component from that credit. The judge/deterministic classification is
the load-bearing piece of that slice (see Kill criteria).

## Consequences

**Becomes easier:**
- A design target instrumented with a deterministic static-source-contract
  component reaches `suitable` with a **real deterministic fidelity floor**, not
  a presence/text fig leaf.
- `n_evaluable` recognizes deterministic value wherever it lives — AC text or
  component — fixing the gap where a well-instrumented target's judge-free
  fidelity rung went uncounted.
- The vision eval stays a reviewed fidelity component and `has_signal` source,
  never the evaluability basis — the composite posture holds.

**Becomes harder:**
- A gate change: the gate must read `install.json` components and classify each
  component's checks as deterministic vs stochastic, correctly excluding the
  vision eval from the `n_evaluable` credit — new surface, and the one place the
  judge/deterministic line must not be crossed.
- The static-source-contract observer needs the vellum producer closure, so C
  admits vellum-style targets, not every design target; a closure-less design
  target still needs a deterministic AC. The gap is narrowed, not fully closed.

## Assumptions

- The static-source-contract observer's checks are deterministic and judge-free
  (`family: command`) — grounded in `skills/design-eval/static_contract.py` and
  `examples/static-source-contract.md`; confirm the installed `checks.json`
  family at implementation time.
- The gate can reliably distinguish a deterministic component from the stochastic
  vision-eval component (by check family / component type in `install.json`).
  Confirm the component metadata actually supports this distinction before
  implementing — if it cannot, the first Kill criterion fires.

## Kill criteria

- The gate **cannot** reliably tell a deterministic component from the stochastic
  eval component (so crediting components risks crediting the judge by mistake).
  Then C collapses into B's risk — abandon component-crediting and fall back to
  Option A (a deterministic AC is required).
- **No** real design target carries a deterministic component (the
  static-source-contract closure proves too rare to matter). Then C helps no one
  in practice, and the design-target gap is closable only via a deterministic AC
  (Option A) or stays open pending a generalized judge-free fidelity rung.

## Open questions

- The exact classification mechanism — how the gate decides a component is
  deterministic vs stochastic (check `family` in `install.json`? a component-type
  field? the `approval_provenance`/judge markers?) — is an implementation detail
  for the follow-up slice, but it is the slice's load-bearing risk.
- Does a generic (non-vellum) design target have any judge-free deterministic
  fidelity rung available, or only targets with the vellum producer closure? If
  only vellum, is generalizing that static-source-contract producer path a
  worthwhile larger follow-up? Out of scope here.
