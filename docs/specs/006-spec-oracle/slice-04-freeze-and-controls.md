---
status: DONE
dependencies: []
last_verified: 2026-06-10
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
- [x] All ACs pass; full test suite green.
- [x] Tests cover stale source, modified generated artifact, missing
      approval, and negative-control failure.
- [x] Reviewed by `reviewer` subagent.
- [x] Implementation review passed.
- [x] Deviation log produced under this slice heading.
- [x] Reconciliation review passed.

### Close-out (post-DONE)

- [x] `docs/architecture.md` documents freeze/approval semantics.
- [x] `docs/specs/README.md` status board updated.

**Anti-horizontal-phasing check:** After this slice, the oracle overlay
is safe enough to use for unattended implementation without the runner
quietly moving the target.

### Deviation log (after reconciliation)

Original ACs above are preserved; this records what changed during
implementation. Implemented 2026-06-10; +7 engine freeze tests
(`test_checks.py` `FreezeEnforcementTests`), +6 overlay approve/freeze tests
(`test_oracle_overlay.py` `ApproveTests` + CLI), +1 runner-prompt test
(`test_loop.py`); full suite 605 passed, 1 skipped.

- **Freeze is opt-in at the engine, mandatory at the installed component.**
  `checks.py` gained `--enforce-freeze`; bare `checks.py` (planning/inspection)
  is unchanged (backward-compatible with 006-02/03), while the generated
  `score_spec_oracle_<id>` runs with `--enforce-freeze` so only the *installed*
  overlay enforces. The gate runs **before** any check executes or the ledger is
  written, so an unapproved/stale/tampered overlay never runs.
- **AC1 approval** — `approval_status` ∈ {draft, approved, stale} lives in
  `checks.json`; `--enforce-freeze` refuses (exit 2, `spec_oracle_unapproved`)
  unless `approved` (missing field defaults to draft → refused).
- **AC2 source hash** — the gate re-hashes `source_spec_path` against the recorded
  `source_hash` → `spec_oracle_stale` on drift; `approve` likewise refuses to
  approve an already-drifted source.
- **AC3 artifact hashes** — `approve` records sha256 of `checks.py` +
  `oracle.sh.fragment` in `approved_artifacts`; the gate refuses
  (`spec_oracle_artifact_modified`) on mismatch.
- **AC4 negative-control runner** — a `negative_control` is a **spec-override
  dict** merged onto the check and run in isolation, which must yield `fail`
  (non-destructive — distinct from the spec's illustrative "remove a file"
  description). `approve` refuses if a control does not fail (the check is not
  falsifiable). v1 leniency: a check with no control (or `"not_applicable"`) is
  skipped — see below.
- **AC5 loop protection** — `agents/runner.md` ("What to avoid") forbids editing
  approved spec-oracle artifacts, names `spec_oracle_artifact_modified`, and
  frames it as self-grading; asserted by `RunnerVerdictBlockTests`.
- **New env-error reasons:** `spec_oracle_unapproved`, `spec_oracle_stale`,
  `spec_oracle_artifact_modified`, `spec_oracle_plan_modified`.
- **006-03 integration tests updated.** `GateIntegrationTests` now `approve` the
  overlay after install — a legitimate consequence of the installed component now
  enforcing freeze (without approval it correctly refuses rc=2), not a regression
  mask.

**Review response (independent `jig:reviewer`: needs-changes → resolved).** The
reviewer flagged that `checks.json` — which holds the approval fields and the
recorded hashes — was not itself protected, so honest relaxation of a check in
`checks.json` was not caught (the ACs only mandate hashing `checks.py` /
`oracle.sh.fragment`). **Hardened in-slice:** `approve` now records
`approved_content_hash` (a hash of the `checks` + `residual_judgment` content)
and the gate refuses (`spec_oracle_plan_modified`) when the approved checks are
relaxed. Two further findings were dispositioned as **disclosed, spec-sanctioned
v1 behaviour** rather than fixed: (a) the negative-control leniency (absent
control skipped — `docs/refinement-todo.md` carries the tightening: require
controls for new non-`command` invariants + planner control-generation); (b) the
freeze hashes are **tripwires for honest drift, not an anti-adversarial
sandbox** — a runner that writes arbitrary files could rewrite both an artifact
and its recorded hash, so the defense against a *deliberately* self-rewriting
runner is the AC5 prompt constraint + the human approval flow, per ADR-0001's
filesystem-only trust model. Both, plus the source-fields-optional skip, are now
documented in `docs/architecture.md` ("Spec-oracle freeze & approval" → Threat
model).

**Reconciliation review (inline):** deviation log checked against the diff
(faithful — no source-spec ACs or DoD rewritten). Changes are scoped to
`checks.py` / `oracle_overlay.py` / `agents/runner.md` + their tests, the 006-03
`GateIntegrationTests` approval update, and docs (architecture freeze subsection,
refinement-todo entry, board, this slice). The review's needs-changes is resolved:
the material `checks.json`-integrity gap was closed with the `approved_content_hash`
tripwire; the remaining (inherently un-closeable in a filesystem-only model)
limits are disclosed in the threat model rather than hidden.

## Amendments

- **2026-07-02 (spec 019-01 / ADR-0022):** the "source-spec hash checks" this
  slice's Goal/AC1 describe were **removed** from `checks.py --enforce-freeze`
  — the runtime freeze gate now compares only the parsed AC set
  (`approved_content_hash`), not a live hash of the raw source-spec file. The
  one-time `approve()` source-hash check (this slice's AC2, at approval time
  only) is unchanged. Rationale: a living-document spec consumer (jig)
  mutates the source file's bytes on every lifecycle transition without
  changing any AC, which made `--enforce-freeze` trip `spec_oracle_stale` on
  every transition. See [ADR-0022](../../decisions/adr-0022-freeze-against-parsed-acs.md)
  and [spec 019-01](../019-compile-core-simplification/slice-01-freeze-parsed-acs.md).
  This record is preserved as historical fact for what 006-04 originally
  shipped; it no longer describes `--enforce-freeze`'s current behavior for
  the source-hash portion.

---

