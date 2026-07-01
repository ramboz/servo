---
status: DEFERRED
dependencies: [016-01, 016-02, 016-03, 007]
last_verified:
---

## Slice 016-04 — skill-surface

**Goal (pre-SPIDR — no ACs):** Ship the `/servo:execution-plan` skill surface
(house-style SKILL.md: fire / Do-NOT-fire triggers, `--json`, sibling pointers,
refusal table) + the install-contract entry (007), making `compile` usable and
self-explaining. Closes spec 016.

**DEFERRED — resolution trigger:** activates once **016-01..03 are DONE** and the
helper is stable enough to wrap in a skill surface.

> **Re-scoped by [ADR-0018](../../decisions/adr-0018-suitability-gates-compile-not-heartbeat.md).**
> The original sketch also had the heartbeat "reuse a plan across passes." That is
> **removed**: heartbeat findings are spec-less, so a per-`spec-id` plan has
> nothing to bind to at the dispatch boundary. This slice is the skill surface
> only. Kept as a stub so the spec does not falsely roll up DONE.
