---
slice: 042-05 — bounded parallel dispatch
pass: compliance
verdict: pass
reviewer: general-purpose
reviewed_at: 2026-11-13T17:06:58Z
prompt_source: review.py implementation docs/specs/042-campaign-orchestration/spec.md 042-05 skills/heartbeat/campaign.py skills/heartbeat/test_campaign.py
---

VERDICT: pass (round 1)

All five acceptance criteria for slice 042-05 are met and the tests exercise them
meaningfully, not superficially:
- AC1 (bounded dispatch of N workers at once): concurrency is genuinely proven by a
  condition-based barrier stub (every worker must observe all N started before
  proceeding); a serial dispatcher would time out at count 1. `max_parallel` is read
  from the plan, default 1.
- AC2 (aggregate ceiling before each dispatch): enforced on `_status_summary`
  enforced_cost_usd (servo + verified wrapped) + Σ reserved live ceilings + this
  item's ceiling; a breach refuses and the item stays QUEUED (proven re-run on a
  later wake). The enforced-recorded-spend term is proven with a pre-seeded 95-of-100
  ledger.
- AC3 (reservation held only while live; reconciled across all live workers): a
  killed worker among several live ones releases only its own budget/reservation —
  proven with real sleeping subprocesses for liveness plus a dead pid.
- AC4 (ledger consistency under concurrent record): 12 real competing `record`
  processes for distinct items all land, one object per line.
- AC5 (max_parallel 1/unset = serial): routes to the extracted 042-02 code with an
  identical decision shape; full suite stays green (no 042-02/03/04 regression).

Verification: 28/28 new 042-05 tests pass; full test_campaign.py green; ruff clean;
all three host campaign.py mirrors byte-identical.

Findings (both addressed post-review):
- MEDIUM (coverage): the dispatch-time fail-closed branch (`_run_next`, max_parallel>1
  + `_validate_parallel_invariants` fails → record refusal + rc=2) was untested, the
  real guard for a hand-edited plan.json since `_load_plan_file` does not re-validate.
  FIXED: `test_hand_edited_incoherent_plan_fails_closed_at_next` added.
- LOW (robustness): `reserved_live` summed only numeric ceilings, under-counting a
  ceiling-less live reservation as 0 (fail-OPEN on a cost brake). FIXED: extracted
  `_reserved_live` now recovers the item's planned ceiling from the plan, and an
  unresolvable ceiling yields `reserved_unknown` → the wake dispatches nothing
  (fail-closed); covered by `ReservedLiveFailClosedTests` + `test_unknown_reserved_
  ceiling_fails_closed`.

Reconciliation: lifecycle transition DRAFT → DONE is a close-out step (not a defect).
