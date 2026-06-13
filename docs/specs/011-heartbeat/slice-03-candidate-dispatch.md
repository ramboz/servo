---
status: DRAFT
dependencies: [011-02]
last_verified:
---

## Slice 011-03 — candidate-dispatch

**STATUS: DRAFT**

**Goal:** Each **actionable, `open`** finding becomes a candidate: `gate.py`
oracle **preflight (refuse-without-oracle)** → an **isolated git worktree** →
`loop.py` (spec 003) → the outcome (`tried` + final oracle status, or `passed`)
is recorded back to the inbox. Nothing spawns a loop without passing the oracle.
(Seam: `race.py` (005) as an alternate dispatch target when it lands.)

> **Goals-only stub — ACs deliberately not pinned yet.** This is the heartbeat's
> one execution edge; its ACs must bind Guardrail #3 (refuse-without-oracle,
> deferring to `gate.py`'s preflight taxonomy per ADR-0002) **and** Guardrail #4
> (discovered content is untrusted input — the dispatch prompt must frame
> issue/commit text as data, never instructions; an optional 011-02 provenance
> marker may inform this). **To begin:** SPIDR-split into fleshed ACs and
> transition to `READY_FOR_REVIEW`. `DRAFT` stub so spec 011 rolls up
> `IN_PROGRESS`. `dependencies:` above is provisional (real deps include 002
> `gate.py` + 003 `loop.py`, both DONE); refine at split.
