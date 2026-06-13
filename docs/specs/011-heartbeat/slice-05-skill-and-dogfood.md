---
status: DRAFT
dependencies: [011-02, 011-03, 011-04]
last_verified:
---

## Slice 011-05 — skill-and-dogfood

**STATUS: DRAFT**

**Goal:** `/servo:heartbeat` SKILL.md — **Tier-2 explicit-opt-in** framing, the
read-only-discovery promise, the whole-heartbeat-ceiling warning up front, the
refusal table, and the **Routine-wiring recipe** (cron / CI `schedule:` /
scheduled agent). Plus an end-to-end dogfood driving the real discover → triage
→ preflight → worktree → loop → record chain on a fixture target.

> **Goals-only stub — ACs deliberately not pinned yet.** Closes spec 011: the
> skill surface documents all four guardrails (including #4, untrusted
> discovered content) and the dogfood exercises the spec-level DoD scenario. The
> close-out reconciliation finalizes `docs/architecture.md` (the inbox-schema
> row, once 011-02 pins the `finding_id` + status contract and its ADR is
> Accepted), the README skills-table row → DONE, and product-vision backlog #7.
> **To begin:** SPIDR-split into fleshed ACs and transition to
> `READY_FOR_REVIEW`. `DRAFT` stub so spec 011 rolls up `IN_PROGRESS`.
> `dependencies:` provisional; refine at split.
