---
status: DEFERRED
dependencies: [008-01, adr-0019]
last_verified:
---

## Slice 008-02 — rubric-shaping

**Goal (pre-SPIDR — no ACs):** Interactively turn one eval-able AC (008-01's
output) into a concrete rubric: scoring criteria, scale, and the judge prompt —
the artifact whose hash ADR-0005 clause 2 freezes. Entirely servo-guided per
ADR-0019: no jig-authored rubric intent, no split authoring step.

**DEFERRED — resolution trigger:** activates once **008-01 is DONE** and
produces a real eval-able AC to shape a rubric for. The rubric's concrete shape
(how much scoring-criteria structure, what the scale looks like) depends on
what that AC actually reads like — authoring it earlier would guess at the
boundary.

> Kept as a stub so the spec does not falsely roll up DONE.
