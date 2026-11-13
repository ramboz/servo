---
status: DONE
kind: feature
dependencies: [042-02]
last_verified: 2026-11-13
arch_review: true
frame_review: true
---

## Slice 042-05 — bounded parallel dispatch

**Goal:** `campaign next` may dispatch up to `max_parallel` (> 1) servo-driven
workers at once, under an **aggregate** cost ceiling enforced before each
dispatch on Σ recorded spend + Σ reserved per-worker ceilings of the live
workers. This is the concurrency step; it is deferred out of the parity release
because `max_parallel` defaults to 1 and A2 is unverified.

**DoR:**
- 042-02 is DONE (serial dispatch + reservation reconciliation).

**Acceptance Criteria:**

1. `campaign next <id>` dispatches additional ready items up to `max_parallel`,
   each in its own worktree. `max_parallel` is read from the plan and defaults
   to 1 (serial, i.e. 042-02's behaviour) when unset.
2. Before each dispatch, the aggregate ceiling is enforced on Σ recorded spend
   (servo + verified wrapped) + Σ reserved per-worker ceilings of live workers.
   A dispatch that would breach the aggregate ceiling is refused and the item
   stays queued.
3. A per-worker reservation is held only while that item's `loop.py` run is
   live; it is reconciled on wake (042-02 AC4) across all live workers, so a
   killed worker among several releases only its own budget.
4. The ledger's `flock` + atomic-write discipline keeps the ledger consistent
   under concurrent `campaign record` writes from parallel workers.
5. If parallel workers routinely conflict on shared target resources, the plan
   can cap `max_parallel` at 1 and keep only the planned-list and ledger value
   (ADR-0049 kill criterion); the cap is per-campaign.

**DoD:** ACs pass with tests (concurrent record under lock; aggregate-ceiling
refusal); compliance + craft + arch reviews; reconciliation.

**Anti-horizontal-phasing check:** a campaign with `max_parallel: 3` runs three
workers at once under one aggregate budget, the ledger stays consistent, and a
killed worker's reservation is recovered — bounded parallelism end to end.

## Assumptions

- **A2 (resource contention):** parallel worktree workers on one machine don't
  contend on shared resources (ports, caches, the target's build dirs) for
  typical targets. Unverified; this slice is why `max_parallel` default stays 1
  until a real campaign raises it.

## Scope — what the aggregate brake does and does NOT cover

The frame-critique's central reading (recorded in the deviation log) is that this
slice's one novel contribution — the **aggregate** ceiling — is deliberately
**narrow**, and the narrowness must be stated plainly, not left implicit:

- **Servo-driven, USD-only.** The aggregate ceiling is computed and enforced only
  in `_parallel_dispatch`, reached only by servo-driven `campaign next`. It applies
  to single-unit **USD** campaigns on Claude Code (ADR-0049's enforced mode:
  "servo itself runs up to N `loop.py` workers … under an aggregate ceiling").
- **Host-driven mode has NO campaign-level aggregate cap.** In advisory (042-03)
  and wrapped (042-04) modes the host spawns the workers; servo only records. There
  is no servo coordinator to enforce an aggregate ceiling before dispatch. A
  **wrapped** wave's aggregate exposure is Σ the per-worker `loop.py` ceilings (each
  worker's loop is braked) with no campaign-level cap; an **advisory** wave has no
  per-worker loop ceiling at all (nothing brakes a runaway advisory worker in flight
  — 042-03's `campaign status` discloses exactly this), so its in-flight exposure is
  unbounded. Either way there is no campaign-level aggregate cap. This is inherent to
  host-driven mode, not a 042-05 omission.
- **The motivating Copilot runaway is NOT addressed by this slice.** ADR-0049's
  recorded two-day runaway was a credit-billed, **host-driven**, 15-worker Copilot
  fan-out. ADR-0049 bounds it through **042-04's per-worker verified-wrapped**
  bounding of each `loop.py` subprocess — not through 042-05's aggregate ceiling,
  which that case (host-driven, credit) cannot use. 042-05 adds nothing to the
  Copilot aggregate story; it is a Claude-Code/USD refinement, gated behind the
  unverified A2 and `max_parallel` default 1.
- **Credit-priced aggregate is deferred, not forbidden forever.** A credit
  `aggregate_budget` or any credit item under `max_parallel > 1` is rejected
  fail-closed because recorded credit spend is `cost_usd: null` (never summed to
  USD). Pricing credits to a USD-equivalent aggregate ceiling (feasible with spec
  041's Copilot per-1M pricing) is a follow-up (`docs/refinement-todo.md`), not a
  property of this slice.
- **The coordinator blocks for the whole wave.** `campaign next` launches the wave
  then joins every worker in plan order under the held non-blocking lock, with no
  outer timeout — so for a multi-hour wave it is a lock-holding process for the
  duration of the **slowest** worker, and freed slots/budget are reused on the
  **next** wake, not mid-wave (selection happens once per wave). It remains a
  command that exits (episodic, no daemon), but the "cheap/episodic" story is a
  wave-duration blocking window, generalizing 042-02's single-loop block. A
  completion-order join with mid-wave re-selection is a deferred enhancement
  (`docs/refinement-todo.md`).

### Deviation log (after reconciliation)

The original ACs are preserved above. Review rounds:
- **Round 1:** **compliance / craft / arch PASS** (each with nits, folded below);
  **frame-critique NEEDS-CHANGES** — the PRIMARY finding was *frame honesty, not a
  code defect* ("the code is correct and unusually honest"): 042-05's aggregate
  ceiling lands only on servo-driven USD campaigns, while ADR-0049's motivating
  runaway is credit-billed host-driven Copilot — a mode that structurally gets no
  servo-enforced aggregate ceiling. The SECONDARY finding: the "episodic coordinator"
  story understates a wave-duration blocking window. Both were addressed by the
  honest **Scope** section above (and the architecture.md / SKILL.md scope notes),
  not by a code change — the reviewer's own prescribed fix ("a frame change, not a
  code fix").
- **Round 2:** **frame-critique PASS** after the Scope section made the narrowness
  explicit. **Reconciliation PASS.**

Load-bearing choices made during implementation:

1. **The dispatch model is Popen-all-then-join-all within one `campaign next`**
   (`_dispatch_items`), so workers run concurrently while the coordinator stays an
   episodic command that exits. The serial path (`max_parallel` 1) is the **N=1
   case**: `_dispatch_item` is `_launch_item` (isolate → provision → Popen →
   reservation) then `_join_and_record` (communicate → record → delete
   reservation), and `_run_item_loop` was split into `_spawn_item_loop` +
   `_join_item_loop`. `max_parallel` 1/unset routes to the unchanged serial block
   with the identical 042-02 decision shape (regression-guarded by
   `SerialPathRegressionTests`). *Rejected:* a detach-and-exit episodic model
   (record on a later wake) — a large divergence from 042-02 and fiddly
   daemonization; *rejected:* a serial-blocking "wave" (not actually concurrent).
2. **Aggregate-ceiling SOURCE: a new optional plan-level `aggregate_budget{unit,
   ceiling}`** (same `{unit, ceiling}` shape as a per-item budget, shared validator
   `_budget_shape_error`). Required when `max_parallel > 1` (fail-closed: no
   unbounded parallel spend); optional + unenforced when serial (serial path
   unchanged). The per-item `budget.ceiling` bounds one worker; the campaign's total
   needs its own declared cap (ADR-0049).
3. **Mixed units: parallelism is single-unit USD, fail-closed** (`_validate_parallel_
   invariants`, enforced at `init` AND re-checked at `next`). Recorded credit spend
   is `cost_usd: null` (041-02 per-run brake; "the USD totals never mix units"), so
   an aggregate credit ceiling could not enforce AC2's "Σ recorded spend" term — it
   would be a false brake. See the Scope section.
4. **The aggregate check reserves each live worker's FULL ceiling** (worst case);
   on finish its reservation is released and its ACTUAL recorded spend joins the
   enforced total. A refused item stays **queued** and selection **stops in plan
   order** (no skip-ahead — no priority inversion / starvation of a high-priority
   item). The reservation now carries `ceiling` + `unit` so the live-worker sum is
   computable (additive to 042-02's record).

Nits fixed (compliance / craft / arch):
- **`reserved_live` tightened to fail CLOSED.** A live reservation that lacks a
  numeric `ceiling` (e.g. a pre-042-05 reservation surviving a mid-campaign binary
  upgrade) now recovers the item's planned ceiling from the plan by item id, and a
  ceiling neither recorded nor resolvable yields `reserved_unknown` → the wake
  dispatches **nothing** (extracted testable `_reserved_live`). Previously it summed
  only numeric ceilings, silently under-counting (fail-open on a cost brake).
- **The dispatch-time fail-closed branch is now directly tested**
  (`test_hand_edited_incoherent_plan_fails_closed_at_next`): a plan.json hand-edited
  after init into an incoherent parallel plan (`_load_plan_file` does not
  re-validate) → `next` records the refusal and exits rc=2, dispatching nothing.

Conscious design choices (noted, not changed):
- **The `coordinator_decision` entry is polymorphic by mode**: serial keeps
  042-02's singular `dispatched` (object|None) + `dispatch_error`; the parallel wave
  records a list `dispatched` + `dispatch_errors` + an `aggregate{unit, ceiling,
  enforced_spend, reserved_live, reserved_unknown, free_slots, refused}` block; a
  hand-edited-plan refusal records `aggregate{error}`. This is the cost of keeping
  the serial path byte-for-byte 042-02 (AC5). Decision entries are forensic/debug
  data (not a consumed contract), parallel is opt-in (default 1), and architecture.md
  now notes the richer parallel shape.
- **`enforced_spend` counts a re-queued item's re-run cost cumulatively** (it is Σ
  over all recorded outcomes, not distinct-item spend). Safely conservative — the
  aggregate caps total money spent and stops dispatch sooner, never later.
- **Minor serial/parallel duplication** (the env-error breadcrumb + the
  `{item, run_id, result, cost_usd}` dispatched-field shaping) is left in place: the
  singular-vs-plural decision contract makes full extraction marginal.
- **The concurrency-proof barrier stub uses a 30s deadline**: condition-based
  (every worker must observe all N started), so the correct path resolves in ms; the
  deadline only bounds how long a *broken* (serial) implementation takes to fail.

Deferred / documented follow-ups (`docs/refinement-todo.md`):
- **Credit-priced aggregate ceiling.** Price AI credits to a USD-equivalent (spec
  041's Copilot per-1M pricing) so a credit / Copilot campaign can carry an
  aggregate ceiling, lifting the single-unit-USD restriction on parallelism.
- **Wave blocking window.** A completion-order join (poll/select) with mid-wave
  re-selection would reuse freed slots/budget within a wave and shorten the
  lock-holding window, instead of selecting once per wave and blocking on the
  slowest worker.
- **A2 (resource contention).** Unverified. A real campaign must settle whether
  parallel worktree workers contend on shared target resources (ports, caches,
  build dirs) before `max_parallel` default is raised above 1.

### Reconciliation sweep

| Artifact | Disposition | Rationale |
|----------|-------------|-----------|
| `skills/heartbeat/campaign.py` + 3 host copies | `updated` | `PLAN_TOP_KEYS` += `max_parallel` / `aggregate_budget`; `_budget_shape_error` (shared), `_validate_aggregate_budget`, `_validate_parallel_invariants`; `_plan_max_parallel` / `_plan_aggregate_ceiling` / `_reserved_live`; `_launch_item` / `_join_and_record` / `_dispatch_items` (split from `_dispatch_item`); `_spawn_item_loop` / `_join_item_loop` (split from `_run_item_loop`); `_serial_dispatch` / `_parallel_dispatch` / `_emit_escalations` and the `_run_next` branch. Byte-identical across hosts (drift gate green). |
| `skills/heartbeat/test_campaign.py` | `updated` | TDD coverage over a real git worktree + injected stub runner: barrier-proven concurrency, aggregate-ceiling refusal (within-wave + enforced-spend term), mixed-unit fail-closed, killed-among-several reconcile, concurrent distinct-item record, serial byte-identity, dispatch-time fail-closed, `_reserved_live` fallback. Source-only, not vendored. |
| `skills/heartbeat/SKILL.md` + 3 host copies | `updated` | The bounded-parallel-dispatch paragraph + the aggregate-brake scope; hosts regenerated + drift-checked (host-transformed, not byte-identical — the drift gate is authoritative). |
| `docs/architecture.md` | `updated` | The campaign paragraph now documents 042-05 (max_parallel, aggregate ceiling, single-unit-USD, the Scope of the brake, the wave blocking window, the richer decision shape). |
| `docs/decisions/adr-0049-…` | `no-op` | Accepted; 042-05 implements its bounded-parallelism boundary-line treatment. The aggregate ceiling it describes is the servo-driven one this slice builds; no ADR edit needed. |
| `docs/refinement-todo.md` | `updated` | Credit-priced aggregate ceiling, the wave blocking window, and the A2 contention question recorded as follow-ups. |
| `docs/specs/042-…/spec.md` | `no-op` | Already `status: IN_PROGRESS`; the slice marker carries this slice's lifecycle. |
| `docs/specs/042-…/slice-05-…md` | `updated` | This slice doc — lifecycle, the Scope section, the deviation log, this sweep. |
| `docs/specs/042-…/reviews/slice-05-*` | `new` (written at close-out) | The compliance / craft / arch / frame-critique / reconciliation verdicts, persisted by `review.py record-review` at the close step (before DONE) — parallel to the board row above. Written into the changeset before landing, so the `new` disposition is accurate at commit time. |
| `docs/specs/README.md` (board) | `deferred` | Regenerated by `workflow.py status-board` at the close step, before DONE. |
| `skills/agent-loop/loop.py` | `no-op` | 042-05 is campaign.py-only; loop.py is untouched. |
| `README.md` / `docs/product-vision.md` / `docs/memory/**` / `CLAUDE.md` | `no-op` | No front-door, principle, glossary, or primer change beyond the spec + ADR. |
