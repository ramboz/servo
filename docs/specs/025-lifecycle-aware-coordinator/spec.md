---
status: IN_PROGRESS
dependencies: [adr-0030, adr-0010, adr-0012]
last_verified: 2026-08-06
---

# Spec 025 — lifecycle-aware-coordinator

> Implements the coordinator half of
> [ADR-0030](../../decisions/adr-0030-durable-quarantine-and-lifecycle-coordinator.md)
> (Accepted; reframed by its 2026-08-06 frame-critique). Part of the long-horizon
> autonomy bridge (the `oh-my-cli` follow-on). Builds on spec 024's `quarantined`
> skip.

## Why this spec

`heartbeat.py` dispatches in pure arrival order (`_select_candidates` sorts by
`discovered_at` then `finding_id`) and frames raw finding text as the loop prompt
rather than a normalized work item. A long-horizon coordinator should spend each
tick on the highest-value work and normalize before touching code — `oh-my-cli`'s
discipline. [ADR-0030](../../decisions/adr-0030-durable-quarantine-and-lifecycle-coordinator.md)
decides a priority ladder + lifecycle-aware normalization, **narrowed by the
frame-critique to the rungs the existing signals can actually compute**.

## Goals

1. The heartbeat inbox schema gains a `priority` field (an ADR-0010
   `SCHEMA_VERSION` 2 -> 3 bump with the standard migration). Dispatch selection
   ranks by a ladder computed from signals that exist today —
   **security/data-loss > failing-CI > new work > idle** — where
   `security/data-loss` is a new `_classify_issue` severity gate over a
   configurable critical-label set. The `oh-my-cli` rungs **resume-interrupted**
   and **active-work** are deferred (no signal source; see Notes).
2. Before dispatch, a new defect is **normalized** into a structured record (title,
   ACs, security notes) rather than dispatched as free text — via jig's `bug-fix`
   entry when jig is co-installed, else a servo built-in record. servo must not
   hard-depend on jig's board (ADR-0011 boundary posture).
3. The coordinator skips `quarantined` findings (spec 024) and, **when a readable
   jig board is present**, findings whose mapped jig bug is claimed or in a
   servo-configured skip-status set; jig absent / board unreadable -> dispatch
   normally (fail-open).
4. Boundedness preserved: the whole-pass cost ceiling (ADR-0012) + `max-candidates`
   + readiness gate (spec 023) + quarantine skip (spec 024) remain the bounds.
   Ranking changes *order*, not *eligibility* or the number of dispatches.

## Vertical slices

- **025-01 — priority ranking + lifecycle-aware normalization:** the `priority`
  field + schema bump, ladder-based selection over computable rungs, jig-or-builtin
  normalization on dispatch, and the quarantined/claimed skip. See the slice file.

## Notes

- Priority is advisory *ordering* over the same candidate set; eligibility stays
  oracle/quarantine/readiness-gated — ranking changes order, not what is eligible.
- Deferred rungs: an interrupted dispatch is indistinguishable from any `tried`
  finding (no resumable-candidate class exists), and "active work" would require
  reading jig's board as a hard signal. Both are parked until a signal source
  exists — recorded here rather than faked.
- The live jig round-trip (a real `QUARANTINED` board, jig spec 105 ingest) is a
  deferred integration slice gated on jig 105 landing; 025-01 verifies against
  servo-owned board fixtures.
