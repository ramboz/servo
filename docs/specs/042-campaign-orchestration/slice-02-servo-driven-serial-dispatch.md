---
status: DONE
kind: feature
dependencies: [042-01]
last_verified: 2026-11-12
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

### Deviation log (after reconciliation)

The original ACs are preserved above. Review rounds:
- **Round 1:** compliance PASS, arch PASS; **craft needs-changes** (five nits, no
  blockers); **frame-critique needs-changes** (three blockers + two nits).
- **Round 2:** **craft PASS** (all five nits fixed; `_record_loop_outcome` refactor
  confirmed), **frame-critique PASS** (all three blockers resolved + both nits
  closed). Round-2 left three craft nits and one frame nit, all addressed before
  landing: the append-then-unlink re-spend window (frame), the stale harness comment,
  the orphan-promotion breadcrumb, and a non-git-target guard test (craft).

Load-bearing choices made during implementation:

1. **`campaign next` is a new subcommand of `campaign.py`**, not a new module — it
   extends 042-01's CLI (`init`/`record`/`status`). The surface is `campaign next`.
2. **Heartbeat provisioning is reused via a dynamic `spec_from_file_location` load of
   `heartbeat.py`**, never a static import (the dependency-free invariant;
   `DependencyFreeTests`' AST scan forbids `import heartbeat`). `next` reuses the
   fine-grained helpers (`_is_git_work_tree`, `_remove_worktree_if_present`,
   `_provision_oracle`, `_git`, `_format_ceiling`) rather than calling `_dispatch_one`
   wholesale: `_dispatch_one` is finding-shaped (builds a finding/jig prompt), returns
   heartbeat's ADR-0010 outcome, and runs `loop.py` with no `--outcome-line` and no
   child pid — none of which the campaign contract can use. The transitive
   gate-consumer load heartbeat performs at import is scoped to this dispatch verb;
   042-01's record/status hot paths deliberately keep off it (mirrored ledger lock).
3. **The ledger stores `loop.py`'s own spec-040 `--outcome-line` record** (tier
   `servo`, never `self_reported`); **cost is sourced from the run's `state.json`**,
   not re-derived (AC2). When the best-effort `--outcome-line` file is absent the
   outcome is re-rendered from the terminal summary with loop.py's own
   `_outcome_record`. The subprocess RUNNER and the in-process pure-helper import are
   split across two test hooks (`SERVO_CAMPAIGN_RUNNER_PY` vs
   `SERVO_CAMPAIGN_LOOP_PY`) so the renderer always binds to the real loop.py 040
   contract; a drift guard (`test_outcome_renderer_binds_to_loop_pys_own`) fails if
   that binding breaks, matching 042-01's validator/constant parity tests.
4. **Reservation liveness is the child pid + its process start time** (`ps -o
   lstart=`), a reuse-proof handle: a recycled pid — the worker died and the number
   was reused, including across a reboot — reports a different start time and reads
   dead (frame Round-1 blocker 1). On wake, a reservation that is not live is:
   **recorded** → cleaned up; **finished but unrecorded** (the worker wrote its
   `--outcome-line` but its parent died before recording) → the orphaned line is
   **promoted** into the ledger, not re-run, keeping the finished worker's spend;
   **killed mid-run** → released and re-queued at its base sha (budget recovered,
   AC4). `_record_loop_outcome` appends the record BEFORE consuming the sink, so a
   crash in that window leaves a recorded-not-live reservation (→ `cleaned_recorded`)
   plus a harmless leftover sink, never a lost record that re-runs and double-spends
   (frame Round-2 nit).
5. **Base sha** is captured at reservation (current HEAD) and the worktree is re-cut
   at it; since servo does no git operations (AC6) HEAD is stable, so a re-queue
   re-cuts at the same base. An unresolvable base sha (broken git / no commit) is an
   `env_error`, never a `"HEAD"` string (craft Round-1 nit).
6. **Escalation scope is an optional per-item `escalation_scope`** — an *additive*
   extension to 042-01's plan schema (the required-set and the A4 contract are
   unchanged; an unknown key is still rejected). An item without one shares a single
   default scope, so a plan of independent items (distinct `oracle_ref` gates, no
   scope) batches into ONE escalation rather than one message per item — the AC5
   anti-goal. `oracle_ref` is the item's gate, deliberately NOT its escalation scope
   (frame Round-1 blocker 2). Escalations are emitted as one batched message.
