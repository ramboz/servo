---
status: RECONCILED
kind: feature
dependencies: [adr-0044]
last_verified: 2026-10-14
frame_review: true
arch_review: true
claimed_by: servo-installed-required-gate
review_reopened_at: 2026-10-15T03:44:29Z
---

## Slice 035-01 - installed-required-gate

**Goal:** A developer opts an existing deterministic overlay into approved
required policy and gets an honest, non-averageable verdict from the installed
project quality gate.

**DoR:**
- ADR-0044 accepted only after parent alignment and fresh frame critique.
- Required-field/result-channel/version-2 proposal independently reviewed;
  unavailable evidence, identity serialization/approval closure and migration
  behavior pinned. Existing command-check fixtures are available.
- No completed Vellum/Jig slice, design capture or not-yet-written observer is
  required. New installed-result/race proof is delivered by this slice, not
  required before starting it; existing frozen policy is not altered to pass.

**Acceptance Criteria:**

1. **Installed end-to-end policy.** A documented project-owned flow configures
   required existing `command` or `generated_artifact_command` assertions,
   reviews the required set, explicitly approves/freezes and installs them,
   then runs the real `gate.py <target> --json`. Generation/installation alone
   never approve. Existing scalar components remain installed and diagnostic.
2. **Contradiction veto.** With quality at least 0.99 and threshold 0.5, one
   required assertion failing yields oracle and gate exit 1, v2 `fail`,
   `required_constraints_failed` and the failed ID/reason. Repeat with
   `THRESHOLD=0` and a zero required-component weight: it still fails. An
   observed required absence is a failure, not unavailable capture.
3. **Refusal and complete-set proof.** Missing result, unavailable check,
   unknown/unsupported required check, duplicate/extra/omitted required ID,
   invalid result/version, unapproved or edited policy, stale run or wrong
   component/config/artifact identity yields exit 2 and a specific per-item
   cause under `required_evidence_unavailable`. A known failure plus unknown
   evidence returns 2 while retaining the known failure. No pruning, empty
   denominator or stale ledger success can produce pass.
4. **Single invocation, bound result.** A side-effect counter proves each
   component/check runs once per evaluation. Numeric diagnostic and structured
   evidence share that invocation. Two concurrent gates cannot consume each
   other's result; partial writes and mismatched run IDs refuse. The complete
   approved required set, score, raw check evidence, interpreted verdict and
   hashes are recoverable from the existing component artifacts/ledger. The
   overall gate record binds each immutable component result by its content
   digest and that exact gate run, not a component-owned success label.
5. **Decision table.** Required pass plus high quality returns 0; required
   pass plus low quality returns 1/`quality_below_threshold`; required fail
   plus low quality returns 1/`required_and_quality_failed`. Required-state
   counts and IDs match evidence; composite/threshold remain available but
   are not used as a proxy for a required verdict. A passing deterministic
   component plus failed quality threshold yields a preserved overall `fail`;
   the component's passing envelope cannot be used as completion authority.
6. **Compatibility and installation.** With no required policy, old scalar
   checks, `--score-only`, default scaffold, custom SEED functions, v1 gate
   payload and 0/1/2 behavior remain unchanged. Enabling policy upgrades the
   relevant driver explicitly and refuses unsupported/customized shapes
   without half-writing or silent fallback. Reinstall/uninstall is idempotent;
   removal of a still-required component refuses until explicit policy
   revision. Canonical templates/installers and generated Claude/Codex/Copilot
   packages plus supported vendored gate/check paths carry the same behavior.

**DoD:**
- [x] Witnessed failing-to-passing tests cover every criterion and controls.
- [x] Real scaffold -> approve -> install -> gate exercises pass/fail/refusal
      in supported installed packages, not just direct scorer calls.
- [x] Required compliance, craft and architecture reviews pass.
- [x] Documentation, deviation log, reconciliation sweep and review complete.

## Assumptions

- The existing artifact seam can carry an invocation-bound result without
  races. AC4 is the bounded validation; do not assume a ledger timestamp proves it.
- Cross-project consumers accept the v2 proposal after parent reconciliation.

