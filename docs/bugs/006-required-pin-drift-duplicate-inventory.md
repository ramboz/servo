---
status: REVIEWED
tier: standard
severity: medium
claimed_by: real-source-static-app-gate
regression_test: skills/spec-oracle/test_required_gate.py::InstalledRequiredGateTests::test_ac3_pinned_input_drift_retains_exact_inventory_and_original_cause
main_repro_checked_at: 2026-10-19
main_repro_ref: servo-card-slice-closeout@2cd33a4a08dea72a961662e24b5f11da5e7bdeb0
main_repro_result: reproduces
red_confirmed_at: 2026-10-19
green_confirmed_at: 2026-10-19
fix_class: structural_fix
security_surface: false
escalated_to:
closure_schema: 1
---

# Bug 006: required-pin-drift-duplicate-inventory

## Symptom

An installed required gate correctly refuses changed approved input, but its
overall carrier duplicates every required ID and replaces the leading cause
with a secondary `NoneType` error. During the separately authorized finite
[036-03 APP pilot](../specs/036-deterministic-design-evidence/static-app-pilot-evidence.md),
native run `24a10dd7-c782-41db-9727-3213e4e381ca` published 41 UNKNOWN items:
two copies of each approved twenty IDs plus `<gate>`. This is a defect in the
generic runtime introduced with the unmerged 035 implementation, not a new
design interpretation or a source-producer defect. Closed 035/036-01 records
are linked, not amended.

## Repro

Approve/install a required command component with two IDs and an explicitly
pinned input. Change only that input, leaving all checks and approvals
unchanged, and run the real native gate at `THRESHOLD=0`.
Before the fix, the focused regression observes
`['<gate>', 'assertion', 'assertion', 'second', 'second']`, not the approved
`['assertion', 'second']`. No assertion command should run after pin drift.
Exact input restoration must restore an actual native PASS.

## Evidence

Retained artifact root:
`/Users/ramboz/.copilot/session-state/43b73062-3958-42e3-879f-4f588494ff00/files`.
`static-native-proof/dashboard/mutated-copied-source-input/` contains actual
argv/stdout/stderr, engine carriers, Generic acceptance/readback and exact
restoration. `unexpected-duplicate-required-inventory.json` SHA256 is
`ca47f603f92f240892bd14f475eb99ee5daa25d7ddb926662441b430c24b236b`.
The original gate SHA256 is
`18fb70fe4fec1259f5f62d47ede631b5ef3173014d4131eab9a1b9ef93fb4cf9`.
The copied and read-only original SOURCE input both retain SHA256
`385f73c2d2736c316d170b1b74eeb23ad891d1556745c3e3e0df7ecaded52eef`
after exact restoration; no APP observation was acquired for this control.

`static-generic-pin-drift-red-unittest.txt` witnesses the first isolated native
regression fail. `static-generic-pin-drift-green-unittest.txt` records the
exploratory narrow fix passing, and
`static-generic-pin-drift-targeted-pytest.txt` records 255 related tests plus
50 subtests passing. These precede formal bug lifecycle adoption and are
not retroactively presented as helper-stamped red/green gates.

## Hypotheses

<!-- Anti-anchoring: >=2 candidates, mark the leading one. Any Markdown
     list works (-, *, +, or 1.); the gate counts top-level items only
     (indented sub-bullets are notes, not hypotheses). -->
- [ ] H1: The APP observer or immutable-output consumer duplicated constraints.
  Falsified for this control: no observed output exists; duplicate required
  rows arise before any APP command execution, and a generic two-ID fixture
  reproduces without APP/Vellum code.
- [x] H2 (leading): The oracle's pin preflight and outer gate reconstruction
  produce different refusal causes for the same unavailable component.
  Confirmed by source tracing and native red: oracle retains the original
  artifact-modified cause, while outer validation dereferences a null result;
  whole-row merging then treats their different reasons as additional items.

## Root cause

