---
status: DONE
dependencies: [006-05, adr-0023]
last_verified: 2026-07-02
frame_review: true
arch_review: true
---

## Slice 019-02 — colocate-artifacts

**Goal:** A spec-oracle's durable artifacts (`plan.md`, `checks.json`,
`oracle.sh.fragment`) live under the spec's own directory
(`docs/specs/<spec>/oracle/<slice-id>/`) instead of
`<target>/.servo/spec-oracles/<spec-id>/`, so the spec and its oracle travel
together in git/review; the shared check engine (`checks.py`) is referenced
from one shared location instead of copied byte-identically into every
overlay. Implements [ADR-0023](../../decisions/adr-0023-colocate-durable-spec-oracle-artifacts.md).

**DoR:**
- ✅ **ADR-0023 Accepted** (2026-07-02) — co-locate durable artifacts with
  the spec; keep only ephemeral state under `.servo/`; reference (don't
  copy) the shared `checks.py`, vendor-copy only for the documented
  clone-portability case.
- ✅ **019-01 DONE (or landing first)** — this slice edits the same
  `checks.py::freeze_violation` / `oracle_overlay.py::approve` call sites as
  019-01; land 019-01 first to avoid a merge conflict on the freeze logic
  (019-02 only touches path resolution, not the hash comparisons).
- ✅ Grounded by direct code read:
  - **All path construction funnels through one helper:**
    `oracle_overlay.py::_oracle_dir(target, spec_id)` (line 113-114) returns
    `target / ".servo" / "spec-oracles" / spec_id`. `oracle_plan.py`
    independently recomputes the same path twice (`plan_target` line ~537,
    CLI display line ~589) rather than importing the helper.
  - **`checks.py` is copied, not referenced:** `oracle_overlay.py::generate`
    (lines 135-140) does `shutil.copyfile(engine_src, checks_py)` into
    every overlay dir — one physical copy of the ~990-line engine per
    spec-oracle, then hashed into `approved_artifacts` for the freeze gate
    (`approve`, line ~286-293).
  - **The bash fragment hardcodes relative paths** to `.servo/spec-oracles/
    __SPEC_ID__/` (`oracle_overlay.py` fragment template, ~line 66-69) —
    these must be rewritten to the new location.
  - **Tests that assert the old layout** (would need updating, not just
    the production code): `test_oracle_overlay.py` (`test_fragment_invokes_
    engine_score_only`, `test_uninstall_keeps_plan_artifacts`),
    `test_oracle_plan.py::test_isolation_of_spec_oracle_dir`.
  - **Tests unaffected** (assert freeze/approve *logic*, not paths):
    `test_checks.py::FreezeEnforcementTests`,
    `test_oracle_overlay.py::ApproveTests` / `GateIntegrationTests`.

## Assumptions

- **A1 — exact new path shape.** ADR-0023 gives an example
  (`docs/specs/<spec>/oracle/<slice>/`) rather than a mandated shape. This
  slice assumes that exact shape (`docs/specs/<spec>/oracle/<slice-id>/`) is
  suitable and does not collide with any other convention. *To verify:*
  check for naming collisions against existing spec directory contents
  before implementing; adjust if a better-fitting convention emerges during
  implementation (documented in the deviation log if changed).
- **A2 — migration strategy is an implementation choice, not a spec
  mandate.** AC5 explicitly leaves soft-migration-vs-explicit-command to the
  implementer. This assumes neither approach is materially riskier than the
  other for the (currently small) number of already-installed overlays in
  this repo's own dogfood use. *To verify:* count existing
  `.servo/spec-oracles/*/` directories in this repo before choosing.

**Acceptance Criteria:**

1. **New artifact location.** `oracle_plan.py plan` and `oracle_overlay.py
   install`/`generate`/`approve` write/read `plan.md`, `checks.json`, and
   `oracle.sh.fragment` under `docs/specs/<spec>/oracle/<slice-id>/`
   (resolved relative to the spec path passed in — not `<target>/.servo/`),
   via one shared path helper (replacing the three independent path
   constructions found above). *Test:* `ColocatedArtifactPathTests`.
2. **`spec-id` no longer restates the spec's own path.** Because the
   artifacts now live inside the spec's own directory tree, the `spec_id`
   used for the component name / `checks.json` no longer needs to encode the
   full spec path for disambiguation (e.g. `015-01` suffices where
   `015-01-typed-cross-reference-schema` was needed before, per ADR-0023's
   context). *Test:* `SpecIdNoLongerDuplicatesPathTests`.
