---
status: DONE
dependencies: [015-01, 015-02, 016-01, adr-0015, adr-0018]
last_verified: 2026-06-30
---

## Slice 015-03 — compile-precondition (re-scoped)

**Goal:** Make the verdict a **gate at the Servo Compile boundary**: the Compile
entry path proceeds only on a `suitable` verdict; a `needs_evidence` /
`unsuitable` verdict **halts Compile** and surfaces `reasons` + `missing_evidence`
as the actionable next step (no oracle synthesis, no run). This turns ADR-0015
from a document into a refusal the system performs — at the one boundary where the
verdict has the input it needs (a real spec with ACs).

> **Re-scoped 2026-06-28 by [ADR-0018](../../decisions/adr-0018-suitability-gates-compile-not-heartbeat.md)
> (Accepted), on the [015-05](slice-05-suitability-boundary-spike.md) spike.** The
> original slice also wired the verdict into the **heartbeat per-finding dispatch
> gate**. The spike measured that to be incoherent: the verdict is spec-centric
> but heartbeat findings are spec-less (ephemeral-spec synthesis → `needs_evidence`
> for 36/36 findings, an off switch; 0/3 actionable findings carry a recoverable
> spec; the heartbeat already gates evaluability via `gate.py`). So the **heartbeat
> gate is retired** — the heartbeat keeps `gate.py`, and **011-02's human-only
> `skipped` contract stands unchanged** (no inbox-contract evolution, no new
> automated `skipped` setter; the old assumptions A1/A2 are moot). A finding-shaped
> evaluability check, if ever wanted, is deferred to spec 018. Only the **Compile
> precondition** remains in scope here.

**Resolution trigger:** Re-open when spec **016 (execution-planner)** lands a
**Servo Compile entry point** (the `/servo:edd-suitability → Compile` handoff /
plan build) that this precondition can gate. Until a Compile entry exists, gating
a phase that isn't implemented is not a vertical slice.

> **✅ Re-opened IN_PROGRESS 2026-06-30 — trigger met.** Spec
> [016-01](../016-execution-planner/slice-01-plan-emit.md) landed the Servo Compile
> entry point (`execution_plan.py compile`), which already **enforces the
> `suitable`-only gate**. This slice adds the remaining **enrichment** on top of
> that helper: surface the full `reasons` + `missing_evidence` list on refusal
> (AC1), the explicit fail-closed-on-unavailable tests (AC2), and the
> heartbeat-has-no-suitability-dependency regression assertion (AC3). Implementation
> surface: `skills/execution-planner/execution_plan.py` (+ `test_execution_plan.py`)
> — the Compile boundary lives there, which is exactly why 015-03 waited on 016.

**DoR:**
- ✅ **015-01 + 015-02 DONE** — `suitability.py analyze <target> --spec <path>`
  emits the verdict + populated `missing_evidence` at
  `<target>/.servo/suitability/<spec-id>.json`; subprocessed (never imported).
- ✅ **ADR-0018 Accepted** — fixes the scope to the Compile precondition only.
- ✅ **016 Compile entry point** — `execution_plan.py compile` (016-01, DONE
  2026-06-30) is the consumer this precondition gates; it already enforces the
  `suitable`-only refusal. Trigger MET — remaining 015-03 work is enrichment
  (surface `missing_evidence`, AC2/AC3 tests).

**Acceptance Criteria (re-scoped):**

1. **Compile precondition.** The Compile entry path (the documented
   `/servo:edd-suitability` → Compile handoff, owned by 016) proceeds only on a
   `suitable` verdict; a non-`suitable` verdict halts Compile and surfaces
   `reasons` + `missing_evidence` as the next step (no oracle synthesis, no run).
   *Test:* `CompilePreconditionTests`.

2. **Fail-closed on an unavailable verdict.** If `suitability.py` cannot produce a
   verdict (exit 2 / no artifact / unparseable) for the spec, Compile **does not
   proceed** — an unavailable verdict is treated as non-`suitable`. A broken
   analyzer never opens the Compile gate. *Test:* `CompileGateFailClosedTests`.

3. **Boundary stays honest.** `heartbeat.py` does **not** import or subprocess
   `suitability.py` — the verdict is a Compile-phase gate only (ADR-0018). *Test:*
   a regression assertion that the heartbeat has no suitability dependency.

> **Retired by ADR-0018 (were AC1–4, AC6):** per-finding heartbeat gate before
> dispatch; non-`suitable` ⇒ `skipped` + suitability `actionable_reason`; `skipped`
> provenance; heartbeat fail-closed; spine-safe `skipped` write. These assumed a
> finding→spec linkage that does not exist; the heartbeat keeps `gate.py`.

**DoD:**
- [x] AC1–3 pass; tests added (5, in `test_execution_plan.py`); `ruff check .`
      clean (0.15.17).
- [x] Reviewed by jig compliance + craft passes (maintainer self-review; recorded
      under `reviews/slice-03-{compliance,craft,reconciliation}.md`).
- [x] Deviation log produced under this slice heading (below).
- [x] `docs/specs/README.md` hand-updated (machinery not vendored); 015-03 moved to
      DONE and out of the Deferred-slices table.

### Close-out (post-DONE)
- [x] ADR-0018's Compile-only boundary is reflected in the `execution_plan.py`
      docstring + the `BoundaryHonestyTests` regression guard.

### Deviation log (after reconciliation)

Original (re-scoped) ACs preserved above; the implementation deviated as follows:

- **Implementation surface is spec 016's helper, not a new 015 file.** The Compile
  boundary lives in `skills/execution-planner/execution_plan.py` (016-01), so
  015-03's enrichment (`_format_refusal` surfacing `reasons` + `missing_evidence`)
  and its three AC tests (`CompilePreconditionTests`, `CompileGateFailClosedTests`,
  `BoundaryHonestyTests`) live in `execution_plan.py` / `test_execution_plan.py` —
  exactly the cross-spec dependency that deferred 015-03 until 016 existed.
- **Gate mechanism vs enrichment split.** The `suitable`-only refusal itself
  shipped with 016-01 (AC3 of that slice); 015-03 adds only the *actionable
  message* + the fail-closed and boundary regression tests. No new exit code, no
  schema change — the enrichment is stderr-text only.
