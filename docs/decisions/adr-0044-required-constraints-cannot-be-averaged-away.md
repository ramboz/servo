---
status: Proposed
dependencies: []
last_verified:
frame_review: true
---

# ADR-0044: Required constraints cannot be averaged away

## Status

Proposed (2026-10-14)

## Context

Servo's oracle reduces a build to a single **composite quality score** — a
weighted average of its component scores — and gates completion on that score
clearing a `THRESHOLD` (`skills/quality-gate/gate.py`;
`skills/spec-oracle/examples/required-policy.md`). A weighted average is the
right shape for *quality* dimensions that trade off: a slightly weaker lint
score can be offset by stronger tests, and the threshold picks the acceptable
blend.

But not every check is a quality dimension. Some are **requirements**: the
submit button must exist, the migration must be reversible, the mandatory
assertion must hold. A requirement is not a dimension you spend points on — it
either holds or the build is not done, however good everything else looks.

Folding a requirement into the weighted average destroys that distinction. Give
"the submit button exists" a weight and a score, and a build with a missing
button still clears a 0.8 threshold as long as the other components score high
enough — the average *buys off* the failed requirement. Raising the weight only
moves the magic number; it never restores the "this MUST hold" semantics, and it
corrupts the threshold into an encoding of requirements rather than a quality
bar. Worse, **unavailable** evidence (a check that could not run) reads as a low
score rather than an honest "unknown", so a requirement can be averaged away
*without ever having been evaluated*.

**Scope — this ADR governs deterministic requirements.** It applies to the
`command` and `generated_artifact_command` check families that the shipped
required-constraint runtime evaluates, and no others. That runtime already
embodies the separation (`required_policy` schema 1, the gate's required/quality
decision table, and `--enable-required --weight 0`; see
`skills/quality-gate/required_runtime.py` and
`skills/spec-oracle/test_required_gate.py`); this ADR records the principle so
future scoring work cannot quietly re-blend the two for a deterministic check.

**Out of scope — graded or model-judged requirements.** A probabilistic eval
that "must hold" cannot be expressed as a required constraint today: the runtime
forces any non-command required family to `unknown`
(`skills/spec-oracle/examples/required-policy.md`: "a required residual or
unsupported family stays unknown"). Whether the eval-scoring cluster (specs
035/039) needs a separate *graded-required* axis is a later decision this ADR
deliberately does not settle (see Kill criteria and Open questions). Note in
particular that spec 039's eval is a graded **quality** component — its
"re-judge failure is `env_error`, never the cheap score" is the quality path's
own unavailability handling, not an instance of the required axis — and spec 035
is still an unwritten stub; neither is a consumer of this decision.

## Decision Options Considered

### Option A: One weighted average — model requirements as high-weight components
- **Pros:** one number, one threshold, one code path; nothing new to reason
  about; authors already understand weights.
- **Cons:** a high average still buys off a failed requirement — the exact
  failure this ADR exists to prevent; the threshold stops meaning "quality bar"
  and starts secretly encoding requirements; "unavailable" collapses into a low
  score, so a requirement can pass-by-omission without being evaluated; the
  single number loses the diagnostic ("was it quality or a requirement?").

### Option B: A separate required verdict, not blended into the quality average (chosen)
- **Pros:** a requirement cannot be traded against quality points — the gate
  passes only if **every** required constraint passes **and** quality ≥
  threshold, and the required verdict is computed separately from the composite,
  so a failed requirement is never diluted by high-scoring components; it can be
  fully decoupled from the quality average by carrying the required check in its
  own **weight-0 component** (beside the scaffold's weighted baseline, so the
  weight-0 one contributes no quality points while still gating); unknown
  required evidence is a first-class `env_error` that takes precedence over any
  score, so unavailable evidence never reads as pass; the distinct reasons
  (`required_constraints_failed`, `quality_below_threshold`) keep the diagnostic
  honest.
