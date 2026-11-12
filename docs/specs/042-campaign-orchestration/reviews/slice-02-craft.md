---
slice: 042-02 — servo-driven serial dispatch
pass: craft
verdict: pass
reviewer: jig:reviewer
reviewed_at: 2026-11-12T23:29:19Z
prompt_source: review.py pr-review docs/specs/042-campaign-orchestration/spec.md 042-02 skills/heartbeat/campaign.py skills/heartbeat/test_campaign.py skills/heartbeat/SKILL.md skills/heartbeat/heartbeat.py --richer-skill none (round 2)
---

VERDICT: pass (round 2)

REASONING:
Round 1 returned needs-changes on five nits (no blockers); round 2 confirms all are
adequately fixed and the `_record_loop_outcome` refactor is sound. The
runner/renderer env-var split (`SERVO_CAMPAIGN_RUNNER_PY` vs
`SERVO_CAMPAIGN_LOOP_PY`) is the right design: the stub replaces the spawned worker
while the fallback path binds to the real loop.py `_outcome_record`, so the new
fail-open tests and the `test_outcome_renderer_binds_to_loop_pys_own` drift guard are
effective rather than self-referential. `_record_loop_outcome` is correctly shared by
normal dispatch and orphan promotion with consistent sink-consume / ledger-append /
reservation-cleanup ordering; host parity holds across all three vendored copies.

SPECIFIC ISSUES (round 1, all resolved in round 2):
- [nit][impl] fail-open surface + no `_outcome_record` drift guard → added the
  fallback/env-error/state-absent/credit tests + the drift guard; split the runner
  and pure-helper import hooks.
- [nit][impl] `_load_heartbeat` docstring listed an unused `_is_git_work_tree` → now
  an early guard in `_dispatch_item`.
- [nit][impl] env-error reason only on stderr → `dispatch_error` recorded on the
  coordinator-decision entry.
- [nit][impl] magic `--max-iterations "5"` → `COPILOT_DEFAULT_MAX_ITERATIONS`.
- [nit][impl] `base_sha` → `"HEAD"` string fallback → unresolved base sha is now an
  env_error.

Post-pass nits (round 2), addressed before landing:
- the stale 042-02 harness-section comment (said `SERVO_CAMPAIGN_LOOP_PY`) → corrected
  to `SERVO_CAMPAIGN_RUNNER_PY`.
- orphan promotion discarded the failure reason → now emits an `orphan_unrecordable`
  breadcrumb before re-queue.
- the non-git early-guard had no direct test → `test_non_git_target_is_dispatch_env_error`.

RECONCILIATION NOTES:
- The runner/pure-helper import split is logged in the deviation log as the mechanism
  that keeps the 040 renderer on loop.py's real contract.