3. **`checks.py` is referenced, not copied, for the common case.** The
   fragment's shebang/import references one shared `checks.py` (e.g. the
   plugin-installed copy, resolved the same way `oracle_overlay.py` already
   resolves its own sibling engine) instead of `shutil.copyfile`-ing a
   private copy into each spec's oracle dir. Vendor-copy remains available
   only behind an explicit flag for the documented clone-portability case
   (a Routine/CI that clones the repo without the servo plugin installed).
   *Test:* `NoPerOverlayEngineCopyTests` (default path: no `checks.py`
   written under the spec's oracle dir); `VendorCopyOptInTests` (flag: a
   copy IS written).
4. **`.servo/` holds only ephemeral state.** After this slice, nothing new
   is written under `<target>/.servo/spec-oracles/`; `.servo/` only ever
   gains run-scoped state (`runs/`, ledger, install manifest, plan handoff)
   per ADR-0004/0010/0016 — unaffected by this slice. *Test:*
   `ServoDirHoldsNoDurableSpecOracleArtifactsTests`.
5. **Migration path for existing installs.** A target that already has
   `.servo/spec-oracles/<id>/` from before this slice either (a) continues
   to be read from the old location when the new location is absent (soft
   migration), or (b) a one-shot `oracle_overlay.py migrate` command moves
   it — implementer's choice, documented in the deviation log; either way,
   an existing installed `oracle.sh`'s SEED block is not broken by this
   change. *Test:* `ExistingOverlayMigrationTests`.
6. **`gate.py` / `oracle.sh` integration unaffected.** `gate.py` never
   constructs a spec-oracle path itself (confirmed: it only runs
   `oracle.sh` and parses its stdout) — no changes needed there; the
   existing `test_gate.py` suite passes unmodified as a regression guard.
   *Test:* full `skills/quality-gate/test_gate.py` green with zero edits.

**DoD:**
- [x] All ACs pass; full test suite green (no regressions).
- [x] Implementer test coverage exercises each AC with at least one fixture.
- [x] Compliance review pass.
- [x] Craft review pass.
- [x] Arch review pass (module-boundary change: artifact home moves out of
      `.servo/` into `docs/specs/`).
- [x] Deviation log produced under this slice heading.
- [x] Reconciliation sweep produced under this slice heading.
- [x] Reconciliation review pass.
- [x] `docs/refinement-todo.md` updated if any decisions were deferred.

### Close-out (post-DONE)
- [x] `docs/specs/README.md` regenerated by `workflow.py status-board`.
- [x] `docs/architecture.md` updated to reflect the new artifact home (arch
      review trigger).

**Anti-horizontal-phasing check:** a spec author reviewing a PR now sees the
spec's oracle plan + checks living next to the slice it evaluates in the same
diff/tree, instead of hunting through `.servo/spec-oracles/<id>/` in the
target — directly observable in `git show`/`git log` on the spec's directory.

### Deviation log (after reconciliation)

Original ACs preserved above; the implementation deviated/extended as follows:

- **Breaking CLI signature change (disclosed, not hidden).** `oracle_overlay.py
  generate`/`install`/`approve` gained a required `spec-dir` positional
  argument before `spec-id` (the CLI now reads
  `oracle_overlay.py install <target> <spec-dir> <spec-id>`, not
  `<target> <spec-id>`). This is a necessary consequence of AC1 (artifacts
  now live under the spec's own directory, which must be told to the
  helper) — reflected consistently in `SKILL.md`, `docs/architecture.md`,
  and every updated test.
- **AC2 (spec_id simplification) is behavioral, not a new validation rule.**
  `_SPEC_ID_RE` is unchanged; both a bare fragment (`015-01`) and a
  path-restating id remain legal. The simplification is that a bare
  fragment now *suffices* (no disambiguation need, since the artifacts
  live inside the spec's own directory) — proved by
  `SpecIdNoLongerDuplicatesPathTests`, not a format change.
- **AC5 migration: soft read-fallback chosen, not an explicit `migrate`
  command.** Per Assumption A2, zero `.servo/spec-oracles/*/` directories
  were found anywhere in this repo's own worktrees before deciding — with
  nothing installed yet in dogfood use, a forced migration command would be
  dead code; `oracle_dir_for_spec`'s fallback (new location wins once it
  has its own `checks.json`; else read the legacy location if present)
  costs nothing today and protects any future/external install for free.
