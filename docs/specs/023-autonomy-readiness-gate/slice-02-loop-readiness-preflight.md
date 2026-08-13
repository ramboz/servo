---
status: DONE
dependencies: [023-01, adr-0029, adr-0018]
arch_review: true
last_verified: 2026-08-12
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
- ✅ 023-01 DONE — the `check` contract (`readiness.py check <target> --prompt`,
  exit `0` permit / `1` refuse / `2` env-error) and its `_goal_id` scheme are
  landed on `origin/main` (PR #24).
- ✅ Confirmed the existing `loop.py` surface tests (`BackgroundDispatchTests`,
  `EmitRoutinePromptTests`, `BackgroundFlagConflictTests`) and the two `main()`
  entry points (emit-routine returns at the `_emit_routine_prompt` branch;
  `--background` parent dispatches via `run_goal_loop_background`; the detached
  child re-exec and the synchronous heartbeat `--prompt` path are both exempt by
  construction). Regression-free approach: env bypass `SERVO_READINESS_GATE=0`
  for existing tests; approved-artifact seeding for the positive-path tests.

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
- [x] All ACs pass; **loop.py's existing suite stays green** (no regressions). 333 passed, 0 failed.
- [x] Each AC covered by ≥1 test; each new test shown capable of failing (mutation-verified, incl. the fail-closed branch).
- [x] Reviewed (compliance + craft; +arch — edits the loop.py core + a launch contract). All three PASS.
- [x] Deviation log + reconciliation sweep recorded under this slice.
- [x] Disclosed limit recorded: `--emit-routine-prompt` gates at emit time only
      (frame-critique follow-up #2) → refinement-todo (docs/refinement-todo.md, "autonomy-readiness — Routine recurrence re-verifies premise only").

### Close-out (post-DONE)
- [x] `docs/specs/README.md` regenerated (status-board).
- [x] Product-vision / README note that unattended launches consult readiness.

**Anti-horizontal-phasing check:** After this slice, an operator who runs
`loop.py --background` (or `--emit-routine-prompt`) on an unapproved premise is
refused end-to-end — the readiness gate goes from "a human consults it" (023-01)
to "the launcher enforces it" (023-02).

### Deviation log (after reconciliation)

Implementation followed the ACs faithfully; the original ACs above are preserved. Deviations
and post-implementation changes:

- **Fail-closed branch coverage added (compliance review, High).** The first implementation left
  the `readiness_check_unavailable` branch (`readiness_rc != 0` → refuse rc=2: env-error / spawn
  failure / timeout) untested, so a fail-*open* regression would have survived. The fix-up round
  added two end-to-end tests (`ReadinessBackgroundGateTests` + `ReadinessEmitRoutinePromptGateTests`
  `::test_refuses_when_the_readiness_check_itself_fails`, driving a missing target so real
  `readiness.py check` returns rc=2 through `main()`) plus `ReadinessCheckDetailUnitTests`, and
  demonstrated red-capability (deleting the branch fails both). AC coverage is now 5/5 with every
  new test shown capable of failing.
- **`_readiness_check_rc` return widened `int` → `(int, str)` (compliance Medium + craft nit + arch
  nit — same root).** It now returns a bounded (last 500 chars, stripped) snippet of the
  subprocess's stderr, folded into the `readiness_check_unavailable` refusal message so a broken /
  partial readiness install names its underlying cause (`readiness.py`'s `error: <reason>:
  <message>` breadcrumb, e.g. `target_missing`) instead of a bare exit code. Fail-closed semantics
  unchanged; the `readiness_unapproved` (rc=1) message unchanged.
- **Cosmetic tidy (craft nit).** Dropped the redundant parens in `_readiness_gate_bypassed`'s
  bypass-set membership check.
- **Test-harness seam (regression-free).** `_run_loop`/`_run_raw` now default
  `SERVO_READINESS_GATE=0`, so every pre-existing `--background` / `--emit-routine-prompt` / `--plan`
  surface test is unaffected; the new readiness tests re-enable the gate explicitly. This is the
  regression-avoidance mechanism the DoR called for (env-bypass over artifact-seeding for legacy
  tests).

Deferred (non-blocking nits → refinement-todo, not addressed inline):
- Preflight subprocess isn't registered as `_active_subprocess`, so a SIGINT during the preflight
  waits up to the 30s timeout (craft nit 2) — benign: the preflight runs before signal handlers are
  installed and before any run starts.
- The AC4 pin (`_READINESS_GATED_SURFACES`) and `_readiness_gated_surface()` are parallel literals;
  the tuple-assertion test tripwires the tuple's value but doesn't *force* a new surface to be added
  to the tuple (arch nit 1). Airtight fix: derive the mapping from the tuple, or assert every gated
  dest routes through it.

### Reconciliation sweep

- **Generated host copies** (`hosts/claude/skills/agent-loop/loop.py`,
  `hosts/codex/plugins/servo/skills/agent-loop/loop.py`) — **updated**: regenerated from the
  canonical `skills/agent-loop/loop.py` via `scripts/build_host_packages.py` (spec 022 dual-host
  parity; these are build artifacts, never hand-edited).
- **docs/refinement-todo.md** — **updated**: the disclosed emit-time-only limit was recorded round 1;
  the two deferred nits above appended this round.
- **docs/product-vision.md** — **updated**: noted that unattended launches
  (`--background` / `--emit-routine-prompt`) now consult (enforce) the readiness gate (close-out
  item). The root `README.md` was deliberately **not** touched — the DoD close-out is
  "product-vision / README" (either suffices), and product-vision's autonomy section is the
  accurate home for this note.
- **docs/architecture.md** — **no-op**: the servo↔readiness coupling is subprocess+filesystem only
  (no new module boundary or public contract); the launch-surface gate is already described by
  ADR-0029 and spec 023. No new load-bearing decision with rejected alternatives (the
  subprocess-not-import choice was pre-decided by `readiness.py:_goal_id`'s arch note), so no new ADR.
- **ADR-0011 citation drift (surfaced by arch pass) — deferred**: spec.md Goal 5 / the reuse-seam
  cite "ADR-0011 boundary" for the servo↔jig subprocess+filesystem rule, but servo's ADR-0011 is
  host-native-phase-hints; the boundary the code honors is "no servo→sibling Python import," stated
  correctly in ADR-0029's Verification section. This is inherited spec-authorship drift from 023
  framing (023-01 already landed), **not** introduced by this slice's implementation. Surfaced to the
  owner for a separate spec-prose correction rather than amended here (closed/landed-record
  authorisation discipline).
- **docs/inbox.md** — **no-op**: no open items resolved by this slice (none present at repo root).
- **Mechanical ceremony artifacts** — **updated**: `spec.md` frontmatter `status:` is a derived
  rollup written by `workflow.py transition`; `reviews/slice-02-{compliance,craft,arch,
  reconciliation}.md` are the recorded review verdicts; `docs/specs/README.md` is regenerated by
  `status-board`. Deliverables `skills/agent-loop/loop.py` + `test_loop.py` are the slice itself.

> **Scope note for reconciliation:** the changed-file set for this slice, measured against
> `origin/main`, is exactly the 12 paths above (deliverable + host mirrors + these docs/evidence
> files). A `main...HEAD` diff over-reports here because this checkout's local `main` ref is stale
> (points at a superseded pre-squash spec-021 commit, 7 behind `origin/main`); the authoritative
> baseline is `origin/main`.
