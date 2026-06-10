---
status: IN_PROGRESS
dependencies: [001, 002, 003]
last_verified: 2026-06-09
---

# Spec 006 — spec-oracle

> Compile a spec or slice into a **spec-specific evidence oracle**:
> acceptance-criteria mapping, deterministic checks, negative controls,
> an installable oracle component, and an evidence ledger that lets
> `/servo:agent-loop` optimize against the spec without pretending one
> generic LLM judge can understand every product promise.

## Why this spec

Specs 001–003 prove the closed-loop substrate:

- 001 scaffolds a project-owned `oracle.sh`.
- 002 makes that oracle uniformly callable through `gate.py`.
- 003 runs a guarded unattended loop against the oracle.

That is enough for projects whose existing tests already encode the
desired outcome. It is not enough for spec-driven projects where each
feature has its own acceptance criteria. In those projects, the hard
part is not "run the loop"; it is "make the loop's target trustworthy."

The pattern is emerging from jig dogfood candidates:

- Spec 039 needed checks for a removed dead file, a `.gitignore` guard,
  and no live runtime references.
- Spec 046 needs temp-scaffold command/link checks and version
  provenance checks.
- Spec 047 needs plugin/scaffold install-contract validators.

Those checks are spec-specific, but their shape is reusable. Servo
should not ship one generic judge that hand-waves over every spec. It
should ship a **spec-to-evidence compiler** that turns acceptance
criteria into a reviewable, executable overlay on top of the repo's
baseline oracle.

This spec closes the gap between "the repo still passes tests" and "the
current spec's promises are proven enough for unattended iteration."

## Goals

1. **Plan from acceptance criteria.** Given a target repo and a
   spec/slice path, extract acceptance criteria and classify each one
   into a check family: command/test, file/content invariant, generated
   artifact smoke check, schema/manifest contract, doc/link check,
   package/archive inventory, or residual judgment.
2. **Produce a traceable evidence contract.** Write a reviewable plan
   that maps `AC -> check -> evidence -> failure message -> negative
   control`. Uncovered judgment stays visible instead of being hidden
   behind a passing baseline suite.
3. **Compile deterministic checks.** Generate stdlib-only check code
   or shell fragments for the common families above, plus a small JSON
   contract the runtime can consume.
4. **Prevent self-grading with extra steps.** The loop must not silently
   invent its own judge and then satisfy it. Generated oracles are
   frozen before unattended implementation, carry hashes, and can be
   changed only through an explicit re-plan/review step.
5. **Install as a project-owned oracle overlay.** The generated
   spec-oracle becomes a component in `oracle.sh` or a called helper
   that `oracle.sh` scores. It composes with the repo baseline instead
   of replacing it.
6. **Record evidence per run.** Each check emits machine-readable
   evidence so loop summaries, future races, and human review can see
   which ACs passed, failed, or remained judgment-only.
7. **Dogfood on jig-shaped specs.** The first useful examples should be
   validator/docs/install-contract specs like jig 046/047, because they
   are rich enough to exercise the pattern without requiring product
   taste judgment.

## Non-goals

- **No universal semantic judge.** Servo will not claim one prompt can
  decide whether every arbitrary spec is complete.
- **No replacement for human policy/taste decisions.** ADR choices,
  product positioning, copy tone, and "is this good enough?" judgments
  are surfaced as residual judgment, not auto-passed.
- **No automatic mutation of source specs.** The planner reads specs and
  writes `.servo/spec-oracles/...` artifacts. It does not rewrite the
  source spec's ACs or DoD.
- **No CI productization.** Generated checks may be CI-friendly, but
  this spec does not add GitHub Actions or other CI wiring.
- **No deep natural-language proof.** The first version extracts
  Markdown acceptance criteria by structure and asks the model only for
  classification/candidate generation. Deterministic checks remain the
  source of truth.
- **No hidden dependency on jig.** Jig specs are dogfood fixtures, not a
  hard dependency. The check families must work for non-jig projects.

## Core model

Servo layers evidence instead of trusting a single score:

