---
status: Accepted
dependencies: []
last_verified: 2026-11-19
frame_review: true
---

# ADR-0050: a reviewed eval is a signal, not an evaluability basis

## Status

Accepted (2026-11-19)

## Context

Servo's suitability gate (`/servo:edd-suitability`, ADR-0015) calls a spec
`suitable` only when **both** legs hold: `has_signal` — an executable gate the
oracle can run at all — **and** `n_evaluable >= 1` — at least one acceptance
criterion of **that spec** backed by a **deterministic** check, not a stochastic
judge. The gate is fail-closed because EDD's risk is asymmetric (ADR-0015): a
loop against a spec that cannot be meaningfully evaluated produces a green oracle
that means nothing — a **false pass**, the worst failure for an unattended
system. ADR-0018 names the shape: **"all-residual ACs + a vacuous oracle."**

Spec 030-01 (ADR-0036) widened the **`has_signal`** leg to
`tests OR ci OR reviewed_frozen_eval`, deliberately leaving `n_evaluable`
untouched (guardrail 5 keeps a deterministic counterweight non-blocking so the
judge cannot stand alone).

This leaves a real, measured gap: a pure **build-to-redline** design target
(vellum's workflow) is **all-residual** — its ACs are fidelity matches against a
redline, scored by the model-judge (`servo:design-eval`). After 030-01 it has a
`has_signal` (the eval) but `n_evaluable = 0`, so suitability returns
**`needs_evidence`, never `suitable`**. The question: **how should a design-led
target earn evaluability** — by crediting the stochastic judge, or another way?

Four facts, verified by running servo's classifier and reading the code, shape
the answer:

1. **AC text alone cannot carry design fidelity.** Run through
   `oracle_plan.py classify`, only presence/text redline ACs classify
   deterministically; all fidelity-substantive phrasings (font, color, size,
   width, visual match) fall through to `residual_judgment`. A deterministic
   *AC-text* rung on a design target is a presence/text anchor **orthogonal to
   fidelity**.

2. **Servo has a judge-free deterministic *fidelity* check — but it is a
   required-policy check, not a component.** The static-source-contract observer
   (`skills/design-eval/static_contract.py`) renders the built app (Chromium) and
   compares computed CSS (font/color/size within tolerance) against the redline —
   real rendered-property fidelity (explicitly "not visual-quality scoring"). Per
   **ADR-0046** it is **component-agnostic**: not an `install.json` component, but
   `family: command` **required-policy checks** in the required-runtime check plan
   at the fixed, target-relative path `<target>/spec/oracle/static/checks.json`.
   `n_evaluable` counts only deterministic AC text today, so its value is
   **uncounted**.

3. **The only *fidelity component* in `install.json` is the stochastic judge.**
   `install.json`'s `components` is a bare `list[str]`; `design_fidelity` (the
   model-judge) is the one fidelity entry there, and 030-01's component read
   resolves it to credit `has_signal`. So "read `install.json` components" reaches
   the **judge** — never the static contract.

4. **The static check is a per-*target* artifact; `n_evaluable` is per-*spec*.**
   `static_contract.py` writes one `checks.json` per target
   (`spec_id: "static"`), while `suitability.py` counts `n_evaluable` from the
   `--spec` under analysis. So a deterministic required-policy check can only be
   credited to a spec it is **attributed** to — crediting it target-globally would
   pass an unrelated all-residual spec on the same target (see Option C cons).

The vision eval is more than taste (frozen/hashed, n-sampled lower-bound,
env-error-honest, reviewed-provenance), but carries servo's own un-closed
residuals: a frozen, hashed eval once scored a **nine-divergence UI at 0.7998 vs
0.80** (ADR-0033); the omission path has **no reviewer-free floor**; `reviewed`
is a **self-reported** string (ADR-0036 guardrail 4; OQ6 open). These bite
hardest in the autonomous mode the gate protects — so the judge must not be the
evaluability basis.

## Decision Options Considered

### Option A: `n_evaluable` keeps requiring a deterministic *AC*; design targets add one
No gate change.
- **Pros:** simplest; the floor is a reviewed criterion in the spec.
- **Cons:** the only deterministic AC text on a design target is presence/text
  (fact 1) — orthogonal to fidelity; the one real judge-free fidelity check (the
  static-source-contract observer, fact 2) stays uncounted because it is a
  required-policy check, not AC text. A properly-instrumented target is refused
  unless its author also writes a fig-leaf presence AC.

### Option B: credit the stochastic vision judge toward `n_evaluable`
- **Pros:** admits the thinnest design targets with no instrumentation; the eval
  is falsifiable, not taste.
- **Cons:** removes the last deterministic anchor — the "all-residual + vacuous
  oracle" false-pass shape ADR-0018 refuses; full gate weight on the most gameable
  surface in the autonomous mode where its defenses are weakest (the 0.7998 field
  report is a judged-only false pass); leans on the self-reported `reviewed`
  string; moves opposite ADR-0036's kill criteria.

