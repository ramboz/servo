---
status: DONE
tier: standard
severity: medium
claimed_by: claude/actionable-specs-adrs-b28ed5
regression_test: skills/execution-planner/test_execution_plan.py::PlanShapeTests::test_evaluation_model_from_colocated_overlay
main_repro_checked_at: 2026-07-08
main_repro_ref: origin/main@027e8da
main_repro_result: reproduces
red_confirmed_at: 2026-07-08
green_confirmed_at: 2026-07-08
fix_class: local_patch
security_surface: false
escalated_to:
---

# Bug 005: evaluation-model-stale-overlay-path

## Symptom

`execution_plan.py compile` emits a `plan.json` whose `evaluation_model` block is
`null` even when a spec-oracle overlay **is** installed — whenever that overlay
lives at the post-[ADR-0023](../decisions/adr-0023-colocate-durable-spec-oracle-artifacts.md)
colocated location (`<spec-dir>/oracle/<spec-id>/checks.json`), which slice
019-02 made the default. The plan silently loses the evaluation-model enrichment;
it looks identical to a baseline-oracle-only target. Not a hard failure — the
compile still exits 0 and writes a plan — which is precisely why it is easy to
miss.

## Repro

1. Scaffold a target and plan a spec-oracle for a spec via the **new** (default,
   post-019-02) layout, so its `checks.json` lives at
   `<spec-dir>/oracle/<spec-id>/checks.json` (not the legacy
   `<target>/.servo/spec-oracles/<spec-id>/checks.json`).
2. Ensure a `suitable` suitability verdict exists.
3. `python3 execution_plan.py compile <target> --spec <spec-dir>/spec.md`.
4. Read the emitted plan: `evaluation_model` is `null`, despite the overlay
   being present and well-formed.

(As a unit-level repro: `_load_evaluation_model(target, spec_id)` returns `None`
for an overlay written only to `<spec-dir>/oracle/<spec-id>/checks.json`.)

## Evidence

- **The buggy read** — `skills/execution-planner/execution_plan.py:236`
  hardcodes the legacy location and checks nothing else:
  ```python
  checks_json = target / ".servo" / "spec-oracles" / spec_id / "checks.json"
  if not checks_json.is_file():
      return None
  ```
- **The canonical resolver it should mirror** —
  `skills/spec-oracle/oracle_overlay.py:155-181` (`oracle_dir_for_spec`):
  resolves to `<spec_dir>/oracle/<spec_id>/` and **only** falls back to the
  legacy `.servo/spec-oracles/<spec_id>/` when the new location has no
  `checks.json` yet (soft migration, ADR-0023 AC5). "The new location always
  wins once it has its own plan."
- **Why it slipped through** — `_load_evaluation_model` was written in 016-01
  (pre-ADR-0023) and was **not** named in 019-02's grounding research (only
  `oracle_overlay.py` and `oracle_plan.py` were flagged as call sites), so the
  019-02 sweep never touched it. Documented in `docs/refinement-todo.md`
  § "execution-planner's evaluation_model still reads the pre-ADR-0023
  spec-oracle path".
- **Why the existing suite stays green** — `test_execution_plan.py`'s
  `_write_overlay` fixture (line 121-132) fabricates the overlay at the **old**
  `.servo/spec-oracles/` path, so it exercises only the legacy branch and never
  the new-layout case.

## Hypotheses

- **H1 (leading, confirmed) — stale hardcoded path.** `_load_evaluation_model`
  reads only the legacy `.servo/spec-oracles/<id>/checks.json` and never the new
  colocated `<spec-dir>/oracle/<id>/checks.json`, so a post-019-02 overlay is
  invisible. *Confirm:* the literal path at `execution_plan.py:236` + the
  divergent `oracle_dir_for_spec` contract. *Falsify:* if it also probed the new
  location, an overlay written there would populate `evaluation_model`. → Held:
  the code reads exactly one location, the legacy one.
- **H2 (alternative, rejected) — the null is correct (no/failed overlay).** The
  overlay is genuinely absent, malformed, or the caller passes a wrong
  `spec_id`, so `null` is the right answer. *Falsify:* write a well-formed
  overlay at the **new** location with a correct `spec_id` and observe
  `evaluation_model` still `null` — isolating *location*, not presence/validity,
  as the cause. → Rejected: the function's own legacy-path read proves it parses
  a well-formed overlay fine; only the location it looks in is wrong.

## Root cause

A **process** problem, not just a bad output: `_load_evaluation_model` encodes
its own copy of "where a spec-oracle's `checks.json` lives", and that copy was
never updated when ADR-0023 / slice 019-02 moved the canonical location. Because
the function does not receive the spec's own directory (`spec_dir`) at all — only
`target` and `spec_id` — it *cannot* look in the new location; it is
structurally blind to it. The fix must (a) thread `spec_dir` in from the caller
and (b) resolve both locations (new preferred, legacy fallback), duplicating —
not importing — `oracle_dir_for_spec`'s logic, per `execution_plan.py`'s
documented dependency-free-skill invariant.

