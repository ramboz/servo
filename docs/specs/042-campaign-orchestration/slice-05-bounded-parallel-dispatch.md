---
status: DRAFT
kind: feature
dependencies: [042-02]
last_verified:
arch_review: true
frame_review: true
---

## Slice 042-05 — bounded parallel dispatch

**Goal:** `campaign next` may dispatch up to `max_parallel` (> 1) servo-driven
workers at once, under an **aggregate** cost ceiling enforced before each
dispatch on Σ recorded spend + Σ reserved per-worker ceilings of the live
workers. This is the concurrency step; it is deferred out of the parity release
because `max_parallel` defaults to 1 and A2 is unverified.

**DoR:**
- 042-02 is DONE (serial dispatch + reservation reconciliation).

**Acceptance Criteria:**

1. `campaign next <id>` dispatches additional ready items up to `max_parallel`,
   each in its own worktree. `max_parallel` is read from the plan and defaults
   to 1 (serial, i.e. 042-02's behaviour) when unset.
2. Before each dispatch, the aggregate ceiling is enforced on Σ recorded spend
   (servo + verified wrapped) + Σ reserved per-worker ceilings of live workers.
   A dispatch that would breach the aggregate ceiling is refused and the item
   stays queued.
3. A per-worker reservation is held only while that item's `loop.py` run is
   live; it is reconciled on wake (042-02 AC4) across all live workers, so a
   killed worker among several releases only its own budget.
4. The ledger's `flock` + atomic-write discipline keeps the ledger consistent
   under concurrent `campaign record` writes from parallel workers.
5. If parallel workers routinely conflict on shared target resources, the plan
   can cap `max_parallel` at 1 and keep only the planned-list and ledger value
   (ADR-0049 kill criterion); the cap is per-campaign.

**DoD:** ACs pass with tests (concurrent record under lock; aggregate-ceiling
refusal); compliance + craft + arch reviews; reconciliation.

**Anti-horizontal-phasing check:** a campaign with `max_parallel: 3` runs three
workers at once under one aggregate budget, the ledger stays consistent, and a
killed worker's reservation is recovered — bounded parallelism end to end.

## Assumptions

- **A2 (resource contention):** parallel worktree workers on one machine don't
  contend on shared resources (ports, caches, the target's build dirs) for
  typical targets. Unverified; this slice is why `max_parallel` default stays 1
  until a real campaign raises it.
