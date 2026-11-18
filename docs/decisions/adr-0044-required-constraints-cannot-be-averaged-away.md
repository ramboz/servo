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
assertion must hold, the design's required element must be present. A
requirement is not a dimension you spend points on — it either holds or the
build is not done, however good everything else looks.

Folding a requirement into the weighted average destroys that distinction. Give
"the submit button exists" a weight and a score, and a build with a missing
button still clears a 0.8 threshold as long as the other components score high
enough — the average *buys off* the failed requirement. Raising the weight only
moves the magic number; it never restores the "this MUST hold" semantics, and it
corrupts the threshold into an encoding of requirements rather than a quality
bar. Worse, **unavailable** evidence (a check that could not run) reads as a low
score rather than an honest "unknown", so a requirement can be averaged away
*without ever having been evaluated*.

This matters now because the eval-scoring cluster is being built on the oracle:
spec 035 (required-evidence-alongside-quality scores) surfaces mandatory
evidence next to the averaged score, and spec 039 (variance-gated eval judging)
depends on "a re-judge failure is `env_error`, never the cheap score" — both
assume requirements and unknowns live on a different axis from the quality
average. The required-constraint runtime already embodies that separation
(`required_policy` schema 1, the gate's required/quality decision table, and
`--enable-required --weight 0`); this ADR records the principle so future
scoring work cannot quietly re-blend the two.

## Decision Options Considered

### Option A: One weighted average — model requirements as high-weight components
- **Pros:** one number, one threshold, one code path; nothing new to reason
  about; authors already understand weights.
- **Cons:** a high average still buys off a failed requirement — the exact
  failure this ADR exists to prevent; the threshold stops meaning "quality bar"
  and starts secretly encoding requirements; "unavailable" collapses into a low
  score, so a requirement can pass-by-omission without being evaluated; the
  single number loses the diagnostic ("was it quality or a requirement?").

### Option B: A separate required axis, orthogonal to the quality average (chosen)
- **Pros:** a requirement cannot be traded against quality points — the gate
  passes only if **every** required constraint passes **and** quality ≥
  threshold; required membership is decoupled from quality weight (a required
  component may carry weight 0, contributing no quality points while still
  gating); unknown required evidence is a first-class `env_error` that takes
  precedence over any score, so unavailable evidence never reads as pass; the
  distinct reasons (`required_constraints_failed`, `quality_below_threshold`)
  keep the diagnostic honest.
- **Cons:** two axes to reason about instead of one; authors must correctly
  classify a check as *required* vs *quality*; a requirement mis-filed in the
  quality bucket still averages away — the principle guides authoring, it cannot
  enforce intent.

### Option C: Required as a veto multiplier on the composite (composite × 0 on any required fail)
- **Pros:** keeps a single surfaced number; a failed requirement forces the
  composite to 0, so it cannot be averaged away.
- **Cons:** collapses the diagnostic — a 0 composite cannot distinguish "a
  requirement failed" from "quality was genuinely zero"; unknown/unavailable
  evidence has no honest representation (0 looks like a hard fail, not an
  `env_error`); recovering *which* requirement vetoed needs a side channel
  anyway, so the "one number" simplicity is illusory.

## Recommended Decision

**Option B.** Required constraints are evaluated on a **separate, all-or-nothing
axis** that is never blended into the weighted quality average. The gate
authorizes completion only when **every required constraint passes and** the
composite quality score clears the threshold. A failed required constraint fails
the gate (`required_constraints_failed`) regardless of how high the quality
average is; **unknown** required evidence errors the gate
(`required_evidence_unavailable`, rc 2) and takes precedence over any score —
unavailable evidence is never a pass. Being *required* is independent of quality
*weight*: a required component may carry weight 0 and still gate. Quality and
required outcomes are reported **side by side**, each with its own status and
reason, so neither can mask the other.

This is already how the required-constraint runtime behaves; this ADR makes the
principle load-bearing for all future scoring and eval work, so a later change
cannot re-fold requirements into the average without superseding this decision.

## Consequences

**Becomes easier:**
- An author can state a hard requirement (`"required": true`) without inventing
  a weight and threshold that approximate "mandatory".
- Spec 035 can surface required evidence beside the quality score with clean
  semantics; spec 039's "a re-judge failure is `env_error`, never the cheap
  score" is a direct instance of unknown-never-passes.
- A green composite can no longer hide a failed requirement, so a reviewer can
  trust the gate's `pass`.

**Becomes harder:**
- Every scoring consumer must carry and display two outcomes, not one number; a
  caller that reads only the composite must also read the required status.
- Authors bear a classification burden: a requirement wrongly placed in the
  quality bucket still averages away — tooling can warn, but cannot decide
  intent.

## Assumptions

None load-bearing. The required/quality separation is observed in shipped code
(`required_policy` schema 1 and the gate's required/quality decision table in
`skills/spec-oracle/examples/required-policy.md`), not an unverified claim.

## Kill criteria

- A real target needs a *graded* requirement (partial credit for a mandatory
  constraint) often enough that a binary pass/fail axis is the wrong model —
  then requirements belong on a scored sub-axis, not a hard gate.
- The two-axis result proves consistently confusing in practice (consumers
  mis-read a `pass` quality score as overall pass), such that a single vetoed
  number (Option C) would be read more safely despite losing the diagnostic.

## Open questions

- Should servo *warn* at authoring/plan time when a check reads like a
  requirement ("must", "never") but is left in the quality bucket with no
  `required` flag? (A lint, not part of this decision.)
- Does the required axis need severity tiers (required vs recommended), or is a
  binary required-vs-quality split sufficient for the eval-scoring cluster?
  Deferred until a consumer needs the middle tier.