- **Cons:** two outcomes to reason about instead of one; authors must correctly
  classify a check as *required* vs *quality*; `weight` is a **per-component**
  property while *required* is a **per-check flag**, so a required check whose
  component carries weight > 0 still folds its score into the composite — the
  clean, no-quality-contribution separation needs the required check in a
  dedicated weight-0 component (the canonical install is `baseline:1` +
  `required-component:0`); a requirement with no `required` flag still averages
  away (the principle guides authoring, it cannot enforce intent).

### Option C: Required as a veto multiplier on the composite (composite × 0 on any required fail)
- **Pros:** keeps a single surfaced number; a failed requirement forces the
  composite to 0, so it cannot be averaged away.
- **Cons:** collapses the diagnostic — a 0 composite cannot distinguish "a
  requirement failed" from "quality was genuinely zero"; unknown/unavailable
  evidence has no honest representation (0 looks like a hard fail, not an
  `env_error`); recovering *which* requirement vetoed needs a side channel
  anyway, so the "one number" simplicity is illusory.

## Recommended Decision

**Option B.** A required constraint produces a **separate pass/fail verdict**
that is never blended into the weighted quality average. The gate authorizes
completion only when **every required constraint passes and** the composite
quality score clears the threshold. A failed required constraint fails the gate
(`required_constraints_failed`) regardless of how high the quality average is;
**unknown** required evidence errors the gate (`required_evidence_unavailable`,
rc 2) and takes precedence over any score — unavailable evidence is never a pass.
Being *required* is a per-check flag, independent of a component's quality
*weight*: to keep a required check out of the quality average entirely, give it
its own weight-0 component beside the scaffold's baseline; it still gates. Quality
and required outcomes are reported **side by side**, each with its own status and
reason, so neither can mask the other.

This is how the shipped required-constraint runtime behaves for deterministic
`command` requirements; this ADR makes the principle load-bearing so future
scoring work cannot re-fold a deterministic requirement into the average without
superseding this decision. It deliberately does **not** extend to graded or
model-judged requirements, which the current runtime cannot express (see Scope).

## Consequences

**Becomes easier:**
- An author can state a hard deterministic requirement (`"required": true` on a
  `command` / `generated_artifact_command` check) without inventing a weight and
  threshold that approximate "mandatory".
- A green composite can no longer hide a failed deterministic requirement, so a
  reviewer can trust the gate's `pass`.
- Future scoring work inherits a recorded boundary: a deterministic requirement
  is a verdict, not a quality point, so it will not be re-blended by accident.

**Becomes harder:**
- Every scoring consumer must carry and display two outcomes, not one number; a
  caller that reads only the composite must also read the required status.
- Authors bear a classification burden: a requirement wrongly placed in the
  quality bucket — or carried in a component with weight > 0 — still contributes
  to the average; tooling can warn, but cannot decide intent.
- A *graded* requirement (a model-judged eval that must hold) is not expressible
  under this decision; the eval-scoring cluster must keep such checks on the
  quality axis or raise a separate graded-required decision.

## Assumptions

None load-bearing for the scoped claim. The required/quality separation for
deterministic `command` requirements — including the command-only family
restriction — is observed in shipped code (`required_policy` schema 1, the gate's
required/quality decision table, `skills/quality-gate/required_runtime.py`,
`skills/spec-oracle/examples/required-policy.md`,
`skills/spec-oracle/test_required_gate.py`), not an unverified claim.

## Kill criteria

- A real target needs a *graded* requirement (partial credit for a mandatory
  constraint, or a model-judged eval that must hold) often enough that a binary,
  command-only pass/fail verdict is the wrong model — then requirements need a
  separate graded-required axis, a decision this ADR explicitly defers rather
  than pre-empts.
- The two-outcome result proves consistently confusing in practice (consumers
  mis-read a `pass` quality score as overall pass), such that a single vetoed
  number (Option C) would be read more safely despite losing the diagnostic.

## Open questions

- Does the eval-scoring cluster (specs 035/039) actually need a *graded-required*
  axis — a model-judged eval that must hold — and if so, with what semantics?
  The current command-only runtime cannot express it, so it is a separate
  decision, not settled here.
- Should servo *warn* at authoring/plan time when a check reads like a
  requirement ("must", "never") but is left in the quality bucket with no
  `required` flag? (A lint, not part of this decision.)