### Option C: a deterministic, spec-attributed required-policy check satisfies `n_evaluable`; the stochastic judge never does (chosen)
`n_evaluable` is satisfied by at least one **deterministic check attributed to the
spec under analysis** — a deterministic AC (`oracle_plan` classified), **or** a
deterministic **required-policy check** (`family: command`, e.g. the
static-source-contract observer per ADR-0046) **whose redline corresponds to that
spec**. The stochastic vision eval (`design_fidelity`) **never** satisfies
`n_evaluable`; it stays a `has_signal` source and fidelity component only.
- **Pros:** gives a design spec a **real deterministic fidelity floor** (fact 2)
  counted toward its own evaluability — not Option A's fig leaf; keeps the judge
  out of the evaluability leg (ADR-0005/0033/0036); counts deterministic value
  wherever it lives (AC text or required-policy check).
- **Cons:** a gate change beyond 030-01's scope (a new read of the required-runtime
  check plan) **and** it must get **attribution** right: the static `checks.json`
  is per-target (fact 4), so an unqualified credit would let an unrelated
  all-residual spec on an instrumented target pass — reintroducing Option B's
  false pass. The credit must be bound to the spec the check attributes to. Also,
  the observer needs the vellum producer closure, so C admits vellum-style
  targets, not every design target.

## Recommended Decision

**Option C**, as a decision with three load-bearing constraints; the exact
integration is the implementing slice's work:

1. **Deterministic only.** `n_evaluable` is satisfied by a deterministic check —
   a deterministic AC or a `family: command` required-policy check. The
   **stochastic vision eval never** satisfies `n_evaluable` (rejects Option B); it
   stays `has_signal` + fidelity component.
2. **Spec-attributed.** A required-policy check credits `n_evaluable` only for the
   spec whose redline it corresponds to — never target-globally (fact 4). An
   unattributed credit is forbidden, because it would pass an unrelated
   all-residual spec on the same target.
3. **Judge-excluded.** The credit reads the deterministic check plan, never the
   `design_fidelity` component (fact 3).

With these, a design-led target reaches `suitable` by pairing the vision eval
(fidelity signal) with its *own* static-source-contract check (the deterministic
fidelity floor), while an all-residual spec with no deterministic check of its own
— and no attributed required-policy check — stays `needs_evidence`, correctly.

The ADR fixes the **decision and its constraints**, not the mechanism. The
follow-up slice owns the integration — which required-runtime plan to read, how to
match a check's redline to the spec under analysis (fact 4's attribution), and the
timing — and its tests are where attribution/judge-exclusion bugs get caught. The
ADR deliberately does not pin those, because they are implementation that belongs
under test, not in the decision record.

## Consequences

**Becomes easier:**
- A design spec with its own static-source-contract check reaches `suitable` on a
  **real deterministic fidelity floor**, not a presence/text fig leaf.
- `n_evaluable` recognizes deterministic value wherever it lives (AC text or an
  attributed required-policy check), while the judge stays a component — the
  composite posture holds.

**Becomes harder:**
- A gate change beyond 030-01: suitability must read the required-runtime check
  plan and enforce **attribution** (the check's redline ↔ the spec under
  analysis), while never reading the stochastic `design_fidelity` component into
  `n_evaluable`. Attribution is the load-bearing part — get it wrong and Option
  B's false pass returns.
- The observer needs the vellum producer closure; a closure-less design target
  still needs a deterministic AC. The gap is narrowed, not fully closed.

## Assumptions

- The static-source-contract observer is a deterministic (`family: command`),
  judge-free required-policy check at the fixed path
  `<target>/spec/oracle/static/checks.json`, reliably readable by the gate
  (verified against the code); its absence is fail-closed (`n_evaluable` stays 0).
- The check's redline can be **attributed** to the spec under analysis, so the
  credit can be scoped to it. A handle plausibly exists — the single-redline-per-
  target identity (vellum's case: one target carries one redline for one design
  spec, so the correspondence holds by construction), or an explicit binding the
  slice adds. It is **not** the static contract's own `source_spec_path`/`spec_id`:
  those are synthetic redline literals (`"static"` / `spec/static.md`), not a
  feature-spec handle, and collide in name with the feature-spec `source_spec_path`
  in `oracle_plan`/`required_runtime` — do not attribute via them. Confirm the
  handle at implementation; if none can be sealed, the first Kill criterion fires.

## Kill criteria

- A deterministic required-policy check **cannot be reliably attributed** to the
  spec under analysis (no stable handle binding the check's redline to a spec).
  Then crediting it would leak to unrelated specs (fact 4 / Option B's false
  pass), so required-policy-check crediting must be abandoned and the gap closed
  only via a deterministic AC (Option A).
- **No** real design target carries an attributable static-source-contract check
  (the vellum closure proves too rare). Then C helps no one in practice, and the
  gap stays open pending a generalized judge-free fidelity rung.

## Open questions

- The attribution mechanism — how the gate binds a required-policy check's redline
  to the spec under analysis, and which plan it reads — is the follow-up slice's
  load-bearing design, under test. Out of scope here.
- Does a generic (non-vellum) design target have any judge-free deterministic
  fidelity rung, or only targets with the vellum producer closure? If only vellum,
  is generalizing that producer path a worthwhile larger follow-up? Out of scope.
