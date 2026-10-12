---
status: DONE
kind: feature
dependencies: [034-01, adr-0043, adr-0040, adr-0042, adr-0005, adr-0024]
last_verified: 2026-10-12
arch_review: true
frame_review: true
---

## Slice 034-05 - native-text-judges

**Goal:** Generic eval and content-fidelity consumers obtain native frozen
gating scores without changing existing transport meanings or scoring policy.

**DoR:**
- Executed native pinned-model/read-only text contract established.

**Acceptance Criteria:**

1. Explicit judge.transport copilot and --transport copilot flow through
   config/CLI/freeze/install/score for both consumers; existing api/Claude cli
   defaults/meanings and approved artifacts are not automatically migrated.
2. Each fresh independent native judge commands the configured non-auto model
   and receives intended prompt input with effective tool restrictions.
   Require an explicit frozen `decoding_mode: native-default` and exact
   `runtime_version` (ADR-0040); reject `temperature`/`max_tokens` and explicit
   numeric-control arguments. Emit/scaffold cannot silently inherit API defaults.
   Version is a compatibility bound, not proof of stable server-side decoding.
3. Preserve frozen evidence/reference/rubric/config hashes, human approval,
   sample count, confidence lower bound, thresholds, manifests and ledger.
   Native transport supplies responses, not a replacement statistical policy.
4. Missing CLI/auth/timeout/error/bad score/model/controls yield env_error, not
   a successful zero/injected score or provider fallback. Provenance identifies
   commanded backend/model and available versus unavailable usage.
5. Installed positive native text scoring for both consumers is separately
   recorded from fixtures. Stale freeze and failed native calls cannot gate pass;
   old transports remain compatible.

**DoD:**
- [x] Native freeze/install/score positive and negative tests show red-to-green.
- [x] Frame, compliance, craft, architecture and reconciliation reviews pass.
- [x] Installed live proof and existing statistical/freeze tests clear.

## Assumptions

Native commanded model and intended decoding controls can satisfy frozen text
judging; unsupported requirements must refuse, not silently relax.

### Generic acquisition readiness supplement

The real installed generic probe exposed the pre-existing candidate-gather stub.
[ADR-0042](../../decisions/adr-0042-native-generic-candidate-files.md) defines the
bounded native-only file seam needed to satisfy the original positive consumer
criteria; original criteria above are retained.

- Require per-case candidate_file inside config.json's component base, with
  frozen `component-file-utf8-v1` policy/path; old API hashes remain unchanged.
- Freeze path/policy, not moving output bytes. Producer deliberately publishes
  real output; no case.input-as-output, fake score or command runner.
- Reject escapes/missing/non-file/non-UTF8/NUL data before judging; read one
  coherent snapshot per case/sample batch and record path/policy/SHA256.
- Native injection hooks cannot bypass runtime/model/attachment contracts.
- Native file-v1 supports only constraint-free scored cases; unsupported
  expected_output.constraints and native fake-actuals injection refuse before
  model calls. Actual-value extraction is a separate inherited residual, not
  supplied by reading a candidate file or by the installed positive proof.

**Anti-horizontal-phasing check:** Consumers get an installed frozen gating
component, not a new transport enum without end-to-end behavior.

### Deviation log (after reconciliation)

1. Added explicit native generic/content config/CLI/freeze/install/score through
   the existing statistical harness, with deliberate native-default/exact-runtime
   consent, closed native judge controls and no approved-config migration.
2. Initial compliance blocked native fake-score/actual injection, discarded
   telemetry and the inherited generic candidate stub. Native injection now
   refuses before selection, actual vendor usage/null is retained in provenance,
   and ADR-0042 supplies real component-contained candidate-file snapshots.
3. ADR-0042 is deliberately constraint-free file-v1: freeze path/policy, not
   moving output bytes; unsupported constraints/invalid files fail before models.
   Actual emitted installed generic score1 and installed content score1 are real
   native calls, not fake hooks; sample/fixture limitations are explicit.
4. Craft requested a literal historical API hash fixture and qualification of
   stale legacy acquisition prose. Compliance found cyclic-symlink resolution
   escaping env_error on Python3.9. Corrections are complete: actual cyclic-path
   red-to-green on Python3.9, literal historical digest and legacy-only live prose;
   independent resolution re-review clears the remaining blocker.

### Reconciliation sweep

| Surface | Disposition | Rationale |
|---------|-------------|-----------|
| Generic/content config/CLI/freeze/install/score | updated | Explicit native transport, coherent file-v1 acquisition and unknown usage provenance. |
| Old API/CLI hashes/configs/statistical policy | no-op | Definitions/call meanings preserved; no automatic migration or replacement aggregation. |
| Native injection / controls / model/runtime | updated | Unsupported/injected paths refuse rather than fabricate passing scores. |
| Native registry / re-freeze ordering | updated | Mark before native activation, reverse after approval; bounded caller enforcement is034-08. |
| Proof / skills / README / architecture | updated | Actual consumers, constraint-free limitation and no SUTcommand/measurement claim. |
| Old closed records | no-op | Preserved; no amendments authorized. |
| Full CI / final reconciliation | updated | Independent verdicts clear; synchronized exact CI passes2255 tests plus all150 install tests/manifests/Ruff/drift gates. |
