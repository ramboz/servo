---
status: DEFERRED
dependencies: [008-01, 008-02, 008-03, adr-0005]
last_verified:
---

## Slice 008-04 — frozen-params-and-emit

**Goal (pre-SPIDR — no ACs):** Set the frozen `n` / `δ` / threshold / judge
model+params with sane defaults and plain-language trade-off guidance (ADR-0005:
too-wide `δ` never passes, too-narrow flaps), then emit the eval definition in
the exact shape `/servo:spec-oracle`'s eval-family extension compiles into a
frozen `score_<name>`. Closes spec 008: this skill authors, spec 006 compiles,
`gate.py` runs.

**DEFERRED — resolution trigger:** activates once **008-01..03 are DONE** and a
real dataset + rubric exist to set frozen params against. ADR-0005 itself
defers default `n`/`δ` to "the first real EDD spec" — this slice inherits that
same gate; guessing defaults now would just be ADR-0005's deferred guess made
twice.

> Kept as a stub so the spec does not falsely roll up DONE.