1. **Repo baseline oracle** — existing `oracle.sh` components from
   scaffold-init: tests, lint, CI, language-specific checks.
2. **Spec overlay oracle** — generated for one spec or slice from its
   acceptance criteria.
3. **Residual judge notes** — ACs that cannot be safely made
   deterministic, plus the reason and suggested human review path.
4. **Evidence ledger** — per-check structured output that shows what was
   actually observed.

The composite score remains the same servo shape: deterministic
components return scores in `[0.0, 1.0]`; env errors return 2; `gate.py`
and `loop.py` do not need a new exit-code contract.

## Evidence contract

The generated plan lives under:

```
<target>/.servo/spec-oracles/<spec-id>/
├── plan.md
├── checks.json
├── oracle.sh.fragment
├── checks.py
└── ledger.jsonl          # produced by check runs, append-only
```

`checks.json` is the machine contract:

```json
{
  "schema_version": 1,
  "spec_id": "046-scaffold-artifact-fidelity",
  "source_spec_path": "docs/specs/046-scaffold-artifact-fidelity/spec.md",
  "source_hash": "sha256:...",
  "planner_version": "0.1.0",
  "baseline_commands": ["python3 scripts/run_tests.py"],
  "checks": [
    {
      "id": "AC-046-01-1",
      "statement": "Stocktake command works from the scaffold target.",
      "family": "generated_artifact_command",
      "status": "generated",
      "command": "python3 .claude/skills/jig-scaffold-init/stocktake.py .",
      "working_directory": "<temp_scaffold>",
      "expected": {"exit_code": 0},
      "failure_message": "stocktake command failed from scaffold target",
      "negative_control": "remove .claude/skills/jig-scaffold-init/stocktake.py"
    }
  ],
  "residual_judgment": [
    {
      "id": "AC-XYZ",
      "reason": "copy tone / product positioning",
      "suggested_review": "human or craft-review pass"
    }
  ]
}
```

The exact schema can evolve before implementation, but the principles are
load-bearing:

- every generated check names the AC it covers;
- every check has an actionable failure message;
- uncovered ACs are explicit;
- the source spec hash is recorded;
- a re-plan is required when the source spec hash changes.

## Check families

First-version deterministic primitives:

| Family | Examples |
|---|---|
| `command` | Run an existing test/lint/build command and assert exit code. |
| `file_presence` | Path exists, path absent, executable bit present. |
| `text_invariant` | Text contains / does not contain string or regex. |
| `json_contract` | JSON file parses; required key exists; value equals expected. |
| `archive_inventory` | Zip/tar contains required paths and excludes forbidden paths. |
| `markdown_links` | Local Markdown links resolve from generated docs. |
| `generated_artifact_command` | Build/scaffold into tempdir, then run a command from that generated tree. |
| `runtime_reference_scan` | Scan live roots for forbidden stale references, excluding historical docs. |
| `residual_judgment` | Explicitly not deterministic in v1. |

These primitives are intentionally boring. Most large projects already
have feature-specific acceptance checks in this shape; servo makes them
cheap to generate and attach to a loop.

## Guardrails

- **Frozen before loop.** `/servo:agent-loop` consumes a generated
  spec-oracle only after it is marked `approved` in `checks.json`.
  A runner iteration must not edit approved oracle artifacts as part of
  satisfying the spec.
- **Hash mismatch refuses.** If the source spec hash changes, the
  spec-oracle exits 2 with `reason=spec_oracle_stale` until re-planned.
- **Negative controls required when feasible.** A generated check should
  include a simple "known bad" mutation or fixture proving that the
  check can fail. The first version can mark `negative_control:
  not_applicable` for command checks that already invoke an existing
  suite, but new generated invariants need controls.
- **Residual judgment blocks auto-complete by default.** A spec-oracle
  with unresolved residual-judgment ACs may still help iteration, but
  it should not report a perfect spec-overlay score unless the user
  explicitly allows judgment-only ACs to be excluded from the composite.
