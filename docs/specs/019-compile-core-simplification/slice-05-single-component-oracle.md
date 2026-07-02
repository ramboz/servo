---
status: RECONCILED
dependencies: [001-05, 002-05]
last_verified: 2026-07-02
frame_review: true
---

## Slice 019-05 — single-component-oracle

**Goal:** A scaffolded `oracle.sh` with exactly one registered component
scores it directly (capture `score_<name>`, compare to `$THRESHOLD`) with no
weighted-sum/`awk`-average arithmetic; the weighted-composite path is
preserved byte-for-byte for the ≥2-component case, so multi-component
oracles keep working unchanged when a second component is later spliced in
by `oracle_overlay.py::install`.

**DoR:**
- ✅ Grounded by direct read of `templates/oracle.sh.template` (the single
  generation source for every scaffolded `oracle.sh` — via
  `scaffold.py::_render_oracle`) and `skills/spec-oracle/oracle_overlay.py::
  install`: today, **every** install — including the single-component case
  the dogfood's real oracles all were ("every real oracle in the dogfood
  was a single component at weight 1.0, threshold 1.0") — runs the same
  `awk`-based `weighted_sum += score*weight; total_weight += weight;
  composite = weighted_sum/total_weight` loop over `COMPONENTS=("name:
  weight")`, even when there is exactly one entry (where the arithmetic is
  a no-op: `score*weight/weight == score`).
- ✅ **`gate.py` is agnostic to how `oracle.sh` computes its composite** —
  it only subprocess-invokes `oracle.sh` and regex-parses its
  `oracle: composite=X threshold=Y` stdout line
  (`_ORACLE_SUMMARY_RE`, `skills/quality-gate/gate.py`). Any internal
  simplification of the scoring path is invisible to `gate.py`, so this
  slice needs zero changes there — confirmed by direct read.
- ✅ **`oracle_overlay.py::install`'s splicing logic must keep working
  unchanged.** It finds `COMPONENTS=(\s*\n` and the `# SEED:start/end`
  markers via regex to add a second component to an *existing* `oracle.sh`
  (lines 145-194). The design constraint this DoR imposes: **do not**
  introduce a second oracle.sh template shape (a "simple-mode" file
  structurally different from the "weighted" one) — that would break
  `install`'s ability to upgrade a single-component oracle into a
  multi-component one. Instead, the *aggregation logic at the bottom of
  the one template* branches at runtime on `${#COMPONENTS[@]}`; the
  `COMPONENTS` array + `# SEED:` block shape stay identical in both cases.
- ✅ **001/002 DONE** — `scaffold.py::_render_oracle` (single template
  source) and `gate.py` (composite-line consumer) are stable, DONE
  surfaces this slice edits/depends on respectively.

## Assumptions

- **A1 — one template with a runtime branch, not two template shapes.**
  This slice assumes `templates/oracle.sh.template` should stay a single
  file whose aggregation logic branches at runtime on
  `${#COMPONENTS[@]}`, rather than generating a structurally different
  "simple" oracle.sh for the single-component case. The load-bearing reason:
  `oracle_overlay.py::install` upgrades an existing `oracle.sh` to a second
  component via regex over the `COMPONENTS=(` array and `# SEED:` markers
  (AC4) — a structurally different simple-mode file would break that
  upgrade path or require a separate migration step this spec does not
  otherwise call for. *To verify:* prototype the runtime-branch approach
  against the existing `oracle_overlay.py::install` regexes before writing
  the full implementation; fall back to documenting an upgrade-migration
  step in the deviation log if the branch approach turns out incompatible.

**Acceptance Criteria:**

1. **Single-component path skips weighted arithmetic.** When
   `${#COMPONENTS[@]} -eq 1`, `oracle.sh` captures that one
   `score_<name>` value and compares it directly to `$THRESHOLD` (no
   `weighted_sum`/`total_weight`/`awk` averaging invoked for the comparison
   — a direct numeric compare is fine, still via `awk` or shell arithmetic
   for the float compare itself, but with no weight multiplication/division
   step). *Test:* `SingleComponentNoWeightedAverageTests` — a fixture
   `oracle.sh` with one component, asserting via a code-shape check (grep
   the rendered script for the absence of the multi-term weighted-sum
   expression on the taken branch) or a runtime probe that varies the
   component's declared weight and shows it has zero effect on the outcome
   (proving the weight is inert on this path, i.e. not silently still
   being used).
2. **Same stdout/exit-code contract.** The single-component path still
   emits `oracle: composite=<score> threshold=<threshold>` on stdout
   (same regex `gate.py` parses) and the same closed 0 (pass) / 1
   (below-threshold) / 2 (missing component / rc≠0,2) exit contract as
   today. *Test:* `SingleComponentExitContractTests` (pass / fail / missing
   / bad-rc fixtures, mirroring the existing multi-component
   `test_gate.py` coverage but against a single-component oracle.sh).
3. **Multi-component path is unchanged.** A `≥2`-component `oracle.sh`
   (freshly scaffolded with 2 components, or a single-component one
   upgraded via `oracle_overlay.py::install`) still runs the existing
   weighted-average loop, byte-identical in behavior to today. *Test:*
   full existing `test_scaffold.py` multi-component fixtures +
   `test_oracle_overlay.py::GateIntegrationTests` pass unmodified.
