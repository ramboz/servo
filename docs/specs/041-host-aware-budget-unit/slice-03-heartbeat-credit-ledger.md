---
status: DRAFT
kind: feature
dependencies: [041-02]
last_verified:
---

## Slice 041-03 — heartbeat credit ledger

**Goal:** A heartbeat pass on a Copilot-hosted target is bounded by a
whole-pass AI-credit ceiling, kept strictly apart from USD.

**DoR:** 041-02 DONE.

**Acceptance Criteria (sketch):**

1. `heartbeat.py run --host copilot --credit-ceiling N` forwards the host and
   the remaining whole-pass credits to each dispatched loop.
2. `outcome` records `credits` (number or `null`). A `null` is never summed as
   0: it stops the pass with rc=2 and the remaining candidates stay `open`.
3. A whole-pass ceiling sums only outcomes in its own unit. An inbox pass that
   would mix USD and credit outcomes under one ceiling refuses with rc=2.
4. With no `--host copilot`, heartbeat behaviour is byte-identical.

**DoD:** ACs pass; docs updated; reviews.

**Anti-horizontal-phasing check:** an unattended Copilot heartbeat stops at a
credit budget the user set, across all the findings it dispatches.
