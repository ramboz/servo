---
status: Accepted
date: 2026-08-04
deciders: ramboz
supersedes:
superseded-by:
frame_review: true
last_verified: 2026-08-06
---

# ADR-0030: Durable cross-run quarantine and a lifecycle-aware coordinator

## Status

Accepted (2026-08-06)

> **Recorded, not yet built.** This ADR captures two coupled servo-side decisions
> for the long-horizon-autonomy bridge (the `oh-my-cli` follow-on). It anchors the
> DRAFT specs [024](../specs/024-durable-cross-run-quarantine/spec.md) (quarantine)
> and [025](../specs/025-lifecycle-aware-coordinator/spec.md) (coordinator), and is
> the servo peer of jig ADR-0050. No `loop.py` / `heartbeat.py` code ships with
> this record.

## Context

Two gaps block servo's heartbeat from being a safe, bounded, long-horizon
coordinator.

**1. A plateaued finding is terminally parked, not durably legible, and can
never be retried on new evidence.** `loop.py` persists an `oracle_score_history`
plateau signal, but only under `<target>/.servo/runs/<run-id>/state.json`, and
that plateau knowledge dies with the run. On the heartbeat side, ADR-0010's
lifecycle already prevents *unbounded* re-dispatch: a dispatched finding goes
`open → tried`/`passed` and is **sticky — never auto-reset to `open`**, and
`_select_candidates` selects only `open` findings, so a doomed finding is
attempted exactly once and then sits `tried` forever. That bounds thrash, but at
the cost of two gaps `oh-my-cli` closes with "third identical failure →
quarantine; retry requires new diagnostic evidence": (a) the parked finding is
indistinguishable from any other one-shot `tried` failure — a reviewer/jig
cannot see *that* it plateaued or *where* the evidence lives; and (b) there is no
**principled, evidence-gated re-admission** path — the finding can never come
back for another attempt even when genuinely new diagnostic evidence appears,
and any future re-dispatch capability would have no thrash guard. The durable
quarantine record is the legibility layer *and* the guard that makes a bounded
`→ open` re-admission safe.

> **Frame-critique correction (2026-08-06).** An earlier draft of this ADR framed
> the gap as "the same doomed finding is re-dispatched every tick forever." That
> is false against the shipped code (sticky-`tried` already bounds it — see the
> Frame-critique section below). The decision is re-scoped accordingly: quarantine
> is the durable-legibility + evidence-gated-re-admission layer over the existing
> one-attempt lifecycle, not a bound on a cross-tick re-dispatch that does not
> exist today.

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

**A. Durable cross-run quarantine (written by `heartbeat.py`, keyed by
`finding_id`).** `heartbeat.py` — the component that owns the `finding_id` and the
real target path — writes the durable record; `loop.py` stays unchanged and
target-scoped. In a heartbeat dispatch, `loop.py` runs against an *ephemeral
worktree* and has no `finding_id`, so it cannot be the writer (frame-critique
FLAW 1). Instead, `run_dispatch` reads the dispatched loop's summary — which
already carries `terminal_reason` — and, on `oracle_plateau`, writes a **cross-run**
record to `<target>/.servo/quarantine/<finding_id>.json` (the file key **is** the
stable, content-derived `finding_id`; the run-varying "failure signature" is a
*stored field*, not part of the key — FLAW 6), and sets the finding's inbox
status to a new terminal value **`quarantined`** (distinct from `tried`, so the
park is legible). `_select_candidates` stays `open`-only, so a quarantined finding
is never re-dispatched — the anti-thrash property. `quarantine/` is added to
`_NON_PROVISIONED_SERVO_DIRS` so it is never copied into a dispatch worktree, and
the skip is always evaluated against the **real** target's `.servo/quarantine/`
(FLAW 8).