- **Project-owned artifacts.** Generated checks live in the target under
  `.servo/spec-oracles/`; users can inspect and edit them through an
  explicit re-plan flow. Servo does not hide the judge in plugin state.

## SPIDR analysis

| Technique | Question | Decision |
|---|---|---|
| **S — Spike** | Can a useful planner classify real spec ACs into reusable check families? | **Yes, but spike-shaped first slice.** 006-01 validates against existing jig specs 039/046/047 without installing anything. |
| **P — Path** | Generate checks first or integrate with loop first? | **Plan → compile → freeze → integrate.** The loop should consume only reviewed/frozen checks. |
| **I — Interface** | What is the stable boundary? | `checks.json` + `oracle.sh.fragment` + ledger JSONL under `.servo/spec-oracles/<spec-id>/`. |
| **D — Data** | What data makes this safe? | AC mapping, source hash, check family, command/expectation, failure message, negative control, residual judgment. |
| **R — Rules** | What prevents self-grading? | Approved/frozen spec-oracle artifacts, hash checks, negative controls, residual-judgment visibility. |

## Slice index

| Slice | Title | Goal |
|---|---|---|
| 006-01 | evidence-plan | Read a spec/slice and emit a reviewable plan mapping ACs to check families, including uncovered residual judgment. No install. |
| 006-02 | check-library | Implement stdlib-only check primitives and compile generated plans into runnable `checks.py` + `checks.json` against temp fixtures. |
| 006-03 | oracle-overlay | Generate/install an `oracle.sh` component that runs the spec checks, records ledger entries, and composes with the baseline oracle. |
| 006-04 | freeze-and-controls | Add source-hash validation, approval/freeze workflow, and negative-control verification for generated checks. |
| 006-05 | skill-and-dogfood | Ship `/servo:spec-oracle` SKILL.md, anti-greediness tests, and dogfood plans for jig specs 046 and 047. |

---

## Slice 006-01 — evidence-plan

**Goal:** A planning helper that reads a target repo plus a spec/slice
Markdown file and writes a reviewable evidence plan without modifying
the target's oracle. End-to-end value: a user can see which acceptance
criteria are deterministically coverable before trusting an unattended
loop.

**DoR:**
- ✅ Specs 001–003 DONE.
- ✅ A spec path can be provided explicitly; no discovery magic required.
- ✅ First dogfood inputs available: jig specs 039, 046, and 047.

**Acceptance Criteria:**

1. **AC extraction.** Given a Markdown spec or slice with an
   `Acceptance Criteria` section, the helper extracts numbered ACs with
   stable IDs and source line references.
2. **Family classification.** Each AC is classified into one of the
   first-version check families (`command`, `file_presence`,
   `text_invariant`, `json_contract`, `archive_inventory`,
   `markdown_links`, `generated_artifact_command`,
   `runtime_reference_scan`, `residual_judgment`).
3. **Plan output.** The helper writes
   `<target>/.servo/spec-oracles/<spec-id>/plan.md` and
   `checks.json` with `schema_version`, `spec_id`, `source_spec_path`,
   `source_hash`, and one entry per AC.
4. **Uncovered judgment visible.** ACs classified as
   `residual_judgment` include a reason and suggested review path.
5. **No target behavior change.** Slice 006-01 does not edit
   `<target>/oracle.sh`, `.servo/install.json`, or any source file
   outside `.servo/spec-oracles/<spec-id>/`.
6. **Dogfood classification fixtures.** Tests include fixture specs
   shaped like jig 039, 046, and 047 and assert that obvious ACs land in
   deterministic families rather than residual judgment.

**DoD:**
- [x] All ACs pass; full test suite green.
- [x] Test coverage per AC under `skills/spec-oracle/test_oracle_plan.py`.
- [x] Reviewed by `reviewer` subagent.
- [x] Implementation review passed.
- [x] Deviation log produced under this slice heading.
- [x] Reconciliation review passed (inline).
- [x] `docs/refinement-todo.md` updated if any decisions were deferred.

### Close-out (post-DONE)

