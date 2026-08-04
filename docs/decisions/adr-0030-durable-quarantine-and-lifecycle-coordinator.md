---
status: Proposed
date: 2026-08-04
deciders: ramboz
supersedes:
superseded-by:
frame_review: true
last_verified: 2026-08-04
---

# ADR-0030: Durable cross-run quarantine and a lifecycle-aware coordinator

## Status

Proposed (2026-08-04)

> **Recorded, not yet built.** This ADR captures two coupled servo-side decisions
> for the long-horizon-autonomy bridge (the `oh-my-cli` follow-on). It anchors the
> DRAFT specs [024](../specs/024-durable-cross-run-quarantine/spec.md) (quarantine)
> and [025](../specs/025-lifecycle-aware-coordinator/spec.md) (coordinator), and is
> the servo peer of jig ADR-0050. No `loop.py` / `heartbeat.py` code ships with
> this record.

## Context

Two gaps block servo's heartbeat from being a safe, bounded, long-horizon
coordinator.

**1. Thrash is only bounded per-run.** `loop.py` persists an
`oracle_score_history` plateau signal, but only under
`<target>/.servo/runs/<run-id>/state.json`. Each heartbeat tick starts a fresh
run-id, so the same doomed finding is re-dispatched every tick forever — the
long-horizon thrash failure `oh-my-cli` bounds with "third identical failure →
quarantine; retry requires new diagnostic evidence." The plateau knowledge dies
with the run.

**2. The coordinator is FIFO and lifecycle-blind.** `heartbeat.py`
([ADR-0010](adr-0010-triage-inbox-schema.md),
[ADR-0012](adr-0012-heartbeat-whole-pass-cost-ceiling.md)) discovers signals and
dispatches actionable findings, but its inbox has no priority field — it is pure
arrival order — and it dispatches raw finding text rather than a normalized work
item. `oh-my-cli` ran on a priority ladder (resume interrupted > security/data-loss
> failing CI > active work > new work > idle) and normalized every issue before
touching code. The signals servo needs already exist in `_classify_ci` /
`_classify_issue`; they are just not ranked or normalized.

Both live in the same dispatch path, so they are decided together. This ADR is the
servo peer of jig ADR-0050 (which adds the `QUARANTINED` terminal + `attempts`
counter to the jig bug record); the two sides share a file across the ADR-0022 /
[ADR-0011](adr-0011-host-native-phase-hints.md) filesystem boundary, never code.

## Decision

**A. Durable cross-run quarantine.** On an `oracle_plateau` (or a repeated
identical terminal failure), `loop.py` writes a **cross-run** record to
`<target>/.servo/quarantine/<fingerprint>.json`, keyed by a stable per-finding
failure fingerprint (finding id + normalized failure signature). `heartbeat.py`'s
dispatch-candidate filter (today "actionable + open") gains a **quarantine skip**:
a fingerprinted finding with a live quarantine record is recorded `skipped`, not
dispatched, so it stops consuming a tick every cycle. A quarantine record clears
only on **new diagnostic evidence** (a changed evidence pointer) — the servo-side
mirror of jig ADR-0050's release rule.

**B. Lifecycle-aware coordinator.** The heartbeat inbox schema gains a
`priority` / `severity` field, and dispatch selection ranks by an `oh-my-cli`-style
ladder computed from the existing `_classify_ci` / `_classify_issue` signals,
instead of FIFO. Before dispatch, the coordinator **normalizes** a new defect
through jig's `bug-fix` entry when jig is co-installed (a structured record with
ACs + security notes, read over the filesystem), rather than dispatching free
text; it skips `QUARANTINED` / claimed items by reading jig's bug board.

**C. Attest-only handshake.** When servo quarantines a finding that maps to a jig
bug, jig advances that bug to `QUARANTINED` **attest-only** (jig ADR-0050) — jig
records *that* servo plateaued and *where* the evidence lives; it never re-runs
the oracle. servo defines and owns the fingerprint; jig only reads the pointer.

**Boundedness.** Whole-pass cost ceiling (ADR-0012) + `max-candidates` +
autonomy-readiness (ADR-0029) + quarantine-skip are the four bounds that make a
long unattended run safe. "Never complete" stays the heartbeat's existing
idle-not-terminal posture.

## Consequences

### Positive

- A plateaued finding is attempted a bounded number of times, then durably
  quarantined — thrash cannot survive across ticks.
- The coordinator spends each tick on the highest-value work and dispatches
  normalized items, not raw text.
- servo and jig share an anti-thrash boundary with no code coupling; the human
  reviews a quarantine queue instead of every tick.

### Negative

- New durable state (`.servo/quarantine/`) and a fingerprint contract to keep
  stable across runs.
- Heartbeat gains ranking + normalization logic and a soft dependency on jig's
  bug board when co-installed (must degrade gracefully when jig is absent).

### Neutral

- Reuses the existing plateau signal and `_classify_*` outputs; no new discovery
  machinery.
- Priority ladder is advisory ordering over the same candidate set — it changes
  *order*, not *what is eligible* (eligibility stays oracle/quarantine-gated).

## Alternatives considered

- **Keep plateau per-run; rely on the cost ceiling to bound thrash.** Rejected:
  the ceiling bounds a *pass*, not repeated re-selection of the same doomed
  finding across passes — the finding still burns a slice of every tick.
- **A separate quarantine daemon / store outside heartbeat.** Rejected as
  premature; the dispatch filter is the natural home and the record is a plain
  file (ADR-0011 posture). Revisit only with a third consumer.
- **Full priority queue with preemption.** Rejected as over-engineered for a
  tick-based coordinator; a computed rank over the candidate set is sufficient.
- **Normalize inside servo instead of via jig's `bug-fix`.** Rejected when jig is
  present: it already owns normalized defect records; duplicating that in servo
  would fork the lifecycle. Servo ships a minimal built-in only for the
  jig-absent case.

## Verification

- A finding hitting the plateau threshold writes a `.servo/quarantine/<fp>.json`;
  a subsequent tick records it `skipped` (witnessed no re-dispatch); clearing
  requires a changed evidence pointer.
- Dispatch ordering fixtures: a security/data-loss finding outranks new work; a
  resume-interrupted item outranks a failing-CI item.
- Normalization: a new defect is dispatched as a structured jig bug record (ACs
  present) when jig is co-installed; degrades to a built-in record when absent.
- Attest-only: the jig-facing path never invokes a scorer; jig cites the servo
  evidence pointer (cross-checked against jig ADR-0050's spec 105 fixtures).

## References

- [Spec 024 — durable-cross-run-quarantine](../specs/024-durable-cross-run-quarantine/spec.md)
- [Spec 025 — lifecycle-aware-coordinator](../specs/025-lifecycle-aware-coordinator/spec.md)
- [ADR-0010 — triage inbox schema](adr-0010-triage-inbox-schema.md)
- [ADR-0012 — heartbeat whole-pass cost ceiling](adr-0012-heartbeat-whole-pass-cost-ceiling.md)
- [ADR-0011 — host-native phase hints stay advisory](adr-0011-host-native-phase-hints.md)
- jig ADR-0050 — durable failure-quarantine + attest-only handshake (peer, `ramboz/jig`)