In `skills/quality-gate/required_runtime.py`, `oracle()` checks the entry's
approved evaluator/runtime/artifact pins before executing. Pin drift therefore
publishes a component with `result:null` and one UNKNOWN per approved ID.
`run_gate()` previously attempted `validate_component()` on that null
reference without independently establishing the same pin failure first.
The resulting secondary `NoneType` items differ from the oracle's original
items, so the later whole-dict unknown merge appends them. Aggregate comparison
then adds an additional gate refusal.

The repair reuses the existing `check_pins` authority before outer component
validation. It does not deduplicate after the fact, discard refusal causes,
accept a missing result merely because pins pass, or change APP/SOURCE grading.

## Repository closure inventory

<!-- Spec 091 / ADR-0037: pre-fix repository closure. Standard & gnarly
     bugs gate ROOT_CAUSED -> FIXING on substantive answers below. This
     is an effort-and-protocol standard, NOT a completeness proof: show
     the search you actually ran. A bare "none found" fails; record
     residual uncertainty as an assumption WITH the protocol behind it,
     applying the same enumeration standard as `## Root cause` (ADR-0052).
     Prefer a configured semantic index; the portable floor is targeted
     search + `git log`/`git blame`. -->

**Equivalent / convergent logic searched:**

Targeted Python searches for `check_pins(`, `validate_component(` and
`run_gate(` across `skills/` and `scripts/` found the existing runtime
validation helper, oracle preflight, Generic preserved-reader checks, gate
dispatch and their tests. This is an inventory of direct symbol references
in that bounded source tree, not a universal claim about external adopters
or dynamically imported plugin code.

**Relevant history inspected:**

`git log --all -S 'i not in items'` and blame of reconstruction/merge lines
identify `936aa2e4` (required-evidence implementation) as the introduction of
this process; it is inherited by required stack base
`2cd33a4a08dea72a961662e24b5f11da5e7bdeb0`.
Freshly fetched `origin/main` is
`dc56bd3397c21224866cba639adb7c5a334bcec0`; it does not contain
`skills/quality-gate/required_runtime.py`. Fresh-main qualification must
therefore explicitly distinguish the absent-on-trunk feature from the
unmerged integration base, not falsely mark the defect resolved on main.

**Affected call sites:**

`run_gate()` reconstructs native required outcomes; `gate.py` dispatches to it.
`oracle()` and `validate_binding()` already use the same pin helper.
`gate_consumer._validate()` independently checks pins for published component
references; `run_gate()` recovery and `validate_component()` continue refusing
unavailable/malformed evidence. The official Claude/Codex/Copilot projections
carry the runtime through `scripts/build_host_packages.py`.

**Reuse decision:**

Reuse `check_pins`, preserving its established pin order and original cause.
Do not create another integrity implementation, grading controller or
deduplication fallback. Keep Generic readback and source normalizers unchanged.

## Fix class

`structural_fix`: align the process which reconstructs a preflight refusal
with the existing independent pin authority, rather than editing the bad
published rows or silently removing duplicate diagnostics.

## Fix

Add the existing evaluator/runtime/artifact pin check immediately before
outer `validate_component()`. Extend native regression coverage to protected
artifact, vendored evaluator and vendored runtime drift with a missing result,
exactly-once approved IDs, original cause, no assertion execution and exact
restoration PASS. Separately retain current-pin missing/malformed-result
refusal coverage.

## Call-site closure

<!-- Spec 091 / ADR-0037: before REVIEWED, account for every site named
     in the inventory above as changed, tested, or intentionally left
     alone. Accounting, not mandatory widening. -->

**Disposition per affected site:**