**Anti-horizontal-phasing check:** The developer can already enforce required
checks and read concrete failures with the installed CLI, without waiting for
the design component or unattended consumer slice.

### Deviation log (after reconciliation)

No material change to Accepted ADR-0044 or original AC1-6. The reviewed plan's
carrier is implemented in quality-gate-owned `required_runtime.py`; the default
oracle template stays byte-identical and only explicit supported installs
upgrade the driver. The loop change solely vendors that sibling dependency,
not 035-02 consumer behavior.

Independent reviews exposed invocation-path closure and migration bugs, fixed
with witnessed installed red-to-green regressions. Conservative unsupported
shapes now refuse: relative PATH entries for bare executables, unsupported
interpreter/module/option-separator argv, and generated relative script
entrypoints. These limitations are documented, not optimistic fallbacks.
False-only annotations retain legacy scalar freeze. Missing gate-side carrier
emits v2 unknown refusal before invocation, with null run ID; it is not an
attestable run. See [implementation receipt](implementation-receipt.md) for
historical and final-byte evidence.

The craft nit was addressed by forging only composite against unchanged
effective quality policy. The arch nit was addressed by scoping stateless
wording to v1. Source provenance remains distinct from future evaluated-build/
served linkage; 035-02 and 036 stay DRAFT.

The final audit after initial reconciliation found typed-JSON aliases and
numeric overflow in malformed results, plus byte-encoding regressions in
marker-only legacy detection. The local helper review cycle was reopened to
IN_PROGRESS, the cases witnessed red and corrected, and compliance/craft/arch
refreshed against the final bytes. Typed domains now refuse rather than
coerce malformed proof; marker discovery alone is encoding-tolerant, not
required JSON. Historical validation/captures remain explicitly historical
in the receipt. No new framework or policy semantics were introduced.

### Reconciliation sweep

| Surface | Disposition / evidence |
|---|---|
| CLI, approved checks/overlay, scaffold/SEED and project vendors | updated; installed positive/negative/concurrent controls and unsupported-shape refusal in current-source tests |
| Host packages and install contract | updated; generated with existing builder, drift checks and actual three-host scaffold/approve/install/gate controls |
| Live README/skills/architecture | updated; opt-in/default split, actual fields, preserved overall authority and conservative evaluator limits; v1 stateless wording corrected |
| Spec/tasks/reviews/board | updated through helpers; original ACs preserved, independent readiness and real review-recovery chronology retained |
| Decision records/conventions/closed specs | no-op; Accepted ADR-0044 owns the boundary, no new architecture decision or convention amendment, no closed record edits |
| Leanness/lightweight decisions | no-op; no registry, duplicate evaluator, configurable framework or unrelated UI decision; carrier only meets the approved slice |
| Inbox/refinement ownership | no-op; no inbox file/item to resolve; deferred consumer and design work already belongs to 035-02/036 |
| Primers and close-out | no-op for absent AGENTS/CLAUDE primers; spec035 remains active because 035-02 is DRAFT, no closed-spec compression |
| Memory | updated via installed memory helper; actual invocation-path closure and overall-authority learning; team advisory skipped this bounded run without adding unrelated people metadata |
| Use-case coverage | no-op by helper: vision has no Use cases section |
| Cross-project integration | deferred to coordinator; no source capture, design observer, served/current-delivery proof or native Copilot autonomy claimed |

**Selected-parent inventory boundary:** this slice's changed-file set is
`git diff --name-only a383c8761afaab010f133207876d1c6f01ff2b2e`, including the
staged implementation. The reconciliation helper's `main...HEAD` list uses a
stale local main reference and includes inherited accepted-parent work. Its
CONTRIBUTING.md, CHANGELOG.md, plugin/release metadata, release workflows,
older closed specs/ADRs and product-vision/refinement changes are deliberately
excluded: no delta in those paths against the selected parent is owned by
035-01. This is not permission to amend/reconcile those closed records. The
complete selected-parent manifest is enumerated in the implementation receipt;
generated host paths are accounted by their explicit roots/files there.

### Close-out (post-DONE)

- [ ] Regenerate board and record opt-in/default compatibility invariants.
- [x] Reconcile live gate/skill/install documentation; preserve closed records.
