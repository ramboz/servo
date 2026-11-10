---
status: Proposed
dependencies: [adr-0008, adr-0010, adr-0018, adr-0030, adr-0043, adr-0047, adr-0048]
last_verified:
frame_review: true
---

# ADR-0049: Campaigns: bounded dispatch over a planned work list

## Status

Proposed (2026-11-10). **Owner acceptance required.** The owner asked for
orchestration support ("we should add orchestration support in servo"). That
authorizes drafting this ADR, not accepting it. No campaign slice is
implemented until the owner explicitly accepts this text.

## Context

In a recorded two-day multi-session campaign on Copilot CLI, a coordinator
spawned 15 worker sessions to remediate a two-repo audit. servo never ran.
Four causes:

1. Its loop is refused on Copilot (ADR-0043; ADR-0048 proposes the fix).
2. The target repo had no `.servo/` oracle.
3. The host's built-in `orchestrate` skill won the routing ("one session ≈ one
   branch ≈ one PR").
4. Neither jig nor servo has a campaign layer, so the host filled the gap.

The run showed what goes wrong without per-node discipline:
- a runaway worker (1,383 calls, 59 compactions);
- a resident coordinator with 85 lossy compactions and 252 edits of its own;
- 646 chatty coordinator messages;
- external review forcing an 11-session fix wave that an earlier
  integration review might have caught.

servo already has most of the campaign machinery in the heartbeat (spec 011):
- a ranked work list;
- one worktree per item;
- `loop.py` under a per-item and whole-pass ceiling;
- typed outcomes recorded in a locked, atomically written ledger;
- quarantine (ADR-0030).

Spec 038 adds per-iteration accounting, role placement and the escalation
ladder. What is missing is a **planned** work list, bounded **parallelism**,
an **episodic coordinator** step and a host-driven mode.

Three boundary lines stand in the way. Each is cited and treated explicitly
below:

| Line | Source |
|---|---|
| Dispatch is "serial in v1" | `skills/heartbeat/heartbeat.py:53`; docs/architecture.md (heartbeat dispatch) |
| "no `/servo:crew` skill ever" | spec 003 Non-goals (`docs/specs/003-agent-loop/spec.md:39`). It points to an architecture.md "Why no crew skill" section that does not exist (dangling reference) |
| "not a cron daemon, a queue, or a long-lived process" | spec 011 (`docs/specs/011-heartbeat/spec.md:197-198`) |

## Decision Options Considered

### Option A (recommended): a campaign is heartbeat-style dispatch over a planned work list

- **Plan artifact:** `.servo/campaigns/<id>/` holds a plan (work items, each
  with its oracle reference, budget and `models` block, the spec 038 schema)
  and an append-only, lock-guarded ledger of typed outcomes (spec 040's
  outcome line).
- **Source of the work list:** a plan file that servo reads. jig's reframe
  manifest or spec slices can produce one, but servo never reads jig
  internals: the plan is servo's own schema.
- **Episodic coordinator:** `campaign next` wakes on demand (a host event, a
  Routine or a human), reads the ledger, decides the next dispatches or
  escalations, writes them, and exits. There is no daemon and no resident
  coordinator context.
- **Two modes:**
  - **servo-driven** (Claude Code, headless): servo runs up to *N* `loop.py`
    workers in worktrees, under an aggregate ceiling.
  - **host-driven** (Copilot, attended): servo emits the plan plus one kickoff
    brief per item, with the worker contract built in (oracle command,
    budget, model tier, one-line outcome format, escalation scope). The
    host's own orchestrator spawns the children, and servo gates their typed
    outcomes into the ledger. servo neither spawns nor messages host
    sessions.
- **Integration review:** a wave-level step before PRs go out. It produces one
  fresh-context review brief over the wave's diffs.

**Pros:**
- reuses the heartbeat's proven worktree, outcome and quarantine machinery;
- the per-node discipline (oracle, budget, plateau, ladder) applies to every
  worker;
- the coordinator stays cheap, because it is episodic;
- the host keeps the session tree (ADR-0008: compose on host primitives).

