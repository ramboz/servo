---
status: DONE
dependencies: [001, 006, 015-01, adr-0016]
arch_review: false
frame_review: false
last_verified: 2026-06-30
---

## Slice 016-01 — plan-emit

**Goal:** A new `execution_plan.py compile <target> --spec <path>` assembles the
[ADR-0016](../../decisions/adr-0016-execution-plan-artifact.md) **execution plan**
and writes it to `<target>/.servo/plans/<spec-id>/plan.json` (atomic). The plan
**references** (never copies) the other Compile artifacts — the suitability
verdict (`.servo/suitability/<spec-id>.json`, 015), the oracle (`oracle.sh`, 001),
and the spec-oracle overlay id (006) — and records the planned `budget` / `driver`
/ `prompt_ref` + `provenance: compiled` and `schema_version: 1`. This is the
durable Compile→Run handoff artifact; every later slice (Run consuming it,
clamping, the skill surface) reads what this slice emits.

> **Boundary with 016-02..04.** This slice *emits and persists* the plan; it
> teaches **no** consumer to read it — `loop.py` / the dispatcher reading plan
> defaults is 016-02, budget **clamping** + `human_edited` review is 016-03, and
> the `/servo:execution-plan` skill surface is 016-04. It changes no existing
> caller and does not run the loop (non-goal, 003).

> **The `suitable`-only precondition is the 015-03 seam.** Per ADR-0016, a
> `plan.json` exists **only** for a `suitable` suitability verdict — so `compile`
> refusing to emit a plan on a non-`suitable`/absent verdict *is* the Servo
> Compile precondition that [015-03](../015-edd-suitability/slice-03-pipeline-gate.md)
> (re-scoped, deferred pending 016) describes. Building it here naturally delivers
> that gate at the one boundary where a real spec + verdict exist; reconciliation
> notes whether 015-03 is thereby satisfied.

**DoR:**
- ✅ **ADR-0016 Accepted** (2026-06-30) — the plan location
  (`.servo/plans/<spec-id>/plan.json`), the versioned schema, "reference not
  copy" (incl. `suitability_ref`, not an inlined verdict), the clamp-never-loosen
  posture, and the `suitable`-only-emit invariant are frozen. This slice
  implements its `## Verification` minimum for *emission*: `schema_version` +
  references-not-copies + git-ignored `.servo/plans/`.
