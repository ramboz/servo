---
status: DRAFT
dependencies: [adr-0030, adr-0010, adr-0012]
last_verified: 2026-08-04
---

# Spec 025 — lifecycle-aware-coordinator

> **Status: recorded, not yet built.** Implements the coordinator half of
> [ADR-0030](../../decisions/adr-0030-durable-quarantine-and-lifecycle-coordinator.md)
> (Proposed). Reserved; the `heartbeat.py` ranking + normalization changes below
> are not implemented in the branch that introduced this record. Left DRAFT
> deliberately. Part of the long-horizon autonomy bridge (the `oh-my-cli`
> follow-on).

## Why this spec

`heartbeat.py` dispatches in pure arrival order (no priority field) and dispatches
raw finding text rather than a normalized work item. A long-horizon coordinator
should spend each tick on the highest-value work and normalize before touching
code — `oh-my-cli`'s discipline. The ranking signals already exist in
`_classify_ci` / `_classify_issue`; they are just not used to order or normalize.
[ADR-0030](../../decisions/adr-0030-durable-quarantine-and-lifecycle-coordinator.md)
decides the priority ladder + lifecycle-aware normalization.

## Goals (provisional)

1. The heartbeat inbox schema gains a `priority` / `severity` field; dispatch
   selection ranks by an `oh-my-cli`-style ladder (resume interrupted >
   security/data-loss > failing CI > active work > new work > idle) computed from
   the existing `_classify_*` signals, instead of FIFO.
2. Before dispatch, a new defect is normalized through jig's `bug-fix` entry when
   jig is co-installed (structured record with ACs + security notes over the
   filesystem), not dispatched as free text; a built-in fallback covers the
   jig-absent case.
3. The coordinator skips `QUARANTINED` (spec 024) and claimed items by reading
   jig's bug board.
4. Boundedness preserved: whole-pass cost ceiling (ADR-0012) + `max-candidates` +
   readiness gate (spec 023) + quarantine skip (spec 024) are the four bounds;
   "never complete" stays idle-not-terminal.

## Vertical slices

- **025-01 — priority ranking + lifecycle-aware normalization:** the `priority`
  field, the ladder-based selection, jig-bug normalization on dispatch, and the
  quarantined/claimed skip. See the slice file for ACs.

## Notes

- Priority is advisory *ordering* over the same candidate set; eligibility stays
  oracle/quarantine/readiness-gated — ranking changes order, not what is eligible.
- Normalization degrades gracefully when jig is absent; servo must not hard-depend
  on jig's bug board (ADR-0011 boundary posture).
