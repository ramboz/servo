---
status: IN_PROGRESS
kind: feature
dependencies: [033-01, adr-0039, adr-0027]
last_verified:
arch_review: true
frame_review: true
claimed_by: claude/adr-0034-specs-028-jig-fe54d4
---

## Slice 033-04 - native-authoring

**Goal:** A Copilot user expands and independently reviews candidate criteria
without changing human ownership of success or existing Claude authoring.

**DoR:**
- Native output, effective tool restriction and fresh-call behavior are probed.
- Authoring stays attended and time-bounded; no claimed hard native USD budget.

**Acceptance Criteria:**

1. Explicit --backend copilot selects native assisted authoring; existing calls
   retain Claude defaults. Model choice is commanded when explicitly selected,
   never falsely reported as pinned when the default is used.
2. Expansion and review are separate fresh calls, no shared session/resume.
   Neither has tools to edit/run target files; intended input only.
3. Missing CLI/auth/timeout/error or malformed output raises explicit authoring
   errors, no fabricated criteria and no fallback Claude/API calls.
4. Preserve candidate/curation/approval, per-AC human authority, re-run and frozen
   protections. No automatic approval from generation.
5. Record backend/version/model provenance and actual usage when available,
   distinguish unavailable telemetry. Execute an installed positive native
   authoring/independent-review probe separately from fake CLI fixtures.

**DoD:**
- [ ] Native fresh-call, permission, failure and approval fixtures are green.
- [ ] Frame, compliance, craft, architecture and reconciliation reviews pass.
- [ ] Installed live proof and existing Claude authoring tests clear.

## Assumptions

Current headless native text and tool restrictions can satisfy authoring;
execute the probe before claiming completion.

**Anti-horizontal-phasing check:** A consumer obtains independently reviewed
candidates and can curate them through the existing workflow.

### Deviation log (after reconciliation)

Pending.

### Reconciliation sweep

Pending: authoring CLI/helper, independent review/approval, provenance,
skill body, generated packages, docs and board.
