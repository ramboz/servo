---
status: DRAFT
dependencies: [011-03]
last_verified:
---

## Slice 011-04 — heartbeat-cost-ceiling

**STATUS: DRAFT**

**Goal:** A **heartbeat-level** hard cost ceiling bounds *discovery (any LLM
assist) + the sum of all dispatched loops* — **not** per-loop. `heartbeat.py
run` = discover → dispatch under this one ceiling; **fail-closed** halt of the
whole pass leaves remaining findings `open` for the next run. Distinct from
`loop.py`'s per-run ceiling (003-02).

> **Goals-only stub — ACs deliberately not pinned yet.** The crystallizing
> decision is the **heartbeat-level vs per-loop cost-ceiling-semantics** call
> (may fold into the 011-02 schema ADR or stand alone; shares DNA with spec
> 005's per-variant-vs-per-race question). ACs should also state the **overshoot
> bound** — a serial-sum ceiling checked *between* dispatches can be exceeded by
> up to one loop's per-run ceiling, since the heartbeat can't preempt a running
> `loop.py` (see spec.md "Out of scope, worth tracking" / the plan-review note).
> **To begin:** SPIDR-split into fleshed ACs and transition to
> `READY_FOR_REVIEW`. `DRAFT` stub so spec 011 rolls up `IN_PROGRESS`.
> `dependencies:` provisional; refine at split.
