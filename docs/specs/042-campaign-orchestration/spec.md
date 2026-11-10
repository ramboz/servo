---
status: DRAFT
skill: heartbeat
use_cases: []
---

# Spec 042: Campaign orchestration

> **Status: DRAFT, scope capture.** Gated on the owner explicitly accepting
> [ADR-0049](../../decisions/adr-0049-campaign-orchestration.md), which stays
> Proposed until then. No slice is implemented before that.

## Overview

A **campaign** is heartbeat-style dispatch over a **planned** work list, not a
free-form crew (ADR-0049). The plan supplies independent, oracle-gated work
items. servo runs each one, or gates each one the host runs, under its
per-node discipline:
- oracle and budget;
- the plateau ladder (038-03);
- role placement (038-02).

It records each item's typed outcome (spec 040) in a file ledger. Advisory
outcomes are marked `self_reported`. An episodic
`campaign next` step reads the ledger, decides and exits. There is no daemon.

Two modes:
- **servo-driven** (Claude Code, headless): servo runs up to `max_parallel`
  `loop.py` workers itself, default 1.
- **host-driven**: servo emits the plan plus one kickoff brief per item, and
  the host spawns the children. The **wrapped** tier runs each worker under
  `loop.py`, which enforces per-node discipline and reports the real outcome
  line; it works on Claude Code hosts today, and on Copilot after ADR-0048 and
  spec 041. The **advisory** tier enforces only verified passes and a ledger;
  its other fields are marked `self_reported`. See ADR-0049.

### Grounded starting point

- **What can be reused from the heartbeat (spec 011):**
  - the worktree per item and its provisioning (`_dispatch_one`,
    `skills/heartbeat/heartbeat.py:2420-2510`);
  - the locked, atomic inbox ledger (`_inbox_lock`, `_atomic_write`);
  - whole-pass ceilings (ADR-0012), quarantine (ADR-0030), and the outcome
    shape (`_outcome_from_summary`).

  Dispatch is serial (`heartbeat.py:53`).
- **Spec 038** adds per-iteration accounting, role placement and the ladder.
  Spec 040 drafts the typed outcome line. Spec 041 drafts the Copilot credit
  budget (ADR-0048, Proposed).
- **Boundary lines and their treatment:** listed in ADR-0049 with sources.
  They are: "serial in v1" (superseded for campaigns only), "no crew"
  (reinterpreted) and "not a queue or long-lived process" (kept).

### Boundaries

- servo never merges, and the runner does no git operations. Landing goes
  through jig `slice-land --mode pr` or the host.
- The oracle is authoritative. In host-driven mode a host's claim of "passed"
  is re-checked with `gate.py` before it enters the ledger.
- servo doesn't decide what to build. No merge-conflict AI, no cloud fan-out.
  servo never depends on jig: the plan is servo's own schema.

## Assumptions

ADR-0049 A1–A4:
- adoption: a host coordinator actually calls servo;
- parallel worktrees don't contend on shared resources;
- the integration review works as an emitted brief;
- campaign items can be oracle-gated.

## Decomposition (SPIDR)

- **Interface:** host-driven *wrapped* mode on Claude Code hosts comes
  first. It is enforced, and it needs no concurrency in servo. Advisory
  Copilot mode follows, then wrapped Copilot after spec 041.
- **Data:** the plan and ledger come first, since every mode depends on them.
- **Rules:** parallelism and the integration review come last.

## Slices (sketch; ACs to sharpen after ADR-0049 is accepted)

- [042-01 — plan and ledger](slice-01-plan-and-ledger.md)
- 042-02 — kickoff briefs + `campaign record` (host-driven mode; uses spec
  040's outcome line; re-checks passes with the oracle).
- 042-03 — `campaign next` (episodic coordinator: reads the ledger, picks the
  next items, batches escalations by scope).
- 042-04 — servo-driven bounded parallel dispatch (`max_parallel`, aggregate
  ceiling with reservations).
- 042-05 — wave integration-review brief (one fresh-context review over the
  wave's diffs before PRs are published).

Dependencies: 038 (DONE when this lands), 040 (outcome line), 041 (Copilot
budget unit, only for unattended Copilot workers).
