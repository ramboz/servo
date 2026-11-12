---
status: DRAFT
skill: heartbeat
use_cases: []
---

# Spec 042: Campaign orchestration

> **Status: DRAFT, slices authored.**
> [ADR-0049](../../decisions/adr-0049-campaign-orchestration.md) was accepted
> 2026-11-11, so the slices below are firm. Prerequisites 038 and 041 are DONE;
> the one remaining prerequisite is the typed outcome line (040-01), which
> 042-01 depends on. Build order: **040-01 → 042-01 → 042-02 → 042-03 →
> 042-04**, then the deferred 042-05 / 042-06.

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
- **Spec 038** adds per-iteration accounting, role placement and the ladder
  (DONE). Spec 040 drafts the typed outcome line (040-01, DRAFT — a prerequisite
  of the ledger). Spec 041 shipped the Copilot credit budget (ADR-0048, DONE),
  so a Copilot worker can now run under `loop.py` for the verified-wrapped tier.
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

- **Data:** the plan and ledger (042-01) come first, since every mode depends
  on them.
- **Interface:** the three host modes are separate slices (ADR-0049) —
  servo-driven serial (042-02, the enforced Claude Code baseline), host-driven
  advisory (042-03), then host-driven verified-wrapped (042-04, which needs
  spec 041). They land together as one version (host parity, below).
- **Rules:** bounded parallelism (042-05) and the integration review (042-06)
  come last and are deferred out of the parity release.

## Slices

**Parity release bundle — these land together as one version.** ADR-0049
commits to host parity (ADR-0022, ADR-0038): servo ships no release where
campaign capability differs by host. The three host modes are separate slices
that land as one version, so verified-wrapped Copilot ships with the rest
rather than leaving the recorded runaway unbraked.

- **(prerequisite) [040-01 — outcome line](../040-servo-wrapped-worker-outcome/slice-01-outcome-line.md)**
  — `loop.py --outcome-line` emits the typed `servo_outcome` record the ledger
  stores and host workers forward. Built first.
- [042-01 — plan and ledger](slice-01-plan-and-ledger.md) — `campaign
  init/record/status` over `plan.json` + `ledger.jsonl`. The A4 checkpoint.
- [042-02 — servo-driven serial dispatch](slice-02-servo-driven-serial-dispatch.md)
  — the episodic `campaign next` coordinator runs each item under `loop.py`,
  serial (`max_parallel` 1), records the loop's line, reconciles reservations
  and batches escalations by scope. The enforced Claude Code baseline.
- [042-03 — host-driven advisory](slice-03-host-driven-advisory.md) — kickoff
  briefs plus `campaign record`, with an oracle re-check of every claimed pass
  and `self_reported` on every other field.
- [042-04 — host-driven verified-wrapped](slice-04-host-driven-verified-wrapped.md)
  — `loop.py` records a content fingerprint at halt; `campaign record` verifies
  run id + fingerprint + base sha (record-before-commit) and re-renders the
  outcome from the loop's state. Needs spec 041 (DONE).

**Deferred out of the parity release** (ship in a later version):

- [042-05 — bounded parallel dispatch](slice-05-bounded-parallel-dispatch.md) —
  `max_parallel` > 1 with an aggregate ceiling and per-worker reservations.
  `max_parallel` defaults to 1 and A2 (resource contention) is unverified, so
  this is release-neutral for parity.
- [042-06 — wave integration-review brief](slice-06-wave-integration-review.md)
  — one fresh-context review brief over the wave's diffs before PRs publish.
  Host-agnostic.

Dependencies: 038 (DONE), 040-01 (outcome line — prerequisite), 041 (Copilot
budget unit, DONE; needed for verified-wrapped Copilot workers).
