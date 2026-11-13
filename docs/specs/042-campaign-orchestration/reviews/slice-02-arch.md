---
slice: 042-02 — servo-driven serial dispatch
pass: arch
verdict: pass
reviewer: jig:reviewer
reviewed_at: 2026-11-12T23:29:19Z
prompt_source: review.py arch-review docs/specs/042-campaign-orchestration/spec.md 042-02 skills/heartbeat/campaign.py skills/heartbeat/test_campaign.py skills/heartbeat/SKILL.md skills/heartbeat/heartbeat.py --richer-skill none
---

VERDICT: pass

REASONING:
Architecturally coherent and preserves servo's documented boundaries. The reuse
boundary is right: campaign.py dynamically loads loop.py and heartbeat.py (never a
static cross-skill import, enforced by `DependencyFreeTests`) and reuses the
fine-grained provisioning helpers rather than `_dispatch_one` wholesale — correct,
because `_dispatch_one` is finding-shaped, returns heartbeat's outcome object, and
runs loop.py with no `--outcome-line` and no child-pid exposure, none of which 042-02
can use. AC2 (cost from state.json with a loop.py-rendered fallback), AC4 (pid+start
liveness + release/requeue/promote with append-then-delete ordering), AC6 (no git ops
beyond worktree isolation, test-verified), and the `"campaigns"` provisioning
exclusion are all sound. Remaining items are deferred-by-scope, none blocking.

SPECIFIC ISSUES (nits):
- [nit][impl] The pre-dispatch `gate.py` oracle verification `_dispatch_one` performs
  before spending budget is intentionally not mirrored; campaign relies on loop.py's
  own in-loop oracle/refusal handling and records the typed outcome. Logged.
- [nit][impl] `_run_item_loop` is a second home for loop.py's launch argv contract
  (justified: campaign needs `Popen` + a pid for the reservation). Logged + refinement-todo.
- [nit][impl/spec] No global aggregate-ceiling brake across live workers; `max_parallel`
  1 + the non-blocking coordinator lock bound concurrency, and the aggregate ceiling is
  deferred to 042-05 (in-scope-deferred). Logged.
- [nit][spec] `escalation_scope` (optional plan field) grounds AC5's scope; default is a
  single shared batch. Logged as a forward-compatible schema addition.
- [nit][spec] docs/architecture.md:266 was stale ("no worker runs yet") → refreshed in
  the reconciliation sweep.

RECONCILIATION NOTES:
- The `"campaigns"` entry in `_NON_PROVISIONED_SERVO_DIRS` is required for correctness
  (prevents a recursive copy of the campaign dir — which contains the worktree — into
  that worktree), not tidiness. Logged.
- Dependency-free invariant preserved on the new dispatch path; the transitive
  gate-consumer load is scoped to the dispatch verb and kept off the record/status hot
  paths. Logged.
