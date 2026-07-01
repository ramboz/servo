---
status: DEFERRED
dependencies: [016-02, 003, adr-0008, adr-0016]
last_verified:
---

## Slice 016-03 — clamp-and-review

**Goal (pre-SPIDR — no ACs):** Enforce **clamp-never-loosen** and support human
review. A plan `budget` above the guardrail safe bound (ADR-0008/003) is **clamped
to the bound**, not honored; a human may inspect/adjust the plan
(`provenance: human_edited`) before Run consumes it, and recompile preserves an
`human_edited` plan (or requires re-approval) rather than silently overwriting it
— the spec-oracle freeze/approval posture (006-04).

**DEFERRED — resolution trigger:** activates once **016-02 is DONE** (a consumer
actually reads plan budgets, so clamping has something to clamp) *and* a
human-edit/review need is real. Clamping ACs depend on the exact read seam 016-02
establishes; authoring them earlier would guess at that boundary.

> Kept as a stub so the spec does not falsely roll up DONE.
