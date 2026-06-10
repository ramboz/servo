---
status: DONE
dependencies: []
last_verified: 2026-06-09
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

