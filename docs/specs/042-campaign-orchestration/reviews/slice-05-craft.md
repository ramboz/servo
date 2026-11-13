---
slice: 042-05 — bounded parallel dispatch
pass: craft
verdict: pass
reviewer: general-purpose
reviewed_at: 2026-11-13T17:06:58Z
prompt_source: review.py pr-review docs/specs/042-campaign-orchestration/spec.md 042-05 skills/heartbeat/campaign.py skills/heartbeat/test_campaign.py
---

VERDICT: pass

The launch/join split (`_launch_item` + `_join_and_record`, and `_run_item_loop`
split into `_spawn_item_loop` + `_join_item_loop`) makes serial dispatch the literal
N=1 case of the parallel wave, and behaviour-preservation is well-evidenced: the full
campaign suite is green, ruff clean, all three host mirrors byte-identical, and
SerialPathRegressionTests pins the 042-02 singular decision shape. The
aggregate-ceiling math is keyed on the right accounting term
(`_status_summary.enforced_cost_usd` — tier servo + verified wrapped only), and the
concurrency proof is a condition-polled shared barrier (not a fixed-sleep race). No
correctness or security blockers.

Strengths (preserve):
- `_budget_shape_error` extracted so per-item `budget` and plan-level `aggregate_budget`
  share one `{unit, ceiling}` contract and cannot drift.
- `_on_spawn` records the item's ceiling+unit into the reservation, so the live-worker
  reserved sum needs no plan re-read; the record-before-reservation-delete crash-safety
  ordering is carried intact into `_join_and_record`.
- Barrier-based (non-sleep) concurrency proof — the correct pattern vs the project's
  prior fixed-sleep signal-timing-race tests.
- Rationale-bearing error messages (e.g. the credit-aggregate and per-item
  USD-denomination refusals).

Nits:
- [nit→FIXED] The dispatch-time fail-closed branch (`_run_next`) was untested (the
  real guard once `_load_plan_file` does not re-validate). Regression test added
  (`test_hand_edited_incoherent_plan_fails_closed_at_next`).
- [nit→FIXED] `reserved_live` silently dropped a ceiling-less live reservation
  (under-count, fail-OPEN). Tightened to fail closed via `_reserved_live` (plan-ceiling
  fallback; unknown → dispatch nothing).
- [nit→conscious] Minor serial/parallel duplication (env-error breadcrumb + the
  `{item,run_id,result,cost_usd}` field shaping): the singular-vs-plural decision
  contract makes full extraction marginal; left as-is, logged in the deviation log.
- [nit→conscious] The barrier stub's 30s deadline only affects how long a *broken*
  (serial) implementation takes to fail; the correct path resolves in ms. Logged.

Craft bar met; no blockers.
