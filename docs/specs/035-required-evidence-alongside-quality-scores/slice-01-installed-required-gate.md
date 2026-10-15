---
status: IN_PROGRESS
kind: feature
dependencies: [adr-0044]
last_verified:
frame_review: true
arch_review: true
claimed_by: servo-installed-required-gate
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
- [ ] Witnessed failing-to-passing tests cover every criterion and controls.
- [ ] Real scaffold -> approve -> install -> gate exercises pass/fail/refusal
      in supported installed packages, not just direct scorer calls.
- [ ] Required compliance, craft and architecture reviews pass.
- [ ] Documentation, deviation log, reconciliation sweep and review complete.

## Assumptions

- The existing artifact seam can carry an invocation-bound result without
  races. AC4 is the bounded validation; do not assume a ledger timestamp proves it.
- Cross-project consumers accept the v2 proposal after parent reconciliation.

**Anti-horizontal-phasing check:** The developer can already enforce required
checks and read concrete failures with the installed CLI, without waiting for
the design component or unattended consumer slice.

### Close-out (post-DONE)

- [ ] Regenerate board and record opt-in/default compatibility invariants.
- [ ] Reconcile live gate/skill/install documentation; preserve closed records.
