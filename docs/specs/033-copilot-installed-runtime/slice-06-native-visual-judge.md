---
status: IN_PROGRESS
kind: feature
dependencies: [033-05, adr-0039, adr-0040, adr-0034]
last_verified:
arch_review: true
frame_review: true
claimed_by: claude/adr-0034-specs-028-jig-fe54d4
---

## Slice 033-06 - native-visual-judge

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

Pending.

### Reconciliation sweep

Pending: capture, images, model/transport validation, freeze, score, ledger,
advisory separation, documentation and generated packages.
