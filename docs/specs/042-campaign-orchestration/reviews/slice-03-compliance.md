---
slice: 042-03 — host-driven advisory
pass: compliance
verdict: pass
reviewer: jig:reviewer
reviewed_at: 2026-11-13T02:51:00Z
prompt_source: review.py implementation docs/specs/042-campaign-orchestration/spec.md 042-03 skills/heartbeat/campaign.py skills/heartbeat/test_campaign.py skills/heartbeat/SKILL.md skills/heartbeat/heartbeat.py (round 2)
---

VERDICT: pass (round 2)

REASONING:
All five ACs are met and backed by non-vacuous tests. AC1 (`campaign brief`) emits
per-item prompt/oracle_ref/budget/models-as-data + base sha + record-before-commit +
item-text-is-data. AC2's re-check downgrades a claimed `passed` to blocked/error
(gate exit 1/2) and fails closed rc=2 on an uninvocable gate or a missing/absent
`--worktree`, with a real-`gate.py` integration test. AC3 keeps advisory cost out of
enforced spend even on a confirmed pass; AC4's `ADVISORY_RUNAWAY_NOTE` is a single
source emitted in both brief and status (quiet for servo-only); AC5's no-spawn tests
assert a genuine trace (a spawned loop writes `<worktree>/.servo/runs/`, which the
gate-only re-check never creates), resolving the R1 vacuous-test blocker.

SPECIFIC ISSUES:
- Round 1 blocker (AC5 no-spawn tests vacuous: asserted a `RUNNER_RAN` sentinel the
  stub never writes) — FIXED: tests now assert the loop-invocation log stays absent
  and no `<worktree>/.servo/runs/` appears.
- SKILL.md brief-summary "can no longer be verified" over-claimed advisory provenance
  — FIXED to match the brief's honest rationale.
- Base-sha fallback message imprecise (non-git only) — FIXED to "no resolvable git HEAD".

RECONCILIATION NOTES:
- Deviation log is faithful and complete: entry-level `self_reported` + `oracle_recheck`
  modeling of AC3, the result/reason read-back, the gate-runs write vs AC5 prose, the
  installed-oracle (not `oracle_ref`) scope, the non-git fallback, and the updated
  `test_advisory_is_self_reported` are all recorded.
