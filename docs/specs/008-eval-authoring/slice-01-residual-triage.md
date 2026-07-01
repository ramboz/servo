---
status: DEFERRED
dependencies: [006, adr-0005, adr-0019]
last_verified:
---

## Slice 008-01 — residual-triage

**Goal (pre-SPIDR — no ACs):** Given a spec-006 evidence plan's
`residual_judgment` list, classify each AC as **eval-able** (a rubric + dataset
could score it) vs **human-residual** (taste / policy / ADR-shaped — stays
waived), with a recorded rationale per AC. Never silently promote a taste call
into an eval. Ships as part of the single servo-owned guided skill ADR-0019
settled — no jig-side authoring step.

**DEFERRED — resolution trigger:** activates once a real spec-006 plan surfaces
a `residual_judgment` AC that a human actually wants scored — the same "first
real EDD spec" trigger spec 008's own header names. Until a real AC exists to
triage, the eval-able/human-residual boundary and how much rationale counts as
"recorded" can't be pinned without guessing at it.

> Kept as a stub so the spec does not falsely roll up DONE. ADR-0019 already
> settled *where* this runs (a servo skill, not split with jig); it did not
> settle *what* the triage rule looks like — that still needs a real AC.
