---
status: DONE
dependencies: [001-03, 006-01, adr-0015]
last_verified: 2026-06-27
---

## Slice 015-01 — verdict-contract

**Goal:** A new `suitability.py analyze <target> --spec <path>` emits the
ADR-0015 **suitability verdict** as JSON: the closed three-state enum
(`suitable` / `needs_evidence` / `unsuitable`), `schema_version: 1`, per-reason
rationale, and a **fail-closed default** (indeterminate ⇒ never `suitable`). The
verdict is produced by a **deterministic rule table v1** over the spec text + the
target's detected signals (001) + spec-006 AC classification, and is written to a
project-owned, inspectable artifact. This is the contract every later slice
(missing-evidence enrichment, pipeline gating, skill surface) consumes.

> **Boundary with 015-02 / 015-03.** This slice produces the *verdict* and its
> top-level `reasons`; the **populated `missing_evidence` list** (closed `kind`
> taxonomy, blocking flags) is 015-02. **Wiring the verdict into Servo Compile
> and the heartbeat dispatch path** is 015-03 — this slice only *emits and
> persists* the artifact; it changes no caller. The rule table is intentionally
> small in v1 (explainable, reproducible); the model-assist extension point is
> documented in 015-04, not built here.

**DoR:**
- ✅ **ADR-0015 Accepted** (2026-06-27) — the verdict JSON shape, the closed
  three-state enum, the fail-closed default (indeterminate ⇒ not `suitable`), and
  "a gate not a score" are frozen. This slice implements its `## Verification`
  minimum: closed enum + `schema_version`, indeterminate ⇒ non-`suitable`.
- ✅ **001 DONE** — `/servo:scaffold-init` signal detection exists; the
  `.servo/install.json` manifest records the target's detected signals
  (tests/lint/CI/language) that the rule table reads as the "is there evidence to
  compile?" input. Verify the exact manifest fields the rule table consumes
  during planning.
- ✅ **006 DONE** — `oracle_plan.py` classifies a spec's ACs into the 9
  deterministic families vs `residual_judgment`; `plan.md` + `checks.json` under
  `.servo/spec-oracles/<id>/` expose the per-AC classification this slice reads to
  judge "are the ACs eval-able, or all human-residual?" Consult its output; do not
  reclassify (non-goal).
- ✅ Decision: stdlib-only, Python ≥ 3.11 (spec 009 floor); reuse servo's closed
  exit-code idiom (ADR-0002): `0` = verdict emitted, `2` = env-error (no spec / no
  manifest / unreadable inputs). A non-`suitable` verdict is **still exit 0** — an
  unsuitable verdict is a *successful analysis*, not an error.
- ✅ Decision (resolves spec open-question "Where the artifact lives"): the
  verdict is a **standalone artifact** at `<target>/.servo/suitability/<spec-id>.json`
  (beside `spec-oracles/`), atomically written (`tmp` + `os.replace`). ADR-0016's
  execution plan *references* it rather than copying it; folding it into the plan
  is explicitly deferred to 016.

**Acceptance Criteria:**

1. **Closed three-state verdict.** `suitability.py analyze <target> --spec
   <path>` emits JSON with `verdict ∈ {suitable, needs_evidence, unsuitable}`,
   `schema_version: 1`, `spec_id`, `analyzed_at` (ISO-8601), and a non-empty
   `reasons` array of machine codes + human strings. No fourth state, no numeric
   score field. *Test:* `VerdictShapeTests`.

2. **Fail-closed default.** When the rule table cannot establish suitability with
   evidence, the verdict resolves to `needs_evidence` (a nameable gap exists) or
   `unsuitable` (not EDD-shaped) — **never** an optimistic `suitable`. A spec with
   no eval-able ACs and no signals yields a non-`suitable` verdict, not a green
   default. *Test:* `FailClosedDefaultTests`.

3. **Deterministic rule table v1.** The verdict is computed by an **ordered,
   first-match rule table** (the spec-006 pattern) over (a) spec text features, (b)
   `.servo/install.json` signals, (c) spec-006 AC classification. Same inputs ⇒
   same verdict, byte-stable (no clock/network/randomness in the decision). Each
   fired rule contributes a `reasons` entry naming the rule. *Test:*
   `RuleTableDeterminismTests`.

4. **`unsuitable` vs `needs_evidence` discrimination.** A spec whose ACs are
   **all** `residual_judgment` with no deterministic signal classifies
   `unsuitable` (success is irreducibly human taste). A spec that is EDD-shaped
   (≥1 eval-able AC or a real test/CI signal) but **missing** a blocking input
   classifies `needs_evidence`. *Test:* `VerdictDiscriminationTests`.

