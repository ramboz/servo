---
status: IN_PROGRESS
kind: feature
dependencies: [034-05, adr-0043, adr-0040, adr-0034]
last_verified:
arch_review: true
frame_review: true
claimed_by: claude/adr-0034-specs-028-jig-fe54d4
---

## Slice 034-06 - native-visual-judge

**Goal:** Frozen design evaluation uses a commanded native vision model with
the actual candidate/reference image inputs, preserving capture/statistical policy.

**DoR:**
- Positive live native image ingestion and commanded vision model established.

**Acceptance Criteria:**

1. Explicit copilot transport uses actual --attachment image inputs, not filename
   prose or self-reported advisory subagent results.
2. Capture providers, image hashes, approval/freeze, confidence thresholds,
   ledger and existing api/cli/subagent meanings remain unchanged.
3. Missing model/image/control/invocation capability gives env_error; no provider
   fallback, fabricated score or approved-config migration.
   Apply ADR-0040's explicit native-default decoding/exact-runtime policy and
   reject unsupported numeric controls; no automatic API-default inheritance.
4. Installed positive native visual score and stale/tampered/failure fixtures
   demonstrate actual image-sensitive judging and frozen model behavior.

**DoD:**
- [ ] Frame, compliance, craft, architecture and reconciliation reviews pass.
- [ ] Actual native image/model proof and existing design-eval tests pass.

## Assumptions

The current native CLI can command the required vision model and ingest both
images. Text-only success does not establish this.

**Anti-horizontal-phasing check:** The consumer gates actual captured design
fidelity through the approved frozen component.

### Deviation log (after reconciliation)

1. Native vision uses the same approved capture/freeze/statistical machinery
   with actual candidate/reference image attachments and commanded model.
   Advisory subagent semantics and old API/CLI capture behavior remain unchanged.
2. Initial compliance blocked injection bypass and missing installed proof.
   Native injection now refuses before capture/runtime selection, telemetry is
   retained without USD conversion, and actual installed manual-capture fixture
   scored different solid colors0 using real images/no fake scores.
3. Proof is labelled fixture self-approval/one sample, not independent production
   approval, calibration or monetary assurance. Craft found relative executable
   overrides could probe one binary and invoke another under changed cwd;
   absolute executable identity correction is complete, witnessed with real
   A/B executables across cwd changes and independently re-reviewed. Bare names
   use PATH and one absolute identity is reused for probing/invocation.

### Reconciliation sweep

| Surface | Disposition | Rationale |
|---------|-------------|-----------|
| Native invocation / attachments / identity | updated | Actual ordered image input and strict model/runtime/control checks. |
| Capture providers / approval / statistics / advisory transport | no-op | Preserve existing ownership and score policy; no new capture framework. |
| Freeze / install / ledger / marker | updated | Explicit new native definitions, actual usage/null money and ordered unpriced registration. |
| Executed evidence | updated | Raw image capability versus full installed consumer/fixture consent clearly separated. |
| Skill / generated hosts / live docs | updated | Native opt-in without false per-turn/monetary guarantees. |
| Full CI / reconciliation | deferred | Final integrated gates and independent reconciliation required before DONE. |