**Evidence-gated re-admission (FLAW 4).** The record stores an `evidence_pointer`
= a hash over the finding's **stable diagnostic evidence projection** (the
`evidence` dict minus known-volatile keys — `run_url` and any `*_url` / `*_at`
value — so a mechanical CI re-run does *not* change it). On a later discover pass,
a `quarantined` finding whose current `evidence_pointer` **differs** from the
recorded one is **re-admitted** (`quarantined → open`, the quarantine file
removed) — the single principled `→ open` reset, safe because unchanged evidence
keeps it parked. An unchanged pointer keeps it `quarantined` (the witnessed
no-redispatch). Deleting the record is also a release (the record *is* the
quarantine): a `quarantined` finding with no live record re-admits, which is the
human release gesture and self-heals a torn record; correspondingly a failed
record write falls back to `tried` rather than parking record-less.

> **v1 disclosure (frame-critique / arch-review).** For *today's* actionable
> sources the stable evidence projection equals the finding_id's own inputs (CI:
> workflow + branch; issue: number), so the pointer does **not** change via
> natural discover — **automatic** evidence-gated re-admission is a *forward hook*
> that fires for essentially no real finding in v1. The real v1 release valve is
> the **human quarantine queue**: a reviewer deletes the record to re-admit
> (ADR-0030 Consequences). The automatic path activates for free once a source
> grows a diagnostic evidence field that varies independently of its identity.
> This is the servo-side mirror of jig ADR-0050's "retry requires new diagnostic
> evidence."

