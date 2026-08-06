---
status: DEFERRED
dependencies: [023-01, adr-0029, adr-0018]
arch_review: true
last_verified: 2026-08-06
---

## Slice 023-02 — loop.py readiness preflight (the two unattended surfaces)

**Resolution trigger:** slice 023-01 is DONE (the `autonomy-readiness` skill + its
`check` consumer contract exist and are landed).

**Goal:** Wire the two unattended long-horizon launch surfaces of slice
003-08/ADR-0008 to auto-consult 023-01's readiness `check` contract, so an
unattended run cannot *start* — nor be *scheduled as a recurring Routine* — on an
unapproved premise. Implements the refuse-without-readiness preflight of
[ADR-0029](../../decisions/adr-0029-autonomy-readiness-gate.md), scoped off the
heartbeat per [ADR-0018](../../decisions/adr-0018-suitability-gates-compile-not-heartbeat.md).

**DoR:**
- ✅ [ADR-0029](../../decisions/adr-0029-autonomy-readiness-gate.md) Accepted;
  discriminator + regression-guard design settled by the frame-critique.
- ⬜ 023-01 DONE — the `check` contract and goal-id scheme it consumes must exist.
- ⬜ Confirm the existing `loop.py` `--background` / `--emit-routine-prompt` tests
  and how they must account for the new gate (env bypass `SERVO_READINESS_GATE=0`
  vs. seeding an approved artifact), so no regression.

**Acceptance Criteria:**

1. **`--background` refuse-to-start.** `loop.py --background --prompt <brief>`
   refuses (rc=2, structured `terminal_reason`) unless an `approved` readiness
   artifact exists for the goal (goal-id derived from `--prompt`, matching
   023-01's scheme). Observable: refused with no/`proposed` artifact; proceeds
   once `approved`.
2. **`--emit-routine-prompt` refuse-to-emit.** `loop.py --emit-routine-prompt`
   refuses to emit the Routine prompt under the same rule. Observable: refused
   while unapproved; emits once approved.
3. **Heartbeat exemption — loop-layer regression guard.** A `loop.py --prompt`
   run setting **neither** flag, with no readiness artifact, is **not** refused
   for missing readiness (asserted at the loop.py layer, not by
   absence-in-`heartbeat.py`). Observable: the existing heartbeat-dispatch path
   (synchronous `--prompt`) is green.
4. **Launch-surface coverage assertion** (frame-critique follow-up #1). The gate
   is pinned to an explicit unattended-launch-surface set; a test asserts the set
   so a future third surface can't silently escape.
5. **Bypass seam.** `SERVO_READINESS_GATE=0` (also `false`/`off`/`no`) skips the
   gate, mirroring servo's gate-bypass idiom, so out-of-band / existing tests are
   unaffected.

**DoD:**
- [ ] All ACs pass; **loop.py's existing suite stays green** (no regressions).
- [ ] Each AC covered by ≥1 test; each new test shown capable of failing.
- [ ] Reviewed (compliance + craft; +arch — edits the loop.py core + a launch contract).
- [ ] Deviation log + reconciliation sweep recorded under this slice.
- [ ] Disclosed limit recorded: `--emit-routine-prompt` gates at emit time only
      (frame-critique follow-up #2) → refinement-todo.

### Close-out (post-DONE)
- [ ] `docs/specs/README.md` regenerated (status-board).
- [ ] Product-vision / README note that unattended launches consult readiness.

**Anti-horizontal-phasing check:** After this slice, an operator who runs
`loop.py --background` (or `--emit-routine-prompt`) on an unapproved premise is
refused end-to-end — the readiness gate goes from "a human consults it" (023-01)
to "the launcher enforces it" (023-02).

### Deviation log (after reconciliation)

_TBD — DEFERRED until 023-01 is DONE._

### Reconciliation sweep

_TBD — DEFERRED until 023-01 is DONE._