5. **Read-only over the target; persisted artifact.** `analyze` does not mutate
   the target's tree or its oracle; it only writes
   `<target>/.servo/suitability/<spec-id>.json` (atomic). Re-running overwrites
   the artifact (re-analysis is idempotent for unchanged inputs). A byte-snapshot
   of the rest of `.servo/` is unchanged. *Test:* `ReadOnlyArtifactTests`.

6. **Closed env-error contract.** Missing/unreadable spec, missing manifest, or
   unparseable spec-006 plan ⇒ exit `2` with a structured stderr reason
   (`spec_missing` / `manifest_missing` / `plan_unreadable`), **no** partial
   artifact written. Never exit `1`; never a torn write. *Test:*
   `EnvErrorContractTests`.

**DoD:**
- [x] All ACs pass; new `test_suitability.py` green (24 tests; full suite 1058
      passed); `ruff check .` clean (pinned 0.15.17).
- [x] Reviewed by the jig compliance + craft passes (recorded under `reviews/`;
      craft + reconciliation are maintainer self-reviews — independent craft
      subagent declined by the maintainer mid-flow).
- [x] Deviation log produced under this slice heading.
- [x] `docs/specs/README.md` regenerated.

### Close-out (post-DONE)
- [ ] If this is not the spec-closing slice, no primer compression required;
      carry the v1 rule-table location forward in the board Notes for 015-02/03.

### Deviation log (after reconciliation)

Original ACs preserved above; the implementation deviated/extended as follows:

- **`reasons[]` shape.** ADR-0015 illustrates `reasons` as `["..."]` (strings).
  AC1 asks for "machine codes + human strings," so each entry is a
  `{"code", "message"}` object instead. Additive, satisfies AC1; consumers that
  branch on the closed `verdict` enum are unaffected.
- **`manifest_malformed` reason code.** AC6 names three env-error reasons
  (`spec_missing` / `manifest_missing` / `plan_unreadable`). The implementation
  adds `manifest_malformed` for a present-but-unparseable manifest — a sound
  fail-closed extension (still exit 2, no artifact). Currently exercised only
  indirectly; an explicit test is deferred to 015-02. (Both review passes flagged
  this as a Low note, not a defect.)
- **v1 signal definition.** Only `tests` / `ci` count as a compilable oracle
  signal; `lint` alone is deliberately insufficient (it becomes a
  `missing_evidence` item in 015-02). This is an implementation choice beyond the
  AC's literal text, made explicit in code + a test.
- **`inputs` block in the artifact.** Beyond ADR-0015's named fields, the
  artifact carries an `inputs` block (signal echo + `ac_counts`) for auditability
  and the 015-04 `--explain` view. Additive; does not alter the closed contract.
- **CLI dispatch nit (fixed in-pass).** The craft pass refactored `main()` from a
  hand-rolled subcommand check to the standard `add_subparsers` +
  dispatch-on-`args.command` idiom used by `heartbeat.py` / `gate.py`. No
  follow-up needed.

### Reconciliation sweep

Drift-prone surfaces checked (`updated` / `no-op` / `deferred`):

- **spec.md open question (artifact location)** — `updated`: resolved to the
  standalone `.servo/suitability/<spec-id>.json` artifact in this slice.
- **ADR-0015 contract** — `no-op`: verdict enum, fail-closed default, and
  "gate-not-score" implemented faithfully; ADR is immutable and unchanged.
- **001 `install.json` `signals` schema** — `no-op`: read-only consumer; the
  `{tests, lint, ci, language}` keys were verified against `scaffold.py`.
- **006 `oracle_plan.py classify` output** — `no-op`: subprocess seam only; the
  `checks` / `residual_judgment` shape was verified against `oracle_plan.py`.
- **015-02 / 015-03 boundaries** — `no-op`: `missing_evidence` left empty; no
  caller wired (gating is 015-03).
- **`docs/specs/README.md` board** — `deferred`: regenerated at DONE close-out.
- **Install-contract / `/servo:edd-suitability` skill surface (007)** —
  `deferred`: the SKILL.md + install-contract entry are slice 015-04; this slice
  ships the helper only.

**Architecture impact:** none — a new standalone skill helper with no caller; no
module boundary or public contract changed, so no ADR (implements the existing
ADR-0015).