**B. Lifecycle-aware coordinator (ladder narrowed to computable rungs).** The
heartbeat inbox schema gains a `priority` field — an ADR-0010 **`SCHEMA_VERSION`
2 → 3 bump** with the standard migration (discover rebuilds a `< 3` inbox on
write; `status`/`dispatch` warn-lower / refuse-higher) (FLAW 7). Dispatch
selection ranks by a ladder **computed only from signals that exist today**
(FLAW 3): **security/data-loss > failing-CI > new work > idle**, where
`security/data-loss` is a *new* `_classify_issue` severity gate over a
configurable critical-label set, `failing-CI` is `_classify_ci`'s default-branch
verdict, and `new work` is any other open+actionable finding. The `oh-my-cli`
rungs **resume-interrupted** and **active-work** are **deferred** — no signal
source exists (an interrupted dispatch is indistinguishable from any `tried`
finding; "active" would require jig's board). Ranking changes *order only*;
eligibility stays oracle/quarantine/readiness-gated, and `max-candidates` + the
whole-pass ceiling still bound the pass. Before dispatch, the coordinator
**normalizes** a new defect into a structured record (title, ACs, security
notes) rather than dispatching free text — via jig's `bug-fix` entry when jig is
co-installed, else a servo built-in record; it skips items whose mapped jig bug
is claimed or in a servo-configured skip-status set **when a readable jig board
is present** (FLAW 5).

**C. Attest-only handshake (servo-owned schema, fail-open).** servo **defines and
owns** the quarantine-record schema and validates it against a **servo-owned
fixture** — jig ADR-0050 / jig spec 105 (the `QUARANTINED` bug status + the
attest-only ingest) are **not landed** and are not in servo's DoD path (FLAW 5).
The record exposes exactly the projection a future jig reader needs (the
`finding_id ↔ bug` mapping key + the evidence location) so that, once jig 105
lands, jig can advance a mapped bug to `QUARANTINED` **attest-only** — recording
*that* servo plateaued and *where* the evidence lives, never re-running the
oracle. servo never depends on jig internals and degrades to normal operation
when jig is absent or its board is unreadable (ADR-0011). The live jig round-trip
(024 AC4 against a real spec-105 fixture; 025 AC3 against a real `QUARANTINED`
board) ships as a **separate later integration slice gated on jig 105 landing**.

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

- On a dispatched loop whose summary carries `terminal_reason == oracle_plateau`,
  `heartbeat.py` writes `.servo/quarantine/<finding_id>.json` and sets the
  finding `quarantined`; the file key is identical across two independent run-ids
  for the same finding (keyed by the content-derived `finding_id`).
- A subsequent discover/dispatch tick does **not** re-select a `quarantined`
  finding with an unchanged `evidence_pointer` (witnessed no re-dispatch), while
  `open` findings still dispatch; a changed `evidence_pointer` re-admits it
  (`quarantined → open`, record removed).
- Dispatch ordering fixtures (computable rungs only): a security/data-loss issue
  (critical-label gate) outranks a plain new-work finding; a default-branch CI
  failure outranks new work.
- Normalization: a new defect is dispatched as a structured record (ACs present)
  — a jig bug record when jig is co-installed, a servo built-in record when
  absent — never raw free text.
- Servo-owned attest legibility: the quarantine record validates against servo's
  own schema fixture and exposes the `finding_id ↔ bug` + evidence-location
  projection; no scorer is invoked on any jig-facing path. (The live jig
  spec-105 round-trip is a deferred integration slice, not in this DoD.)

## Frame-critique (2026-08-06)

`frame_review: true` — an adversarial frame-critique ran before acceptance and
surfaced eight framing flaws; the Decision above is the reframe. Recorded for
auditability:

| # | Sev | Flaw | Resolution |
|---|-----|------|------------|
| 1 | CRIT | `loop.py` cannot write a `finding_id`-keyed record at the real target — in dispatch it runs against an ephemeral worktree and has no `finding_id`. | **`heartbeat.py` writes** the record from the loop summary's `terminal_reason`; `loop.py` unchanged. |
| 2 | CRIT | The "re-dispatched every tick forever" thrash does not exist — ADR-0010's sticky-`tried` lifecycle already bounds a finding to one attempt. | Re-scoped: quarantine is a durable-legibility + **evidence-gated re-admission** layer, not a cross-tick re-dispatch bound. Context §1 corrected. |
| 3 | HIGH | 3 of 6 ladder rungs (security/data-loss, resume-interrupted, active-work) have no signal source. | Ladder narrowed to **security/data-loss (new label gate) > failing-CI > new work > idle**; the two unsourced rungs deferred. |
| 4 | HIGH | "changed evidence pointer" was undefined; the only evidence field (`run_url`) mutates on every mechanical re-run → over-releases. | `evidence_pointer` hashes the **stable evidence projection** (drops `run_url` / `*_url` / `*_at`); re-run ≠ new evidence. |
| 5 | HIGH | 024 AC4 / 025 AC3 verified against jig spec 105 / a `QUARANTINED` board that are **not landed**. | servo owns the schema + fixture, **fail-open** when jig absent; the live jig round-trip is a deferred integration slice. |
| 6 | MED | Fingerprint field set ("finding id + failure signature") is self-defeating — a signature from run output is run-varying. | The **key is `finding_id`** alone; `failure_signature` is a stored field, not part of the key. |
| 7 | MED | Adding `priority` is an ADR-0010 schema change the specs did not version/migrate. | Explicit `SCHEMA_VERSION` **2 → 3** bump + standard migration in 025-01. |
| 8 | LOW | `quarantine/` not excluded from worktree provisioning → stale copies. | Add `quarantine` to `_NON_PROVISIONED_SERVO_DIRS`; skip reads the real target. |

Intent preserved on every count; the contracts are now self-contained and
testable against the shipped code without jig 105.

## References

- [Spec 024 — durable-cross-run-quarantine](../specs/024-durable-cross-run-quarantine/spec.md)
- [Spec 025 — lifecycle-aware-coordinator](../specs/025-lifecycle-aware-coordinator/spec.md)
- [ADR-0010 — triage inbox schema](adr-0010-triage-inbox-schema.md)
- [ADR-0012 — heartbeat whole-pass cost ceiling](adr-0012-heartbeat-whole-pass-cost-ceiling.md)
- [ADR-0011 — host-native phase hints stay advisory](adr-0011-host-native-phase-hints.md)
- jig ADR-0050 — durable failure-quarantine + attest-only handshake (peer, `ramboz/jig`)
