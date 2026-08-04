---
status: DRAFT
dependencies: [adr-0030]
last_verified: 2026-08-04
---

## Slice 024-01 — cross-run quarantine record, heartbeat skip, and release rule

**Goal:** A finding that plateaus is durably quarantined across runs and stops
being re-dispatched every tick, reopening only on new diagnostic evidence — with
the quarantine legible to jig for attest-only bug closure. Implements the
quarantine half of [ADR-0030](../../decisions/adr-0030-durable-quarantine-and-lifecycle-coordinator.md).

**DoR:**
- ✅ [ADR-0030](../../decisions/adr-0030-durable-quarantine-and-lifecycle-coordinator.md) is the governing record.
- ⬜ Confirm where `loop.py` persists `oracle_score_history` / plateau in
  `state.json` and the terminal-reason vocabulary (`oracle_plateau`).
- ⬜ Confirm `heartbeat.py`'s dispatch-candidate filter ("actionable + open") seam.
- ⬜ Decide the fingerprint field set (finding id + normalized failure signature)
  so it is stable across run-ids.

**Acceptance Criteria:**

1. **Cross-run quarantine write.** On `oracle_plateau` (or a repeated identical
   terminal failure), `loop.py` writes `<target>/.servo/quarantine/<fingerprint>.json`
   with the finding id, failure signature, evidence pointer, and a timestamp.
   Observable: a plateau fixture produces the file; the fingerprint is identical
   across two independent run-ids for the same finding.
2. **Heartbeat skip.** A candidate finding with a live quarantine record is
   recorded `skipped` and not dispatched. Observable: a second tick over the same
   inbox does not spawn a loop for the quarantined finding (witnessed
   no-redispatch), while other findings still dispatch.
3. **Release requires new evidence.** The quarantine is treated as cleared only
   when the current evidence pointer differs from the recorded one. Observable:
   re-dispatch stays skipped with an unchanged pointer; a changed pointer re-admits
   the finding.
4. **Attest-only legibility.** The quarantine record exposes exactly the pointer
   jig needs (finding id ↔ bug mapping + evidence location) for jig ADR-0050's
   attest-only ingest, and servo never asks jig to re-score. Observable: the record
   schema round-trips against jig spec 105's ingest fixture; no scorer is invoked
   on the jig side.

**DoD:**
- [ ] All ACs pass; test suite green (no regressions).
- [ ] Each AC covered by ≥1 fixture; each new test shown capable of failing.
- [ ] Reviewed (compliance + craft; +arch — new durable state + a cross-tool
      boundary contract).
- [ ] Deviation log + reconciliation sweep recorded under this slice.

### Close-out (post-DONE)
- [ ] `docs/specs/README.md` regenerated (status-board).

**Anti-horizontal-phasing check:** After this slice lands, a plateaued finding is
attempted a bounded number of times and then durably skipped across ticks —
end-to-end anti-thrash for the coordinator, independent of the priority work in
spec 025.

### Deviation log (after reconciliation)

_TBD — not yet implemented (recorded, not built)._

### Reconciliation sweep

| Artifact | Disposition | Rationale |
|----------|-------------|-----------|
| `docs/specs/README.md` | `updated` | _TBD — regenerate at close._ |
| `docs/decisions/README.md` | `no-op` | _ADR-0030 already indexed._ |
