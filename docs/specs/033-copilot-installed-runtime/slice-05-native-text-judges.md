---
status: IN_PROGRESS
kind: feature
dependencies: [033-01, adr-0039, adr-0040, adr-0005, adr-0024]
last_verified:
arch_review: true
frame_review: true
claimed_by: claude/adr-0034-specs-028-jig-fe54d4
---

## Slice 033-05 - native-text-judges

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
- [ ] Native freeze/install/score positive and negative tests show red-to-green.
- [ ] Frame, compliance, craft, architecture and reconciliation reviews pass.
- [ ] Installed live proof and existing statistical/freeze tests clear.

## Assumptions

Native commanded model and intended decoding controls can satisfy frozen text
judging; unsupported requirements must refuse, not silently relax.

**Anti-horizontal-phasing check:** Consumers get an installed frozen gating
component, not a new transport enum without end-to-end behavior.

### Deviation log (after reconciliation)

Pending.

### Reconciliation sweep

Pending: both config/CLI/freeze/score/ledger surfaces, shared invocation,
approved historical configs, statistical policy, docs and generated packages.