`run_gate()` reconstruction: changed and exercised by actual temporary-target
native gates for all three pin categories, unique two-ID refusals and exact
restoration PASS. `oracle()` / `validate_binding()` / `check_pins()`:
intentionally unchanged, reusing the same established cause and pin order.
`validate_component()` / outer recovery / `gate.py` dispatch / Generic
`_validate()`: unchanged; 255 native/consumer/output tests plus 50 subtests
passed, including the existing exact-run known-failure recovery control.
The added current-pin missing-reference, missing-file and malformed-record
controls all refuse without treating successful pin validation as evidence.
Claude/Codex/Copilot projections are regenerated with the official builder;
the complete pre-expansion suite passed 2569 tests, 14 skips and 310 subtests.
No experimental installed definition is updated in place.

## Already tried

The installed APP experiment is hard-held after the unexpected carrier.
All original installs, exact checkpoint/release, successful pilot cases,
NONPROOF replay setup and source-restoration records remain immutable.
No vendored experiment helper or old approval is edited in place.

The default and selected observer Python lacked pytest. The first helper
attempt returned environment exit 2, not a red test. Standard-library unittest
witnessed the real red/green; related pytest suites use a separate existing
uv test environment, never installation into the frozen observer runtime.

## Regression test

The named frontmatter selector runs the actual installed native gate, not a
mocked aggregate. Its fixture vendors evaluator/runtime inside its temporary
target before mutation, avoiding any shared-runtime writes.

## Proof

Fresh-main inspection and actual detached stack-base reproduction are retained
in `files/bug006-qualified-reproduction/qualification.json` and its
`native-base-red/{command.json,stdout,stderr}`. The record explicitly qualifies
only stack target `2cd33a4a...` as reproducing; fresh main `dc56bd33...` lacks
the feature. Base runtime hash is exactly affected `f0f9d90c...`, not fixed
`526039f3...`; the copied regression test's hash is recorded alongside both.
All three pin categories fail with duplicate rows on that unchanged base.
`result.json` SHA256 is
`241d8be87b4ffe9e92683b6e0a3904663e0fa3fce719b099d467390203d6fdfb`.

After diagnosis, repository-closure recording and the qualified main check,
the exploratory two-line fix was removed and the normal `FIXING` transition
actually ran the expanded regression red and stamped `red_confirmed_at`.
The same two-line change was restored without a bypass. Expanded native
coverage passes two tests plus six subtests (`files/bug006-expanded-green.txt`):
protected input/evaluator/runtime drift with exact restoration, and genuine
missing-reference/file/malformed-record refusals under current pins.
Fresh independent [bug-review](reviews/bug-006-bug-review.md) and
[craft](reviews/bug-006-craft.md) passes both returned PASS, with their
read-only/provenance limits retained. The normal `REVIEWED` transition ran
the same named regression green, stamped `green_confirmed_at` and validated
both actual review artifacts without a bypass.
Existing APP execution authority is suspended; this repair does not itself
authorize another APP experiment.

## Learning

See `docs/memory/learnings.md`, "Bug006 pin refusals need the original
independent authority". A correct refusal exit is insufficient: check the
complete required inventory and original per-ID causes. When preflight
prevents component publication, establish the same pin authority before
interpreting a missing reference; never repair duplicate output after the
fact or infer valid evidence from successful pin checks. Preserve a truthful
stack-target qualification when the owning feature is absent from fresh main.

## Main recheck

- 2026-10-19 - `servo-card-slice-closeout@2cd33a4a08dea72a961662e24b5f11da5e7bdeb0` -> reproduces: Qualified STACK target only: exact archived2cd runtimef0f9 matches affected epoch; expanded native regression RED for protectedinput/evaluator/runtime with duplicateIDs. Retained files/bug006-qualified-reproduction/{qualification.json,native-base-red/{command.json,stdout,stderr},result.json}; resultSHA241d8be87b4ffe9e92683b6e0a3904663e0fa3fce719b099d467390203d6fdfb. Fresh fetched origin/main@dc56bd3397c21224866cba639adb7c5a334bcec0 has no required_runtime.py: featureabsent/notrunnable, NOT plain-main reproduces and NOT resolved-on-main. Parent explicitly approved truthful stack-target qualification, no bypass.