4. **Upgrade path preserved.** `oracle_overlay.py::install` splicing a
   second component into a freshly-scaffolded single-component `oracle.sh`
   still succeeds (finds the `COMPONENTS=(` anchor and `# SEED:` markers
   unchanged) and the result correctly falls onto the multi-component
   (weighted) runtime branch. *Test:*
   `SingleToMultiComponentUpgradeTests` — scaffold single, `install` a
   second component, assert both scores are correctly weighted-averaged.
5. **No components / zero threshold edge cases unaffected.** The existing
   "no components" `env_error` (exit 2) and `THRESHOLD=0` smoke-test
   override paths are untouched by the branch. *Test:* existing
   `test_scaffold.py` / `test_gate.py` fixtures for these cases pass
   unmodified.

**DoD:**
- [x] All ACs pass; full test suite green (no regressions).
- [x] Implementer test coverage exercises each AC with at least one
      fixture.
- [x] Compliance review pass.
- [x] Craft review pass.
- [x] Deviation log produced under this slice heading.
- [x] Reconciliation sweep produced under this slice heading.
- [x] Reconciliation review pass.
- [x] `docs/refinement-todo.md` updated if any decisions were deferred.

### Close-out (post-DONE)
- [x] `docs/specs/README.md` regenerated by `workflow.py status-board`.
- [ ] Primer hygiene: 019-02 and 019-03 are still open at the time this
      slice lands, so spec 019 is NOT yet closing — defer the primer
      compression to whichever of 019-02/019-03 lands last.

**Anti-horizontal-phasing check:** the ~90% common case (one oracle
component) gets a scaffolded `oracle.sh` a human can read top-to-bottom
without mentally executing an `awk` weighted-average — directly observable
by inspecting any freshly-scaffolded single-component target's `oracle.sh`.

### Deviation log (after reconciliation)

Original ACs preserved above; the implementation matched the planned shape with
no functional deviations. Notes from the two review passes:

- **Assumption A1 held with zero fallback needed.** The single-template-with-
  runtime-branch design (one `if [ "${#COMPONENTS[@]}" -eq 1 ]` around the
  scoring section) worked against `oracle_overlay.py::install`'s existing
  `COMPONENTS=(` / `# SEED:` regexes with no changes there — confirmed by
  `SingleToMultiComponentUpgradeTests` driving the real `install` CLI.
  A1's stated fallback (a documented migration step) was not needed.
  `else` branch is byte-identical to the pre-slice weighted-average loop,
  just re-indented.
- **One extra test class beyond the ACs' named ones.**
  `MultiComponentBranchUnchangedTests` was added for direct runtime coverage
  (not just rendering-shape coverage) that the `else` branch still does live
  weighted averaging against the new template file — additive, not a
  replacement for any required class.
- **Two doc nits fixed during reconciliation** (both reviewers independently
  flagged the same drift): the top-of-file header comment in
  `templates/oracle.sh.template` and `README.md`'s "The scaffolded oracle.sh"
  section both described the composite as unconditionally a weighted
  average; both corrected to name the single-component direct-compare path.
- **Test-coverage gap fixed during reconciliation:** the existing
  `ShellcheckTests` fixture seeded 5 detectors, so it only ever shellchecked
  the ≥2-component branch. Added
  `test_rendered_single_component_oracle_shellcheck_clean` (one detector) to
  close the gap the craft reviewer flagged.
- **Environment note (not a spec deviation):** running this repo's tests
  requires `PYTHONUTF8=1` (or a non-C locale) — without it, Python 3.13
  under a `C` locale raises a spurious `SyntaxError` importing
  `skills/spec-oracle/checks.py` (a pre-existing em-dash in a docstring).
  Not fixed here (outside this slice's scope); worth a memory/inbox note for
  future implementer runs.

### Reconciliation sweep

| Artifact | Disposition | Rationale |
|----------|-------------|-----------|
| `README.md` | `updated` | The "scaffolded oracle.sh" section's weighted-average description was stale; corrected to name both the single- and multi-component paths (craft-review finding). |
| `docs/specs/README.md` | `updated` | Regenerated by `workflow.py status-board` after this slice transitions. |
| `docs/product-vision.md` | `no-op` | Checked — no scope/behavior drift; pure internal simplification. |
| `docs/architecture.md` | `updated` | The "Composite weighting heuristic" open-question note (line 444) described the pre-slice weighted-average-always behavior; the reconciliation reviewer caught this (it's a closed historical note, but still describes current scoring internals) — added a one-line "Refined (slice 019-05)" addendum. |
| Primer surfaces | `deferred` | Spec 019 is not closing with this slice (019-02/019-03 still open) — primer compression deferred to whichever of those lands last. |
| `docs/inbox.md` | `no-op` | This project has no `docs/inbox.md` (not adopted) — the environment note went to `docs/memory/learnings.md` instead (see below). |
| `docs/refinement-todo.md` | `no-op` | Checked — nothing deferred; both review nits were fixed directly, not queued. |
| `docs/memory/learnings.md` | `updated` | Added a `PYTHONUTF8=1` test-runner note surfaced during implementation, so future sessions don't lose time rediscovering it. |
| `docs/memory/**` | `no-op` | _TBD._ |
| `docs/decisions/README.md` / ADR index | `no-op` | _TBD._ |
