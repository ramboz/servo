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
items. servo runs each one, or gates each one the host runs. Servo-driven and
wrapped workers run under the per-node discipline:
- oracle and budget;
- the plateau ladder (038-03);
- role placement (038-02).

Advisory workers get only an oracle check of claimed passes.

It records each item's typed outcome (spec 040) in a file ledger. Advisory
outcomes are marked `self_reported`. An episodic
`campaign next` step reads the ledger, decides and exits. There is no daemon.

Two modes:
- **servo-driven** (Claude Code, headless): servo runs up to `max_parallel`
  `loop.py` workers itself, default 1.
- **host-driven**: servo emits the plan plus one kickoff brief per item, and
  the host spawns the children.
  - The **verified-wrapped** tier: the worker runs its item under `loop.py`.
    `campaign record` accepts the item only if its run id and the worktree's
    content fingerprint (HEAD plus diff plus untracked contents) match the
    loop's halt state, and the loop started at the brief's base sha without
    `--allow-dirty`. Recording must happen before any commit, and the
    outcome is re-rendered from the loop's own state. The worker session's own spend
    stays outside every ceiling. On Copilot this tier comes after ADR-0048
    and spec 041.
  - The **advisory** tier enforces only verified passes and a ledger; its
    other fields are marked `self_reported`.

  See ADR-0049.

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

ADR-0049 A1–A5:
- adoption: a host coordinator actually calls servo;
- parallel worktrees don't contend on shared resources;
- the integration review works as an emitted brief;
- campaign items can be oracle-gated;
- worker compliance: wrapped workers stay inside `loop.py`.

## Decomposition (SPIDR)

- **Interface:** servo-driven serial mode on Claude Code comes first. It is
  enforced end to end, with no wrapper session and no concurrency. Advisory
  host-driven Copilot mode follows, then verified-wrapped Copilot after
  spec 041.
- **Data:** the plan and ledger come first, since every mode depends on them.
- **Rules:** parallelism and the integration review come last.

## Slices (sketch; ACs to sharpen after ADR-0049 is accepted)

- [042-01 — plan and ledger](slice-01-plan-and-ledger.md)
- 042-02 — servo-driven serial dispatch plus `campaign next`. The episodic
  coordinator runs each item under `loop.py`, records the loop's line, and
  batches escalations by scope.
- 042-03 — host-driven mode: kickoff briefs plus `campaign record`. The
  advisory tier gets oracle re-checks of passes and `self_reported` fields.
  The verified-wrapped tier checks the run id and content fingerprint, which
  needs `loop.py` to record that fingerprint at halt, and re-renders the
  outcome from the loop's state.
- 042-04 — servo-driven bounded parallel dispatch (`max_parallel`, aggregate
  ceiling with reservations).
- 042-05 — wave integration-review brief (one fresh-context review over the
  wave's diffs before PRs are published).

Dependencies: 038 (DONE when this lands), 040 (outcome line), 041 (Copilot
budget unit; needed for verified-wrapped Copilot workers).
