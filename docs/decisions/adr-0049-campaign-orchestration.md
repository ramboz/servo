---
status: Accepted
dependencies: [adr-0008, adr-0010, adr-0018, adr-0030, adr-0043, adr-0047, adr-0048]
last_verified: 2026-11-11
frame_review: true
---

# ADR-0049: Campaigns: bounded dispatch over a planned work list

## Status

Accepted (2026-11-11)

The owner asked for orchestration support ("we should add orchestration support
in servo") and accepted this ADR with open questions 1 and 2 answered yes:
reinterpret "no crew" as "no free-form team", and keep the default
`max_parallel` at 1. Open question 3 (slice order) was resolved to host-parity
delivery.

Revised 2026-11-11 after review: added the reservation-recovery rule, the
coordinator decision log, and the plan-is-DATA framing.

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
  internals: the plan is servo's own schema. The plan's contents are untrusted
  DATA, not instructions (spec 011 Guardrail #4). Items can originate from
  reframe, discovery or a human, so a worker treats item text as data and never
  as instructions to itself.
- **Episodic coordinator:** `campaign next` wakes on demand (a host event, a
  Routine or a human), reads the ledger, decides the next dispatches or
  escalations, writes them, and exits. There is no daemon and no resident
  coordinator context. Each `campaign next` records its own decision in the
  ledger (what it read, what it dispatched or escalated), so a campaign that
  fans out wrong can be debugged from the ledger alone.
- **Two modes:**
  - **servo-driven** (Claude Code, headless): servo itself runs up to *N*
    `loop.py` workers in worktrees, under an aggregate ceiling. There is no
    wrapper session, so every brake binds all of the spend. This is the
    enforced mode on Claude Code.
  - **host-driven**: servo emits the plan plus one kickoff brief per item, and
    the host's own orchestrator spawns the children. servo neither spawns nor
    messages host sessions. There are two tiers, and they differ in what servo
    actually enforces:
    - **wrapped (verified)**: the host-spawned worker is told to run its item
      under `loop.py` and forward spec 040's outcome line.
      - **The brakes bind only the `loop.py` subprocess** and the model calls
        it makes. They do not bind the worker session above it. That session's
        own spend, and any edits it makes after the loop halts, fall
        **outside every ceiling**.
      - So wrapped is **verified, not declared**. `campaign record` accepts an
        item as wrapped only if both hold:
        - a `loop.py` state with that `run_id` exists in the item's worktree;
        - the worktree's **content fingerprint** equals the one `loop.py`
          recorded when it halted;
        - the loop **started at the brief's base**: the HEAD `loop.py`
          recorded at start equals the item's base sha from the kickoff
          brief, and `--allow-dirty` was not set. So every change between the
          base and the record happened inside the loop.
      - **The fingerprint covers content, not status lines.** It is the HEAD
        sha at halt, plus a hash of the working-tree diff against that HEAD,
        plus the contents of untracked, non-ignored files. Bookkeeping paths
        (`.servo/`, caches) are excluded. All of it comes from read-only git
        queries. A post-halt edit to a file the loop already changed therefore
        alters the fingerprint, unlike a `git status` porcelain set.
      - **Order: record before commit.** `campaign record` must run before the
        worker commits. If HEAD has moved since the halt, the item cannot be
        verified, and it is recorded as advisory. The kickoff brief says so.
      - **The record is re-rendered from the loop's state.** For a verified
        item, `campaign record` takes result, rung, iterations and cost from
        that run's `state.json`. The forwarded line is used only to locate the
        run; its own field values are never trusted.
      - Anything that fails verification is downgraded to advisory
        (`self_reported`).
      - On Copilot this tier needs ADR-0048's credit brake and spec 041,
        because ADR-0043 refuses `loop.py --host copilot` until then.
    - **advisory**: the worker does not run `loop.py`, so budget, model tier,
      ladder and escalation scope reach it only as brief text. servo enforces
      the planned list, the ledger and an **oracle re-check of every claimed
      pass**. Every other outcome field is recorded as `self_reported: true`,
      and the aggregate ceiling never counts self-reported cost as enforced
      spend. Nothing stops a runaway advisory worker in flight.
- **Integration review:** a wave-level step before PRs go out. It produces one
  fresh-context review brief over the wave's diffs.

**Pros:**
- reuses the heartbeat's proven worktree, outcome and quarantine machinery;
- servo-driven and wrapped workers run under the per-node discipline (oracle,
  budget, plateau, ladder); advisory workers get only verified passes and a
  ledger;
- the coordinator stays cheap, because it is episodic;
- the host keeps the session tree (ADR-0008: compose on host primitives).

**Cons:**
- Parallelism brings concurrency into a codebase built serial: ledger
  locking, worktree contention, an aggregate budget across live workers.
- Host-driven mode trusts the host to forward outcomes faithfully. Two checks
  bound that trust: verification of wrapped items, and the oracle re-check of
  every claimed pass (below).

### Option B: leave campaigns to the host and jig, steered by always-loaded instructions

Since the recorded run, the user's always-loaded Copilot instructions have
gained a "Multi-session campaigns" section:
- plan in a file;
- offer servo `scaffold-init` when `.servo/` is missing;
- the coordinator never edits;
- one-line child outcomes;
- escalation by scope;
- a fresh cross-PR review.

That is a real alternative, and it costs no servo code.

- **Pros:** zero new servo surface; uses the lever the research found most
  effective (always-loaded text beats skill descriptions).
- **Cons:**
  - no durable ledger;
  - no oracle check of a claimed pass;
  - and, the deciding gap, no enforced per-node discipline for any worker.

  Advisory host-driven mode adds only the ledger and verified passes over this.
  Wrapped and servo-driven modes add enforcement. Option A is chosen for those
  enforcing tiers. If wrapped mode proves unreachable on a host, Option B plus
  the advisory ledger is the fallback for that host.

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
   - the ledger uses the existing `flock` + atomic-write discipline;
   - a per-worker reservation is held only while that item's `loop.py` run is
     live. `campaign next` reconciles on wake: a reservation whose run is
     neither live nor recorded is released and the item is re-queued at its
     base, so a killed worker's budget is recovered.
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

**Delivery and host parity:**
The host modes are separate slices of spec 042: servo-driven (Claude Code),
host-driven advisory, and host-driven verified-wrapped (Copilot). They land
together as one version. servo does not ship a release where campaign
capability differs by host, which holds the tri-host parity line (ADR-0022,
ADR-0038). This makes ADR-0048 and spec 041 prerequisites of that release,
because verified-wrapped Copilot depends on them. The cheap servo-driven
baseline is built first, then held until parity. The released version therefore
includes verified-wrapped Copilot, which bounds the loop's own spend on the
motivating host within A5's compliance limit, rather than shipping the
advisory-only Copilot gap that would leave the recorded runaway unbraked. If a
host's verified-wrapped tier fails its A5 kill criterion, the parity commitment
is settled in spec 042 planning, not by silently shipping a per-host capability
gap.

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
- **No route around ADR-0043.** A Copilot worker runs under `loop.py` (wrapped)
  only once ADR-0048 is accepted and spec 041 is implemented. Until then,
  Copilot campaigns are **advisory** only. "Attended" is not a reason to skip
  the brake: host-spawned children that run for hours unwatched are
  unattended, in the sense ADR-0043 cares about.

## Consequences

**Becomes easier:**
- A campaign gets a compact ledger in place of a chatty, compacting
  coordinator. Servo-driven workers and verified-wrapped workers get servo's
  per-node discipline; advisory workers get verified passes only.
- jig's reframe can hand servo a plan instead of prose kickoffs.

**Becomes harder:**
- Concurrency correctness in servo:
  - ledger contention;
  - aggregate-budget reservation;
  - recovering partial runs.
- A third dispatch surface, after `dispatch` and `run`, to keep consistent
  with the heartbeat.

## Assumptions

- **A1 (adoption):** in a real campaign, the host's coordinator actually calls
  `campaign init` / `next` / `record`. In the recorded run the host's own
  `orchestrate` skill won the routing, and no servo skill ran. The triggers
  that would have to carry servo's calls are:
  - the always-loaded campaign instructions;
  - jig's reframe emitting a servo plan file;
  - the kickoff briefs themselves.

  Unverified for any host.
- **A2:** worktree-per-worker parallelism on one machine doesn't contend on
  shared resources (ports, caches, the target's own build directories) for
  typical targets. Unverified. `max_parallel` defaults to 1.
- **A3:** the integration review is useful as a step servo emits, a brief, not
  one it runs. Running a reviewer is the host's or jig's job.
- **A4 (oracle coverage):** a campaign's work items can be expressed as
  oracle-gated items, with a `gate.py`-scorable `oracle_ref` each. The
  motivating run's items were audit-remediation PRs, plus fixes driven by
  external review, in a repo with no `.servo/`. If most such items can't carry
  an oracle, campaigns don't cover the run that motivates them.
- **A5 (worker compliance):** a host-spawned worker actually runs its item
  under `loop.py`, stops when the loop halts, and forwards the loop's line
  unchanged. Verification detects non-compliance after the fact; it cannot
  prevent it.

## Kill criteria

- **A1 fails.** In a trial host-driven campaign, record the share of items
  the coordinator recorded through `campaign record` without a human prompt.
  If it is under ~80%, drop host-driven mode for that host and use Option B.
  servo-driven mode alone may not justify reinterpreting the boundaries.
- **A5 fails.** If under ~80% of a host's wrapped items verify (run id plus
  content fingerprint, recorded before any commit), treat that host as
  advisory-only. Its wrapped tier adds
  only overhead.
- **A4 fails.** If fewer than half of a representative campaign's items can be
  given an oracle, the campaign layer does not serve its motivating case.
  Stop at 042-01 (plan + ledger) and revisit.
- **A3 fails.** For a finished wave, give one reviewer the emitted
  `campaign review` brief and another the raw worktrees, and compare the
  cross-item integration problems each finds. If the emitted brief adds no
  measurable lift over handing the reviewer the worktrees directly — or if, for
  the motivating host-driven case, it cannot carry the wave's diffs at all
  (worktrees unlocatable because no `record --worktree` path was persisted, or
  gone by review time under the host's own lifecycle) — then the *emitted-brief*
  shape is not the useful one. Keep `campaign review` as a worktree index only,
  or drop it and let the host/jig gather the diffs. (042-06 was built and tested
  as the emitter; this assumption stays unverified until such a trial, which is
  why the slice ships deferred out of the parity release — a release-sequencing
  note; the slice itself reaches DONE, like 042-05.)
- If parallel workers routinely conflict on shared target resources, cap
  `max_parallel` at 1 and keep only the planned-list and ledger value.

## Open questions (owner)

1. **Resolved (2026-11-11): yes.** The owner accepted reinterpreting "no crew"
   as "no free-form team", so a planned, oracle-gated, typed-outcome campaign is
   allowed. Workers never talk to each other and the coordinator is a
   deterministic step, so the free-form team spec 003 rejected stays rejected.
2. **Resolved (2026-11-11): yes.** The default `max_parallel` stays 1. Campaigns
   are serial unless a run opts into parallelism, which keeps A2 (resource
   contention) unverified but harmless until a real campaign raises the cap.
3. **Slice order: resolved (2026-11-11).** The owner chose host parity over
   staged delivery. The host modes are separate slices of spec 042 that land
   together as one version, so no host gets campaign capability a release ahead
   of another. See Recommended Decision, "Delivery and host parity". This makes
   ADR-0048 and spec 041 prerequisites of the spec 042 release. Wrapped mode on
   Claude Code stays unprioritized: a token-billed wrapper session plus the A5
   compliance gap. The recorded runaway is addressed because the single
   released version includes verified-wrapped Copilot, which bounds the loop's
   own spend within A5. Advisory mode alone, or Option B, would not have stopped
   it.