- ✅ **015-01 DONE** — the suitability artifact exists at
  `<target>/.servo/suitability/<spec-id>.json` with `verdict ∈ {suitable,
  needs_evidence, unsuitable}`; `compile` reads its `verdict` for the precondition
  and records its *path* as `suitability_ref`. Consult it read-only; never
  re-derive the verdict (that is 015's job).
- ✅ **001 DONE** — `.servo/install.json` records the oracle + detected signals;
  `oracle.sh` is the referenced oracle path. Verify the manifest fields the plan's
  `oracle` block reads (threshold / components) during planning.
- ✅ **006 DONE** — the spec-oracle overlay at `.servo/spec-oracles/<spec-id>/`
  (`checks.json`) exposes `spec_oracle_id` + AC counts for the `evaluation_model`
  block. The block is **populated when the overlay is present and null when it is
  not** (ADR-0016: a plan exists even for a baseline-oracle-only target).
- ✅ Decision: stdlib-only, Python ≥ 3.11 (spec 009 floor); reuse servo's closed
  exit-code idiom (ADR-0002): `0` = plan emitted, `2` = env-error. Never exit `1`;
  never a torn write.
- ✅ Decision (budget source of truth): the `budget` block is populated from
  `loop.py`'s **public defaults** — `DEFAULT_MAX_ITERATIONS=5`,
  `DEFAULT_COST_CEILING_USD=2.0`, `DEFAULT_CONTEXT_FILL_THRESHOLD=0.75`,
  `DEFAULT_PLATEAU_WINDOW=3` — read as the safe planned budget, never invented and
  never above the guardrail bound. Actual **clamping** of an over-ceiling human
  edit is 016-03.

## Assumptions

- **A1 — `spec_id` resolution mirrors 015.** The `<spec-id>` keying
  `plans/<spec-id>/` is the same id 015 writes its artifact under (the 006
  `plan.spec_id`, falling back to the spec's parent dir name). *To verify:* read
  the exact id `suitability.py` persisted so the plan and the verdict it
  references share one key.
- **A2 — `prompt_ref` references the spec, not a copy.** In v1 the run's prompt is
  the spec itself, so `prompt_ref` records the spec path (identity), not an
  embedded prompt string. A generated/edited prompt artifact is a later concern.

**Acceptance Criteria:**

1. **Plan artifact shape.** `execution_plan.py compile <target> --spec <path>`
   emits `<target>/.servo/plans/<spec-id>/plan.json` carrying every ADR-0016
   field: `schema_version: 1`, `spec_id`, `compiled_at` (ISO-8601),
   `suitability_ref`, `oracle` `{path, components, threshold}`, `evaluation_model`
   `{spec_oracle_id, ac_count, residual}` (or `null` with no overlay), `budget`
   `{max_iterations, cost_ceiling_usd, context_fill_threshold, plateau_window}`,
   `driver`, `prompt_ref`, and `provenance: "compiled"`. Keys are emitted in a
   stable order. *Test:* `PlanShapeTests`.

2. **References, not copies.** `suitability_ref` is a **path** to
   `.servo/suitability/<spec-id>.json` (never the inlined verdict string);
   `oracle.path` references `oracle.sh`; `evaluation_model.spec_oracle_id`
   references the overlay id. None of the three embeds the referenced artifact's
   contents — editing the referenced artifact is visible to a plan reader without
   recompiling. *Test:* `PlanReferencesNotCopiesTests`.

3. **`suitable`-only precondition (fail-closed; the 015-03 seam).** `compile`
   reads the suitability artifact and emits a plan **only** when `verdict ==
   suitable`. A missing suitability artifact, or a `needs_evidence` / `unsuitable`
   verdict, refuses with exit `2` + a structured stderr reason
   (`suitability_missing` / `suitability_not_suitable`) and writes **no** plan.
   The presence of a `plan.json` therefore implies a `suitable` reference
   (ADR-0016). *Test:* `PlanSuitabilityPreconditionTests`.

4. **Budget from the guardrail source of truth.** The `budget` block equals
   `loop.py`'s public defaults (`5` / `2.0` / `0.75` / `3`); no value exceeds the
   `loop.py` guardrail bound. The plan *records* the planned budget — it does not
   yet clamp a hand-edited over-ceiling value (016-03). *Test:*
   `PlanBudgetDefaultsTests`.

5. **Git-ignored, atomic, read-only over the target.** `.servo/plans/` is
   git-ignored (covered by the existing `.servo/` rule); the write is atomic
   (`tmp` + `os.replace`); `compile` mutates nothing else in the target tree or
   its oracle. A byte-snapshot of the rest of `.servo/` is unchanged. *Test:*
   `PlanAtomicGitignoreTests`.

6. **Closed env-error contract.** Missing/unreadable spec, missing manifest,
   missing suitability artifact, non-`suitable` verdict, or an unreadable/malformed
   input ⇒ exit `2` with a structured stderr reason (`spec_missing` /
   `manifest_missing` / `suitability_missing` / `suitability_not_suitable` /
   `manifest_malformed`), **no** partial artifact written. Never exit `1`; never a
   torn write. *Test:* `PlanExitContractTests`.

7. **Idempotent recompile.** Re-running `compile` over unchanged inputs overwrites
   the plan idempotently — byte-stable except `compiled_at`; `provenance` stays
   `compiled`. (Preserving a `human_edited` plan across recompile is 016-03, out
   of scope here.) *Test:* `PlanRecompileIdempotentTests`.

**DoD:**
- [x] All ACs pass; new `test_execution_plan.py` green (19 tests); full suite
      green (1110 passed); `ruff check .` clean (pinned 0.15.17).
- [x] Reviewed by jig compliance + craft passes (maintainer self-review; recorded
      under `reviews/slice-01-{compliance,craft,reconciliation}.md`).
- [x] Deviation log produced under this slice heading (below).
- [x] Reconciliation sweep — the `suitable`-only precondition delivers the 015-03
      gate *mechanism* but **does not** satisfy 015-03's full ACs (missing_evidence
      surfacing + boundary regression test), so 015-03 stays DEFERRED with its
      trigger marked met; **not** transitioned to DONE.
- [x] `docs/specs/README.md` hand-updated (workflow machinery not vendored).

### Close-out (post-DONE)
- [x] `plan.json` schema + `plans/<spec-id>/` location carried forward in memory
      ([[servo-016-execution-planner-started]]) for 016-02..04.

### Deviation log (after reconciliation)

Original ACs preserved above; the implementation deviated/extended as follows:

- **Two additive fail-closed reason codes.** AC6 enumerates `spec_missing` /
  `manifest_missing` / `suitability_missing` / `suitability_not_suitable` /
  `manifest_malformed`. The implementation adds **`oracle_missing`** (a plan
  referencing an absent `oracle.sh` is useless) and **`suitability_malformed`** (an
  unparseable verdict artifact). Both are sound fail-closed extensions (still exit
  2, no partial write) in the spirit of 015-01's `manifest_malformed` addition.
- **`prompt_ref` is an absolute path.** Per assumption A2 the run's prompt is the
  spec; `prompt_ref` records `str(spec_path.resolve())`. Since the spec typically
  lives outside the target, a relative ref isn't always available — but an absolute
  path in a project-owned artifact is machine-specific. Acceptable for v1 (the plan
  is locally driven); revisit when 016-02 makes Run actually consume `prompt_ref`.
- **AC5 "git-ignored" interpretation.** 016-01 writes under `.servo/plans/`, which
  **scaffold-init (001)** marks git-ignored in the target; 016-01 does not itself
  manage the target's `.gitignore`. The test asserts the location + atomicity +
  read-only, not the target's ignore file.
- **`evaluation_model` on a corrupt overlay.** A present-but-unreadable
  `checks.json` yields `null` (treated as "no overlay") rather than failing the
  compile — the overlay is optional enrichment; documented in the docstring.

### Reconciliation sweep

See [`reviews/slice-01-reconciliation.md`](reviews/slice-01-reconciliation.md) for
the full drift sweep. Headline: **015-03's trigger is now met** (016-01 is the
Compile entry point) but 015-03 is **not** thereby DONE — it stays DEFERRED,
note updated, ready to re-open as a small follow-up.