- **Security fix during reconciliation (both compliance and craft review
  passes independently found this): `oracle_dir_for_spec` did not validate
  `spec_id`.** `oracle_plan.py`'s `--spec-id` CLI flag reached the shared
  path helper with no traversal guard — `--spec-id ../../../tmp/evil` could
  have escaped the spec's own oracle directory. Fixed by moving
  `_validate_spec_id` into `oracle_dir_for_spec` itself (the one
  chokepoint every caller funnels through, per its own docstring's stated
  rationale for centralization), plus adding `ValueError` to
  `oracle_plan.py::_plan_main`'s exception handler. Regression tests:
  `SpecIdValidationIsCentralizedTests` (unit-level, both modules) and
  `test_traversal_spec_id_refused_not_written_outside_spec_dir`
  (CLI/filesystem-level, full-tree snapshot diff proving zero partial
  write).
- **Two out-of-scope gaps found and deferred, not silently absorbed:**
  (1) `skills/execution-planner/execution_plan.py::_load_evaluation_model`
  (spec 016, DONE) independently hardcodes the legacy
  `.servo/spec-oracles/<id>/checks.json` path — a third call site this
  slice's original grounding research didn't name. Not fixed inline:
  `execution_plan.py`'s own file header documents a deliberate
  "dependency-free skill" invariant (duplicates `loop.py`'s constants
  rather than importing them), so importing `oracle_dir_for_spec`
  cross-skill would be a new kind of coupling — a design call for spec 016,
  not this slice. Logged to `docs/refinement-todo.md`.
  (2) The freeze/approval hash (`approved_artifacts`) only covers a
  *vendored* `checks.py`; the referenced (default) shared engine is never
  hashed, so a servo plugin upgrade changes an already-approved oracle's
  engine invisibly to `--enforce-freeze`. A disclosed trade-off of
  ADR-0023's reference-not-copy default (arch-review finding); logged to
  `docs/refinement-todo.md` rather than redesigning the freeze mechanism
  inline.
- **`skills/heartbeat/heartbeat.py` comment updated, no behavior change.**
  Its `.servo/spec-oracles/` sidecar-provisioning logic (spec 011, DONE)
  is now legacy-install-only (a colocated overlay is git-tracked and
  travels with a fresh worktree checkout automatically) — clarified with a
  comment, since a future reader could otherwise wonder why the
  provisioning code still exists post-019-02.

### Reconciliation sweep

| Artifact | Disposition | Rationale |
|----------|-------------|-----------|
| `README.md` | `no-op` | Project front door doesn't describe spec-oracle internals. |
| `docs/specs/README.md` | `updated` | Regenerated by `workflow.py status-board` after this slice transitions. |
| `docs/product-vision.md` | `no-op` | Checked — no scope/behavior drift; implements an already-Accepted ADR. |
| `docs/architecture.md` | `updated` | The spec-oracle artifact-location description was rewritten for the new layout, reference-vs-vendor default, and migration fallback (arch-review trigger). |
| Primer surfaces | `no-op` | Checked — none reference spec-oracle's artifact-location convention directly. |
| `docs/inbox.md` | `no-op` | This project has no `docs/inbox.md` (not adopted). |
| `docs/refinement-todo.md` | `updated` | Two entries added: execution-planner's stale path (spec 016 follow-up) and the checks.py-reference version-skew gap (freeze-hardening follow-up). |
| `docs/memory/**` | `no-op` | No new domain terms beyond what this slice's own record + ADR-0023 already capture. |
| `docs/decisions/README.md` / ADR index | `no-op` | ADR-0023 already indexed as Accepted; this slice only implements it. |
| `agents/runner.md` | `updated` | The "don't edit approved spec-oracle artifacts" guardrail named only the legacy `.servo/spec-oracles/` path; updated to name both the colocated and legacy locations so the runner's prompt stays accurate regardless of which layout a target uses. |
| `skills/heartbeat/heartbeat.py` | `updated` | Comment-only: clarified that sidecar provisioning is legacy-install-only post-ADR-0023 (no behavior change; full heartbeat suite passes unmodified). |
