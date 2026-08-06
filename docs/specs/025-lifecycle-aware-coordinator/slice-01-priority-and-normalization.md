---
status: READY_FOR_IMPLEMENTATION
dependencies: [adr-0030, 024-01]
arch_review: true
last_verified: 2026-08-06
---

## Slice 025-01 — priority ranking and lifecycle-aware normalization

**Goal:** The heartbeat coordinator spends each tick on the highest-value work,
ranked by a ladder computed from today's signals, and dispatches normalized
records rather than raw text — skipping quarantined and claimed items. Implements
the coordinator half of
[ADR-0030](../../decisions/adr-0030-durable-quarantine-and-lifecycle-coordinator.md)
as reframed by its 2026-08-06 frame-critique.

**DoR:**
- ✅ [ADR-0030](../../decisions/adr-0030-durable-quarantine-and-lifecycle-coordinator.md) is the governing record (Accepted).
- ✅ Inbox schema confirmed ([ADR-0010](../../decisions/adr-0010-triage-inbox-schema.md)):
  `SCHEMA_VERSION = 2` (heartbeat.py:131), canonical key order in
  `_normalize_record` (heartbeat.py:809), reader refuse-higher / warn-lower in
  `_read_inbox_for_status` (heartbeat.py:1149). Ranking signals: `_classify_ci`
  (heartbeat.py:410) yields the default-branch CI verdict; `_classify_issue`
  (heartbeat.py:447) inspects issue labels. **No signal exists** for
  resume-interrupted or active-work (deferred).
- ✅ jig board path confirmed: `docs/bugs/*.md` with frontmatter `status` +
  `claimed_by`; jig's `VALID_BUG_STATUSES` has **no `QUARANTINED`** today
  (unlanded jig ADR-0050) — servo reads a configurable skip-status set and
  fail-opens when the board is absent/unreadable.
- ✅ Depends on 024-01 (the `quarantined` status + skip).

**Acceptance Criteria:**

1. **Priority field + ladder ranking (computable rungs).** The inbox schema carries
   a `priority` field; `SCHEMA_VERSION` bumps 2 -> 3 with the ADR-0010 migration
   (discover rebuilds a `< 3` inbox on write; a v2 reader refuses a v3 inbox rc=2;
   `status` warns on a lower version). Dispatch selects by the ladder
   **security/data-loss > failing-CI > new work > idle** (tie-break: existing
   `discovered_at`, `finding_id`), where `security/data-loss` is a new
   `_classify_issue` severity gate over a configurable critical-label set.
   Observable: given a mixed inbox, a security-labelled issue is selected before a
   plain new-work finding, and a default-branch CI failure before new work; a v2
   inbox is transparently rebuilt to v3 on the next discover; a v2 reader refuses a
   v3 inbox rc=2.
2. **Lifecycle-aware normalization.** When jig is co-installed, a new defect is
   dispatched as a structured record (ACs present, security notes) produced via
   jig's `bug-fix` entry over the filesystem; when jig is absent, a servo built-in
   structured record is produced — never raw free text, and never a hard failure.
   Observable: the dispatched item is a normalized record in the co-installed
   fixture and a built-in record in the jig-absent fixture.
3. **Skip quarantined + claimed (fail-open).** The coordinator does not dispatch a
   `quarantined` finding (spec 024) and, **when a readable jig board is present**,
   does not dispatch a finding whose mapped jig bug is claimed or in the
   servo-configured skip-status set; when the board is absent or unreadable, it
   dispatches normally. Observable: a quarantined finding and a claimed-bug finding
   are skipped against a servo board fixture; with no board present, the same
   finding dispatches (fail-open).
4. **Boundedness preserved.** Ranking changes order only; eligibility remains gated
   by oracle / quarantine / readiness, and the whole-pass cost ceiling (ADR-0012) +
   `max-candidates` still bound the pass. Observable: enabling ranking does not
   increase the number of dispatches beyond `max-candidates`, and the same
   candidate set (reordered) is eligible.

**DoD:**
- [ ] All ACs pass; test suite green (no regressions).
- [ ] Each AC covered by ≥1 fixture; each new test shown capable of failing.
- [ ] Reviewed (compliance + craft; +arch — changes the dispatch contract, bumps
      the inbox schema, and adds a soft cross-tool dependency).
- [ ] Host packages regenerated (`hosts/claude`, `hosts/codex`) + manifests valid.
- [ ] Deviation log + reconciliation sweep recorded under this slice.

### Close-out (post-DONE)
- [ ] `docs/specs/README.md` regenerated (status-board).

**Anti-horizontal-phasing check:** After this slice lands, an unattended heartbeat
run works the most important findings first and hands its edit-drivers normalized
records — end-to-end coordinator quality, building on the quarantine skip from
spec 024.

### Deviation log (after reconciliation)

_TBD — filled at reconciliation._

### Reconciliation sweep

| Artifact | Disposition | Rationale |
|----------|-------------|-----------|
| `docs/specs/README.md` | `updated` | _TBD — regenerate at close._ |
| `docs/decisions/README.md` | `no-op` | _ADR-0030 already indexed._ |
