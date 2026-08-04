---
status: DRAFT
dependencies: [adr-0030, adr-0011, adr-0012]
last_verified: 2026-08-04
---

# Spec 024 — durable-cross-run-quarantine

> **Status: recorded, not yet built.** Implements the quarantine half of
> [ADR-0030](../../decisions/adr-0030-durable-quarantine-and-lifecycle-coordinator.md)
> (Proposed). Reserved; the `loop.py` / `heartbeat.py` changes below are not
> implemented in the branch that introduced this record. Left DRAFT deliberately.
> This is the **servo half** of the durable failure-quarantine piece; the jig half
> is jig spec 105 (jig ADR-0050).

## Why this spec

`loop.py` persists a plateau signal only per run-id
(`<target>/.servo/runs/<run-id>/state.json`), so each heartbeat tick starts fresh
and re-dispatches the same doomed finding forever — the long-horizon thrash
failure. [ADR-0030](../../decisions/adr-0030-durable-quarantine-and-lifecycle-coordinator.md)
decides a durable, cross-run quarantine keyed by a stable failure fingerprint,
plus a heartbeat dispatch skip, plus the attest-only handshake to jig ADR-0050.

## Goals (provisional)

1. On `oracle_plateau` / repeated identical terminal failure, `loop.py` writes a
   cross-run `<target>/.servo/quarantine/<fingerprint>.json` keyed by a stable
   per-finding failure fingerprint.
2. `heartbeat.py`'s dispatch-candidate filter skips a fingerprinted finding with a
   live quarantine record (recorded `skipped`, not dispatched).
3. A quarantine record clears only on **new diagnostic evidence** (changed evidence
   pointer) — the servo mirror of jig ADR-0050's release rule.
4. Attest-only handshake: when a quarantined finding maps to a jig bug, jig reads
   the servo evidence pointer and advances the bug attest-only (jig ADR-0050);
   servo owns the fingerprint, jig only reads it.

## Vertical slices

- **024-01 — cross-run quarantine record + heartbeat skip + release rule:** the
  fingerprint, the `.servo/quarantine/` write on plateau, the dispatch skip, and
  the new-evidence clear. See the slice file for ACs.

## Notes

- Fingerprint stability across runs is the load-bearing property; define it over
  finding id + a normalized failure signature (not the raw run-id).
- Boundary: servo writes; jig does cheap reads via subprocess/filesystem only
  (ADR-0011 / jig ADR-0022) — no shared imports, jig never re-derives a score.