**Cons:**
- Parallelism brings concurrency into a codebase built serial: ledger
  locking, worktree contention, an aggregate budget across live workers.
- Host-driven mode trusts the host to forward outcomes faithfully. The oracle
  re-check (below) bounds that trust.

### Option B: leave campaigns entirely to the host and jig

- **Cons:** this is the recorded status quo. Workers ran without servo's
  discipline, and the coordinator was expensive and lossy. Rejected.

### Option C: a free-form `/servo:crew` (agents negotiating work among themselves)

- **Cons:** this is the thing spec 003 rules out, for good reason. There is no
  oracle-anchored unit of work and no typed outcome. Rejected.

## Recommended Decision

Option A. The three boundary lines are handled as follows:

1. **"serial in v1": superseded for campaigns only.** Heartbeat dispatch
   stays serial. A campaign may run up to `max_parallel` workers, default 1:
   - each worker is in its own worktree;
   - the campaign has an aggregate cost ceiling, enforced before each
     dispatch on Σ recorded spend + Σ reserved per-worker ceilings of live
     workers;
   - the ledger uses the existing `flock` + atomic-write discipline.
2. **"no `/servo:crew` skill ever": kept, reinterpreted.** There is still no
   free-form team. A campaign is a planned list of independent, oracle-gated
   work items with typed outcomes:
   - workers never talk to each other;
   - the coordinator is a deterministic step plus a human or host decision,
     not an agent conversation.

   The dangling "Why no crew skill" reference in spec 003 is fixed to point
   here.
3. **"not a queue or a long-lived process": kept.** The ledger is a file. The
   coordinator is a command that exits. Waking it is the trigger's job: a
   host, a Routine or a human.

**Kept unchanged:**
- servo never merges, and the runner does no git operations. Landing goes
  through jig `slice-land --mode pr` or the host.
- The oracle is authoritative. In host-driven mode servo re-runs the item's
  oracle (`gate.py`) on the worker's worktree before it accepts a "passed"
  outcome into the ledger. A host's claim alone is never a pass.
- servo does not decide what to build. The plan supplies the work list.
- No merge-conflict AI. No cloud fan-out: workers are local worktrees, or
  host sessions the host spawns.
- servo never depends on jig.
- Unattended Copilot workers stay refused until ADR-0048 is accepted and spec
  041 is implemented. Host-driven mode on Copilot is attended, so it is not
  blocked by that.

## Consequences

**Becomes easier:**
- A host-orchestrated campaign gets servo's per-node discipline and a compact
  ledger in place of a chatty, compacting coordinator.
- jig's reframe can hand servo a plan instead of prose kickoffs.

**Becomes harder:**
- Concurrency correctness in servo:
  - ledger contention;
  - aggregate-budget reservation;
  - recovering partial runs.
- A third dispatch surface, after `dispatch` and `run`, to keep consistent
  with the heartbeat.

## Assumptions

- **A1:** host-driven mode can be made to work. A host coordinator, such as
  Copilot's `orchestrate` skill or a Claude Code session, forwards a worker's
  one-line outcome and worktree path to `campaign record`. Unverified for any
  host. This decides whether that mode is servo-gated or only advisory.
- **A2:** worktree-per-worker parallelism on one machine doesn't contend on
  shared resources (ports, caches, the target's own build directories) for
  typical targets. Unverified. `max_parallel` defaults to 1.
- **A3:** the integration review is useful as a step servo emits, a brief, not
  one it runs. Running a reviewer is the host's or jig's job.

## Kill criteria

- If A1 fails, meaning no host can forward outcomes without servo spawning
  sessions itself, drop host-driven mode. servo-driven mode alone may not
  justify reinterpreting the boundaries; revisit Option B.
- If parallel workers routinely conflict on shared target resources, cap
  `max_parallel` at 1 and keep only the planned-list and ledger value.

## Open questions (owner)

1. Accept reinterpreting "no crew" as "no free-form team", so that a planned,
   oracle-gated, typed-outcome campaign is allowed?
2. Should the default `max_parallel` stay 1, which is serial and gives
   parallelism by opt-in only?
3. Should host-driven mode ship first? It is the mode that would have changed
   the recorded Copilot run.
