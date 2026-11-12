---
status: DRAFT
kind: feature
dependencies: [042-01]
last_verified:
arch_review: true
frame_review: true
---

## Slice 042-02 — servo-driven serial dispatch

**Goal:** `campaign next <id>` is the episodic coordinator for the enforced
Claude Code mode: it reads the ledger, dispatches the next ready item as a
`loop.py` worker in its own worktree (serial, `max_parallel` 1), records the
loop's typed outcome line, reconciles a killed worker's reservation, batches
escalations by scope, and exits. There is no daemon and no resident coordinator
context.

**DoR:**
- 042-01 is DONE (plan + ledger + `campaign record`).
- The native loop runs on this host (Claude Code `loop.py`, already shipped).

**Acceptance Criteria:**

1. `campaign next <id>` dispatches at most one ready item (default
   `max_parallel` 1): it provisions a worktree for the item (reusing the
   heartbeat's `_dispatch_one` provisioning, `skills/heartbeat/heartbeat.py`),
   runs it under `loop.py` with the item's budget and `models` block, and
   returns when that worker halts.
   - A "ready" item is one with no live reservation and no terminal outcome in
     the ledger. Items dispatch in plan order.
   - When no item is ready, `campaign next` records nothing and exits 0 with a
     "nothing to dispatch" line.
2. On the worker's halt, `campaign next` records the loop's own typed outcome
   line via `campaign record` with `tier: servo` (never `self_reported`). The
   cost is taken from the loop's `state.json`, not re-derived.
3. Each `campaign next` records its own coordinator decision in the ledger
   (what it read, what it dispatched or escalated), so a campaign that fans out
   wrong is debuggable from the ledger alone (ADR-0049 coordinator decision
   log).
4. **Reservation reconciliation on wake:** a reservation whose `loop.py` run is
   neither live nor recorded is released, and the item is re-queued at its base
   sha, so a killed worker's budget is recovered. A reservation is held only
   while the item's run is live.
5. **Escalations batched by scope:** when the ledger shows items that plateaued
   at the ladder ceiling (spec 038-03), `campaign next` emits them grouped by
   escalation scope as one batch, not one message per item.
6. servo never merges and the runner does no git operations: landing stays with
   jig `slice-land --mode pr` or the host. `campaign next` dispatches, records
   and exits — a command, not a queue or a long-lived process.

**DoD:** ACs pass with tests (TDD, with dispatch exercised against a real git
repo — the heartbeat dispatch tests need a real repo, not a `git log` mock);
compliance + craft + arch reviews; reconciliation.

**Anti-horizontal-phasing check:** on Claude Code, a human points `campaign
next` at a plan and watches servo run each item under full per-node discipline,
one at a time, with the ledger showing typed outcomes and recovered budget — a
complete, enforced campaign with no host and no wrapper session.

## Assumptions

- **A2 (resource contention):** one worktree worker at a time doesn't contend
  on shared resources. `max_parallel` is 1 here, so this is harmless until
  042-05 raises the cap.