- [x] `docs/specs/README.md` status board updated.
- [x] README skill table row for `/servo:spec-oracle` flipped to
      IN PROGRESS.

**Anti-horizontal-phasing check:** After this slice, users get a useful
artifact: a concrete answer to "what would servo judge for this spec?"
without yet trusting generated code.

### Deviation log (after reconciliation)

Original ACs above are preserved; this records what changed during
implementation. Implemented 2026-06-09; 43 tests in
`skills/spec-oracle/test_oracle_plan.py`; full suite 470 passed, 1 skipped.

- **Deterministic-only classification (v1).** Family classification is pure
  keyword/regex on the AC statement text — no LLM, no network. The spec's
  non-goal anticipates a *future* model-assisted pass; that is deferred (see
  refinement-todo "spec-oracle family classification is a heuristic first
  pass"). The rule set is ordered, first-match-wins, most-specific-first
  (`generated_artifact_command` before `command`; `runtime_reference_scan`
  before `text_invariant`; `json_contract` before both).
- **Multi-line AC capture (found + fixed in review).** The first cut captured
  only each AC's first physical line, truncating statements and — because the
  classifying keyword often sits on a continuation line — collapsing every
  multi-line deterministic AC into `residual_judgment` (dogfooding this repo's
  own spec 006 produced 0 deterministic / 27 residual). `extract_acs` now joins
  continuation lines into the full statement. Guarded by
  `MultilineRegressionTests`: a keyword-on-3rd-line fixture, plus a spec-006
  `>0`-deterministic tripwire.
- **`checks.json` schema additions.** Beyond the spec's named keys, the payload
  also carries `planner_version`, `generated_at`, per-check `status: "planned"`
  + `source_line`, and a top-level `residual_judgment` array — additive,
  mirroring the Evidence-contract example. The spec licenses this ("the exact
  schema can evolve before implementation").
- **`source_spec_path` recorded as given.** The CLI records the path the user
  passed (typically repo-relative, matching the schema example) rather than an
  absolutised path, so the artifact does not leak filesystem layout.
- **`spec_id` = spec file's parent directory name**, with a `--spec-id`
  override; the pure `extract_acs()` library call falls back to an `AC-SPEC-n`
  scope when given neither a slice heading nor a `spec_id` (every CLI path
  always resolves a real id).
- **Known extraction limitations (logged to refinement-todo).** A continuation
  line that begins with bold (`**…**`) would close the AC section early, and a
  nested numbered sub-list inside an AC would be miscounted as sibling ACs.
  Neither occurs in the fixtures or this repo's specs.
- **`generated_at` reproducibility note.** The wall-clock field makes
  `checks.json` non-reproducible; harmless here but flagged for slice 006-04,
  which hashes generated artifacts.

**Reconciliation review (inline):** deviation log checked against the diff
(faithful); doc changes (board, refinement-todo, README skill row) are scoped
to this slice; no source-spec ACs were rewritten.

---

## Slice 006-02 — check-library

**Goal:** Implement the deterministic check primitives and compile
planned checks into a runnable stdlib-only `checks.py` that emits one
JSON line per AC plus a summary score.

**DoR:**
- ✅ Slice 006-01 DONE.
- ✅ `checks.json` schema from 006-01 is stable enough for first
  implementation.
- ✅ Check primitives do not require network access.

**Acceptance Criteria:**

1. **Primitive coverage.** `checks.py` supports command, file presence,
   text invariant, JSON contract, archive inventory, Markdown local-link,
   generated-artifact command, and runtime-reference scan checks.
2. **Structured output.** A run emits JSONL evidence with
   `schema_version`, `check_id`, `ac_id`, `status`
   (`pass`/`fail`/`env_error`/`not_applicable`), and an actionable
   `message`.
3. **Composite score.** The final summary reports
   `passed_checks`, `failed_checks`, `env_errors`, `not_applicable`,
   and `score` in `[0.0, 1.0]`.
4. **Fixture-proven failures.** Each primitive has at least one passing
   and one failing fixture test, and failing diagnostics name the
   offending path/command/key.
5. **Dependency-free.** The generated runner uses only Python stdlib.

**DoD:**
- [ ] All ACs pass; full test suite green.
- [ ] Test coverage per primitive, including failure diagnostics.
- [ ] Reviewed by `reviewer` subagent.
- [ ] Implementation review passed.
- [ ] Deviation log produced under this slice heading.
- [ ] Reconciliation review passed.

### Close-out (post-DONE)

- [ ] `docs/specs/README.md` status board updated.

**Anti-horizontal-phasing check:** After this slice, a generated plan can
be executed manually and produce AC-level evidence, even before it is
wired into `oracle.sh`.

---

## Slice 006-03 — oracle-overlay

**Goal:** Compile a checked plan into an installable oracle overlay:
`oracle.sh.fragment` plus generated `checks.py`, with a score function
that can be added to the target's `oracle.sh` as a normal servo
component.

**DoR:**
- ✅ Slice 006-02 DONE.
- ✅ Spec 002 `gate.py` contract remains unchanged.
- ✅ `# SEED:` component convention from spec 001 is still the install
  mechanism.

**Acceptance Criteria:**

1. **Fragment generation.** The helper writes an `oracle.sh.fragment`
   containing a valid `# SEED:start spec_oracle_<id>` /
   `# SEED:end spec_oracle_<id>` block.
2. **Install command.** An explicit install mode adds the generated
   component to `oracle.sh` without disturbing existing baseline
   components.
3. **Score semantics.** The generated score is the check summary score;
   any env-error check returns oracle component rc=2.
4. **Ledger entries.** Each oracle run appends check evidence to
   `.servo/spec-oracles/<spec-id>/ledger.jsonl`.
5. **Gate compatibility.** `gate.py <target> --json` sees the overlay as
   an ordinary oracle component; no `gate.py` special case is required.
6. **Uninstall or disable path.** Users can remove or disable the
   overlay component without deleting the plan/check artifacts.

**DoD:**
- [ ] All ACs pass; full test suite green.
- [ ] Tests install the overlay into a temp servo-scaffolded target and
      verify `gate.py --json` pass/fail/env-error paths.
- [ ] Reviewed by `reviewer` subagent.
- [ ] Implementation review passed.
- [ ] Deviation log produced under this slice heading.
- [ ] Reconciliation review passed.

### Close-out (post-DONE)

- [ ] `docs/architecture.md` documents spec-oracle artifacts.
- [ ] `docs/specs/README.md` status board updated.

**Anti-horizontal-phasing check:** After this slice, `/servo:agent-loop`
can optimize against spec-specific AC evidence using the existing gate
contract.

---

## Slice 006-04 — freeze-and-controls

**Goal:** Add the safety layer that prevents self-grading: approval
state, source-spec hash checks, generated-artifact hashes, and negative
control validation.

**DoR:**
- ✅ Slice 006-03 DONE.
- ✅ The project-owned artifact paths are settled.
- ✅ The first generated check fixtures include at least one controllable
  known-bad case.

**Acceptance Criteria:**

1. **Approval state.** `checks.json` carries `approval_status` with
   values `draft`, `approved`, or `stale`. The oracle overlay refuses to
   score as pass when status is not `approved`.
2. **Source hash validation.** If the source spec content changes after
   approval, the overlay exits with env error and a
   `spec_oracle_stale` message until re-planned.
3. **Artifact hash validation.** Approved generated files carry hashes;
   unexpected modification of `checks.py` or `oracle.sh.fragment`
   refuses with an actionable diagnostic.
4. **Negative-control runner.** A validation command exercises
   generated negative controls and refuses approval if a check cannot be
   made to fail.
5. **Loop protection.** Agent-loop documentation and prompts tell the
   runner not to edit approved spec-oracle artifacts; tests assert the
   prompt contains this constraint.

**DoD:**
- [ ] All ACs pass; full test suite green.
- [ ] Tests cover stale source, modified generated artifact, missing
      approval, and negative-control failure.
- [ ] Reviewed by `reviewer` subagent.
- [ ] Implementation review passed.
- [ ] Deviation log produced under this slice heading.
- [ ] Reconciliation review passed.

### Close-out (post-DONE)

- [ ] `docs/architecture.md` documents freeze/approval semantics.
- [ ] `docs/specs/README.md` status board updated.

**Anti-horizontal-phasing check:** After this slice, the oracle overlay
is safe enough to use for unattended implementation without the runner
quietly moving the target.

---

## Slice 006-05 — skill-and-dogfood

**Goal:** Expose the workflow as `/servo:spec-oracle` with clear
anti-greediness bounds, and dogfood it on jig-style specs 046/047 as
worked examples.

**DoR:**
- ✅ Slices 006-01 through 006-04 DONE.
- ✅ At least one jig dogfood target is available locally.
- ✅ The skill name and trigger surface are agreed.

**Acceptance Criteria:**

1. **SKILL.md trigger bounds.** `/servo:spec-oracle` fires on requests
   to generate/specify/evaluate an oracle for a spec, and does not fire
   on "run the oracle" (`quality-gate`) or "iterate on this" (`agent-loop`).
2. **Q&A flow.** The skill asks for target path, spec/slice path,
   baseline commands, and whether to stop after plan generation or
   proceed to install an approved overlay.
3. **Worked examples.** Documentation includes at least two examples
   shaped like jig 046 and 047, showing AC classification and generated
   check families.
4. **Dogfood plan quality.** Running the planner against jig 046/047
   produces plans where the validator/doc/install-contract ACs are
   mostly deterministic and residual judgment is explicit.
5. **No silent approval.** The skill never marks a generated overlay
   `approved` without an explicit user instruction or reviewed approval
   artifact.

**DoD:**
- [ ] All ACs pass; full test suite green.
- [ ] Surface tests under `skills/spec-oracle/test_skill_surface.py`.
- [ ] Dogfood plans committed or recorded as fixtures, with any
      non-deterministic ACs named in the deviation log.
- [ ] Reviewed by `reviewer` subagent.
- [ ] Implementation review passed.
- [ ] Deviation log produced under this slice heading.
- [ ] Reconciliation review passed.
- [ ] `docs/refinement-todo.md` updated for any check family deferred.

### Close-out (post-DONE)

- [ ] `docs/specs/README.md` status board marks spec 006 DONE.
- [ ] README skill table row marks `/servo:spec-oracle` as shipped.

**Anti-horizontal-phasing check:** After this slice, a user can ask
servo to turn a real spec into an evidence overlay, inspect it, approve
it, and then run the existing agent loop against it.

## Open questions

- Should approval be a field in `checks.json`, a separate
  `approval.json`, or a signed/hash-pinned line in `plan.md`?
- Should residual-judgment ACs contribute `0.0`, be excluded from the
  denominator, or force env error until explicitly waived?
- Should generated overlays be one component per spec or one component
  per slice? Lean: per slice for active iteration, with spec-level
  rollup later if needed.
- Should `agent-loop` gain a first-class `--spec-oracle <id>` flag, or
  is installing the overlay into `oracle.sh` sufficient? Lean: install
  into `oracle.sh` first; add a flag only if users need concurrent
  overlays.
- What is the smallest review artifact that counts as explicit approval
  for unattended use?

## References

- [Spec 001 — scaffold-init](../001-scaffold-init/spec.md)
- [Spec 002 — quality-gate](../002-quality-gate/spec.md)
- [Spec 003 — agent-loop](../003-agent-loop/spec.md)
- [ADR-0001 — filesystem-only coupling](../../decisions/adr-0001-reuse-jig-test-detector.md)
- [ADR-0002 — gate caller contract](../../decisions/adr-0002-gate-caller-contract.md)
- [ADR-0003 — fresh subagent roster](../../decisions/adr-0003-fresh-subagent-roster.md)
- [ADR-0004 — session state file format](../../decisions/adr-0004-session-state-file-format.md)
