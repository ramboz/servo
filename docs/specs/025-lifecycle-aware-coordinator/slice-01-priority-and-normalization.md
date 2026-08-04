---
status: DRAFT
dependencies: [adr-0030, 024-01]
last_verified: 2026-08-04
---

## Slice 025-01 — priority ranking and lifecycle-aware normalization

**Goal:** The heartbeat coordinator spends each tick on the highest-value work,
ranked by an `oh-my-cli`-style ladder, and dispatches normalized jig bug records
rather than raw text — skipping quarantined and claimed items. Implements the
coordinator half of [ADR-0030](../../decisions/adr-0030-durable-quarantine-and-lifecycle-coordinator.md).

**DoR:**
- ✅ [ADR-0030](../../decisions/adr-0030-durable-quarantine-and-lifecycle-coordinator.md) is the governing record.
- ⬜ Confirm the inbox schema ([ADR-0010](../../decisions/adr-0010-triage-inbox-schema.md))
  and where `_classify_ci` / `_classify_issue` produce the signals to rank on.
- ⬜ Confirm the jig bug-board read path (filesystem) and `bug-fix` entry contract
  for normalization; design the jig-absent fallback.
- ⬜ Depends on 024-01 (quarantine skip) for the quarantined-item filter.

**Acceptance Criteria:**

1. **Priority field + ladder ranking.** The inbox schema carries a
   `priority` / `severity` field; dispatch selects by the ladder (resume
   interrupted > security/data-loss > failing CI > active work > new work > idle)
   computed from `_classify_*`. Observable: given a mixed inbox, a
   security/data-loss finding is selected before new work; a resume-interrupted
   item before a failing-CI item.
2. **Lifecycle-aware normalization.** When jig is co-installed, a new defect is
   dispatched as a structured jig bug record (ACs present, security notes) via the
   `bug-fix` entry over the filesystem, not as free text. Observable: the dispatched
   item is a normalized record in the co-installed fixture; a built-in record in
   the jig-absent fixture (no hard failure).
3. **Skip quarantined + claimed.** The coordinator reads jig's bug board and does
   not dispatch `QUARANTINED` (spec 024) or claimed items. Observable: a
   quarantined/claimed finding is recorded `skipped`; an open one dispatches.
4. **Boundedness preserved.** Ranking changes order only; eligibility remains
   gated by oracle/quarantine/readiness, and the whole-pass cost ceiling
   (ADR-0012) + `max-candidates` still bound the pass. Observable: enabling ranking
   does not increase the number of dispatches beyond `max-candidates`.

**DoD:**
- [ ] All ACs pass; test suite green (no regressions).
- [ ] Each AC covered by ≥1 fixture; each new test shown capable of failing.
- [ ] Reviewed (compliance + craft; +arch — changes the dispatch contract and adds
      a soft cross-tool dependency).
- [ ] Deviation log + reconciliation sweep recorded under this slice.

### Close-out (post-DONE)
- [ ] `docs/specs/README.md` regenerated (status-board).

**Anti-horizontal-phasing check:** After this slice lands, an unattended heartbeat
run works the most important findings first and hands its edit-drivers normalized
records — end-to-end coordinator quality, building on the quarantine skip from
spec 024.

### Deviation log (after reconciliation)

_TBD — not yet implemented (recorded, not built)._

### Reconciliation sweep

| Artifact | Disposition | Rationale |
|----------|-------------|-----------|
| `docs/specs/README.md` | `updated` | _TBD — regenerate at close._ |
| `docs/decisions/README.md` | `no-op` | _ADR-0030 already indexed._ |
