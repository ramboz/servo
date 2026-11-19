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
criterion backed by a **deterministic** check, not a stochastic judge. The gate
is fail-closed because EDD's risk is asymmetric (ADR-0015): running the loop
against a spec that cannot be meaningfully evaluated produces a green oracle that
means nothing — a **false pass**, the worst failure for an unattended system.
ADR-0018 names that shape at Compile: **"all-residual ACs + a vacuous oracle."**

Spec 030-01 (ADR-0036) widened the **`has_signal`** leg to
`tests OR ci OR reviewed_frozen_eval`, deliberately leaving `n_evaluable`
untouched (guardrail 5 keeps a deterministic counterweight non-blocking so the
judge cannot stand alone — "pair non-deterministic evaluation with deterministic
checks rather than let a single judge carry the oracle").

This leaves a real, measured gap. A pure **build-to-redline** design target
(e.g. vellum's workflow) is **all-residual**: its acceptance criteria are
fidelity matches against a redline, scored by the model-judge
(`servo:design-eval`). After 030-01 it has a `has_signal` (the eval) but
`n_evaluable = 0`, so suitability returns **`needs_evidence`, never
`suitable`**. The question: **how should a design-led target earn evaluability**
— by crediting the stochastic judge, or another way?

Three facts about the deterministic landscape, verified by running servo's real
classifier and reading the code, shape the answer:

1. **AC text alone cannot carry design fidelity.** Of eight natural redline ACs
   run through `oracle_plan.py classify`, only presence (`"the start button is
   present"` → `file_presence`) and text (`"contains '00:00'"` →
   `text_invariant`) classify deterministically; all six fidelity-substantive
   phrasings (font, color, size, width, color-match, visual-faithfulness) fall
   through to `residual_judgment`. So a deterministic *AC-text* rung on a design
   target is a presence/text anchor **orthogonal to visual fidelity**.

2. **Servo has a judge-free deterministic *fidelity* check — but it is a
   required-policy check, not a component.** The static-source-contract observer
   (`skills/design-eval/static_contract.py`) renders the built app (Chromium) and
   compares computed CSS properties (font, color, size within tolerance) against
   the redline — real rendered-property fidelity, far stronger than presence/text
   (though explicitly "not visual-quality scoring"). Per **ADR-0046** it is
   **component-agnostic**: it is *not* an `install.json` component — it compiles
   into ordinary **required-policy checks** (`family: command`) in the
   required-runtime check plan (e.g. `spec/oracle/static/checks.json`). And
   `n_evaluable` today counts only deterministic *AC text*, so the observer's real
   fidelity value is **uncounted**.

3. **The only *fidelity component* in `install.json` is the stochastic judge.**
   `install.json`'s `components` is a bare `list[str]` of names (no
   family/type/judge field); `design_fidelity` (the model-judge) is the one
   fidelity entry there, and 030-01's component read resolves it by name to credit
   `has_signal`. So "read `install.json` components" reaches the **judge** — the
   exact thing that must be kept out of `n_evaluable` — not the static contract.

The decision turns on two linked questions: should the **stochastic vision
judge** satisfy `n_evaluable` (no — its documented residuals below), and should
the **deterministic static-source-contract check** satisfy it so its real
fidelity floor counts?

The vision eval is more than taste (frozen/hashed, n-sampled lower-bound,
env-error-honest, reviewed-provenance). But it carries servo's own un-closed
residuals: a frozen, hashed design-eval once scored a **nine-divergence UI at
0.7998 vs 0.80** (ADR-0033) — "the machinery lends a rigged rubric the appearance
of rigor"; the omission path has **no reviewer-free floor**; `reviewed` is a
**self-reported** string (ADR-0036 guardrail 4; OQ6 open). These bite hardest in
the autonomous mode the gate protects — which is why the judge must not become the
evaluability basis.

## Decision Options Considered

### Option A: `n_evaluable` keeps requiring a deterministic *AC*; design targets add one
No gate change. A design target reaches `suitable` by writing a deterministic AC.
- **Pros:** simplest; the floor is a real, author-reviewed criterion in the spec.
- **Cons:** on a design target the only deterministic AC text available is
  presence/text (fact 1) — orthogonal to fidelity, so fidelity still rests on the
  stochastic judge; and the one real judge-free fidelity check servo ships (the
  static-source-contract observer, fact 2) stays uncounted, because it is a
  required-policy check, not AC text. A properly-instrumented design target is
  still refused unless its author also writes a fig-leaf presence AC.

### Option B: credit the stochastic vision judge toward `n_evaluable`
Admit an all-residual target on the model-judge alone.
- **Pros:** admits the thinnest design targets with no instrumentation; the eval
  is falsifiable, not taste.
- **Cons:** removes the **last deterministic anchor** — the loop optimizes against
  a stochastic judge with no deterministic floor, the "all-residual + vacuous
  oracle" false-pass shape ADR-0018 refuses; puts the gate's full weight on the
  most gameable surface in the autonomous mode where its defenses are weakest
  (the 0.7998 field report is a judged-only false pass); leans the leg on the
  self-reported `reviewed` string; moves opposite ADR-0036's kill criteria.

### Option C: a deterministic *required-policy check* satisfies `n_evaluable`; the stochastic judge never does (chosen)
`n_evaluable` is satisfied by at least one **deterministic check** — a
deterministic AC (classified by `oracle_plan`) **or** a deterministic
**required-policy check** (`family: command` in the required-runtime check plan,
e.g. the static-source-contract observer's `spec/oracle/static/checks.json`,
which is component-agnostic per ADR-0046). The stochastic vision eval
(`design_fidelity`, an `install.json` component) **never** satisfies
`n_evaluable`; it stays a `has_signal` source and fidelity component only.
- **Pros:** gives a design target a **real deterministic fidelity floor** (the
  static-source-contract check, fact 2) counted toward evaluability — not the
  presence/text fig leaf of Option A; keeps the stochastic judge out of the
  evaluability leg entirely (ADR-0005/0033/0036 guardrail 5); counts deterministic
  value wherever it lives (AC text *or* required-policy check).
- **Cons:** a gate change that teaches suitability to **read the required-runtime
  check plan** (`spec/oracle/static/checks.json`) and confirm a `family: command`
  check — a **new read, NOT 030-01's `install.json` component read** (that read
  reaches the judge, not the static contract, per fact 3), so materially larger
  than "mirror 030-01." And the static-source-contract observer needs the vellum
  producer closure, so C admits vellum-style targets, not every design target; a
  closure-less target still needs a deterministic AC.