7. **Non-pass terminals are status-only; only `plateau` escalates** (AC5). A recorded
   `budget`/`blocked`/`error` outcome is terminal and never auto-re-dispatched
   (servo is a command, not a queue — a human/host decides); it is surfaced via
   `campaign status`. A 040 `error` conflates a permanent block with a transient
   `claude_invocation_failed`/`verdict_schema_mismatch` (038-03 BR-7), so transient-
   error auto-retry is a deferred follow-up (refinement-todo) pending a transient-vs-
   permanent classification (frame Round-1 blocker 3, made an explicit decision). The
   pre-dispatch `gate.py` verification `_dispatch_one` runs before spending budget is
   intentionally not mirrored: the coordinator stays cheap (ADR-0049) and `loop.py`
   handles its own oracle refusal, recording the typed outcome.
8. **A non-blocking coordinator lock (`.next.lock`)** serializes overlapping wakes (a
   host + a human): a second `campaign next` backs off and exits 0, so the serial
   `max_parallel` 1 guarantee holds across invocations (frame Round-1 nit). It is held
   for the whole command, including the blocking loop run; separate from the ledger
   lock.
9. **A `coordinator_decision` ledger entry** (AC3), `kind`-tagged and carrying what
   `next` read / reconciled / dispatched (or `dispatch_error`) / escalated, so a
   mis-fan-out is debuggable from the ledger alone. `status`, the cost accounting and
   ready-detection distinguish outcome entries (`"outcome"` object, no `kind`) from
   decision entries.
10. **One ancillary deliverable.** `heartbeat.py` adds `"campaigns"` to
    `_NON_PROVISIONED_SERVO_DIRS`: a campaign worktree lives *inside*
    `.servo/campaigns/<id>/worktrees/`, so excluding `campaigns` stops
    `_provision_oracle` from recursively copying the campaign dir (which *contains*
    the worktree) into that worktree. (`scripts/test_scaffold_runtime.py` already
    classifies `campaign.py` as an ILLUSTRATIVE scaffold helper — added by 042-01
    via #56 — and the classification is keyed on the helper, so it already covers the
    new `campaign next` SKILL.md example; 042-02 does not modify it. The reviews saw
    an independently-added copy of that classification on the pre-#56 base; it
    converged with #56's on rebase.)

### Reconciliation sweep

| Artifact | Disposition | Rationale |
|----------|-------------|-----------|
| `README.md` | `no-op` | The front door lists no campaign CLI. |
| `docs/specs/README.md` (board) | `deferred` | Regenerated by `workflow.py status-board` at the close step, before DONE. |
| `docs/product-vision.md` | `no-op` | No scope or design-principle change. |
| `docs/architecture.md` | `updated` | `campaign next` servo-driven dispatch + the `worktrees/` and `reservations/` runtime sub-artifacts; the stale "no worker runs yet" clause refreshed. |
| `docs/decisions/adr-0049-…` | `no-op` | Accepted; 042-02 implements it. Implementation choices are in this deviation log + the reviews. |
| `docs/decisions/adr-0004 / adr-0010` | `no-op` | The mirrored atomic-write / flock discipline cites them; no contract change. |
| `skills/heartbeat/campaign.py` + 3 host copies | `updated` | The feature — `campaign next` (reconcile / dispatch / record / batch-escalate). |
| `skills/heartbeat/heartbeat.py` + 3 host copies | `updated` | `"campaigns"` added to `_NON_PROVISIONED_SERVO_DIRS` (provisioning-recursion fix). |
| `skills/heartbeat/SKILL.md` + 3 host copies | `updated` | `campaign next` section, the plan's optional `escalation_scope`, the status-only-terminals note; hosts regenerated + drift-checked (sync gate green). |
| `skills/heartbeat/test_campaign.py` | `updated` | TDD coverage for 042-02 (dispatch against a real repo); source-only, not vendored to hosts. |
| `scripts/test_scaffold_runtime.py` | `no-op` | `campaign.py` is already classified ILLUSTRATIVE (042-01 via #56); the helper-level classification covers the new `campaign next` example, so 042-02 does not modify it. |
| `docs/specs/042-…/reviews/slice-02-*` | `new` | compliance / craft / arch / frame-critique / reconciliation verdicts. |
| `docs/refinement-todo.md` | `updated` | 042-02 deferred follow-ups (argv second-home, transient-error retry, default-scope coarseness, the outcome-line-write + parent-death residual). |
| `CLAUDE.md` / `AGENTS.md` primers | `no-op` | No active campaign primer section to compress. |
| `docs/inbox.md` / `docs/memory/**` | `no-op` | No new domain terms or rules beyond the spec + ADR. |
| `agents/*.md` | `no-op` | Unchanged. |
| `docs/specs/042-…/spec.md` | `no-op` | Already `status: IN_PROGRESS` (042-01); the slice marker carries this slice's lifecycle. |
| `docs/specs/042-…/slice-02-…md` | `updated` | This slice doc — lifecycle transitions + hosts the deviation log + sweep. |
