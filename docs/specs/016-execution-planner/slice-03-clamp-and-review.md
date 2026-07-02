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
>
> **Trigger partially met (2026-07-02):** 016-02 is DONE — a consumer (`loop.py
> --plan`) now reads plan budgets, so clamping has something to clamp. Two concrete
> 016-03 hooks were surfaced by 016-02's review and recorded in its deviation log:
> (1) plan-sourced budget values currently skip argparse range/type validation and a
> plan-sourced `driver` bypasses the `choices` guard — both unreachable via the
> current `compiled` producer but live once `human_edited` plans exist; (2) the
> `goal_unavailable` refusal summary echoes DEFAULT/args budget rather than the
> plan-resolved budget (`loop.py:3221-3224`). Stays DEFERRED until a real
> human-edit/review need appears; re-open via DRAFT. (When re-opened, also fix the
> bare `003` dependency token → a `NNN-NN` slice fragment, per 016-02's DONE-gate
> lesson.)