## Recommended Decision

**Option C.** Evaluability (`n_evaluable >= 1`) is satisfied by at least one
**deterministic check** — a deterministic AC *or* a deterministic
**required-policy check** (`family: command` in the required-runtime check plan;
the component-agnostic static-source-contract observer is the design-fidelity
instance, per ADR-0046). The **stochastic vision eval never satisfies
`n_evaluable`** — it remains a `has_signal` source and fidelity component, never
the evaluability basis (this rejects Option B). A design-led target reaches
`suitable` by pairing the vision eval (fidelity signal) with the deterministic
static-source-contract check (the fidelity floor), reachable for targets that
carry the producer closure (vellum today).

This preserves the deterministic anchor the `n_evaluable` leg exists to guard
(ADR-0015/0018) and servo's "the judge is one component, never the sole gate"
posture, while putting a **real, judge-free fidelity floor** under a design
target's verdict — not Option A's fig leaf. The honest limit stands: an
all-residual target with no deterministic check of any kind — neither a
deterministic AC nor a deterministic required-policy check — stays
`needs_evidence`, correctly.

The integration is a follow-up spec/slice and is the load-bearing work: teach the
suitability gate to read the required-runtime check plan and credit `n_evaluable`
from a `family: command` check there, while the `install.json` component read
continues to credit only `has_signal` (and the judge `design_fidelity` is never
read into `n_evaluable`). This is a new read of a plan the gate does not consult
today — not an extension of 030-01's component read.

## Consequences

**Becomes easier:**
- A design target with a static-source-contract required-policy check reaches
  `suitable` with a **real deterministic fidelity floor**, not a presence/text
  fig leaf.
- `n_evaluable` recognizes deterministic value wherever it lives — AC text or a
  required-policy check — fixing the gap where the judge-free fidelity check went
  uncounted.
- The vision eval stays a reviewed fidelity component and `has_signal` source,
  never the evaluability basis — the composite posture holds.

**Becomes harder:**
- A gate change beyond 030-01's scope: suitability must read the required-runtime
  check plan (`spec/oracle/static/checks.json`), a source it does not consult
  today, and credit a `family: command` check there — while never reading the
  stochastic `design_fidelity` component into `n_evaluable`.
- The static-source-contract observer needs the vellum producer closure, so C
  admits vellum-style targets, not every design target; a closure-less target
  still needs a deterministic AC. The gap is narrowed, not fully closed.

## Assumptions

- The static-source-contract observer compiles to deterministic required-policy
  checks (`family: command`) in the required-runtime check plan — grounded in
  ADR-0046 and `skills/design-eval/static_contract.py` (verified: it renders via
  Chromium and compares computed CSS within tolerance). Confirm the plan's
  location/shape the gate must read at implementation time.
- The suitability gate can read that required-runtime check plan and confirm a
  `family: command` check. It does **not** do this today (it reads `install.json`
  components for `has_signal` and AC text for `n_evaluable`); confirm feasibility
  before implementing — if the plan is not reliably locatable/parseable from the
  gate, the first Kill criterion fires.

## Kill criteria

- The suitability gate **cannot** reliably read the required-runtime check plan to
  confirm a deterministic (`family: command`) fidelity check (its location/shape
  is unstable, or not present at suitability time). Then C's integration is
  infeasible as scoped, and the design-target gap is closable only via a
  deterministic AC (Option A) until the plan is made readable.
- **No** real design target carries a static-source-contract required-policy check
  (the vellum closure proves too rare to matter). Then C helps no one in practice,
  and the gap stays open pending a generalized judge-free fidelity rung.

## Open questions

- The exact required-runtime plan the gate reads (`spec/oracle/static/checks.json`
  vs the installed required-policy manifest) and how it confirms a check is
  deterministic (`family: command`) — an implementation detail for the follow-up
  slice, and its load-bearing risk.
- Does a generic (non-vellum) design target have any judge-free deterministic
  fidelity rung available, or only targets with the vellum producer closure? If
  only vellum, is generalizing that static-source-contract producer path a
  worthwhile larger follow-up? Out of scope here.