## Fix class

`local_patch` — a targeted correction to `_load_evaluation_model` (+ its one
caller) that resolves the root cause (wrong location) by honoring ADR-0023's
dual-path contract locally. Deliberately **not** `structural_fix`: the canonical
resolver is **duplicated**, not imported, to preserve the skill-directory
boundary / dependency-free invariant (the same invariant that makes
`execution_plan.py` mirror `loop.py`'s budget constants rather than import
them). The residual drift risk this leaves — a future change to
`oracle_dir_for_spec`'s semantics would again not propagate here — is the known,
accepted trade-off of that invariant, not an oversight.

## Fix

`skills/execution-planner/execution_plan.py`:

1. **`_load_evaluation_model(target, spec_id)` → `_load_evaluation_model(target,
   spec_dir, spec_id)`.** The function now receives the spec's own directory, so
   it can look at the colocated location at all (it previously could not — it was
   structurally blind).
2. **Dual-path resolution (new preferred, legacy fallback):**
   ```python
   new_checks = spec_dir / "oracle" / spec_id / "checks.json"
   legacy_checks = target / ".servo" / "spec-oracles" / spec_id / "checks.json"
   if new_checks.is_file():
       checks_json = new_checks
   elif legacy_checks.is_file():
       checks_json = legacy_checks
   else:
       return None
   ```
   Mirrors `oracle_overlay.py::oracle_dir_for_spec` ("the new location always
   wins once it has its own plan"); the legacy branch keeps pre-019-02 installs
   working. **Duplicated, not imported** — the dependency-free-skill invariant
   (see the file header), the same reason the budget constants mirror `loop.py`.
3. **Caller** `compile_plan` now passes `spec_path.parent` as `spec_dir`
   (`spec_id` is that directory's name, per `_spec_id_from_path`).

The overlay-parse logic (`spec_oracle_id` / `ac_count` / `residual`) and the
present-but-unreadable → optional-enrichment fail-open are unchanged. Scope: one
function + its single caller; no schema/CLI/behavioral change beyond finding the
overlay where it now lives.

## Already tried

_(none yet — diagnosis was inherited from the 019-02 refinement-todo write-up and
independently confirmed against current code.)_

## Regression test

`skills/execution-planner/test_execution_plan.py::PlanShapeTests::test_evaluation_model_from_colocated_overlay`
— fabricates a well-formed overlay at the **new** colocated location
(`<spec-dir>/oracle/<spec-id>/checks.json`) and asserts the emitted plan's
`evaluation_model` is populated (not `null`). Fails on the current code (which
reads only the legacy path → `null`); passes after the fix. A companion
`test_evaluation_model_colocated_wins_over_legacy` locks the precedence (new
location wins when both are present), mirroring `oracle_dir_for_spec`.

## Proof

Red→green witnessed by `bug.py`'s test gate (`tdd.py` shelled under the
`/tmp/servo-venv` python): `red_confirmed_at` stamped at `→ FIXING`,
`green_confirmed_at` at `→ REVIEWED`.

- `test_evaluation_model_from_colocated_overlay` — RED on the old code
  (`evaluation_model == null` for a new-layout overlay); GREEN after
  (`{spec_oracle_id, ac_count: 5, residual: 2}`).
- `test_evaluation_model_colocated_wins_over_legacy` — RED on the old code (read
  the legacy overlay, `ac_count == 1`); GREEN after (new location wins,
  `ac_count == 9`).
- Full `skills/execution-planner/` suite: **49 passed**; the legacy-path
  `test_all_adr0016_fields_present` still green → the fallback preserves
  pre-019-02 installs. `ruff check` clean.

**Reviews:** bug-review PASS + craft PASS (no blockers; 3 strengths). Both
reviewers independently flagged one intentional divergence: the local dual-path
resolver mirrors `oracle_dir_for_spec`'s path resolution but **omits its
`_validate_spec_id` path-traversal guard**. Left as-is by design — at this call
site `spec_id` is `spec_path.parent.name` (a single path component, no
separators/`..`) and the path is only ever read via `is_file()`, never written
or shell-interpolated, so traversal is unreachable; importing the guard would
break the dependency-free-skill invariant and re-duplicating more of the
resolver is out of this bug's `local_patch` scope. Recorded here as a known,
bounded divergence (alongside the drift risk in `## Fix class`).

## Learning

_(recorded in `docs/memory/learnings.md` at DONE.)_

## Main recheck

- 2026-07-08 - `origin/main@027e8da` -> reproduces: git show origin/main:skills/execution-planner/execution_plan.py → _load_evaluation_model (sig (target, spec_id), line 235) hardcodes target/.servo/spec-oracles/<id>/checks.json; no read of the new <spec-dir>/oracle/<id>/checks.json, so a post-019-02 colocated overlay yields evaluation_model=null on fresh main.
