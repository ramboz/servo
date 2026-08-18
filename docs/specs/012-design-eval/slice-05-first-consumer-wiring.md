---
status: DEFERRED
dependencies: [adr-0009]
last_verified: 2026-08-18
---

## Slice 012-05 — first-consumer-wiring

**Goal:** Wire the first real consumer end-to-end — author a project
`config.json` with per-screen setups, capture references, freeze, install, and
run `score_design_fidelity` inside an actual agent-loop so the mechanism is
proven against a live UI rather than against fixtures.

**Resolution trigger:** Resume when a real design-mockup&#8594;UI
project adopts `/servo:design-eval` and can host the wiring. The original
candidate was **food-log** (its slice 002-01 was to be built to `design_v1.0`),
which is a **separate repository** — servo cannot land this work in its own
tree, which is why the slice is parked rather than open. Re-open by
transitioning to `DRAFT` once a consuming project exists and its screens,
rubric, and reference set are available.

**Why it stays parked:** the four mechanism slices (012-01..04) are complete
and shipped; this slice is the only part of spec 012 that is *project* work
rather than *servo* work. Leaving it open would misreport servo as having
unfinished mechanism work, and closing it would claim a live proof that has
never been performed.

_Not started; parked until the resolution trigger fires._
