---
slice: 042-02 — servo-driven serial dispatch
pass: compliance
verdict: pass
reviewer: jig:reviewer
reviewed_at: 2026-11-12T23:29:18Z
prompt_source: review.py implementation docs/specs/042-campaign-orchestration/spec.md 042-02 skills/heartbeat/campaign.py skills/heartbeat/test_campaign.py skills/heartbeat/SKILL.md skills/heartbeat/heartbeat.py
---

VERDICT: pass

REASONING:
All six ACs of slice 042-02 are implemented in `campaign.py`'s `cmd_next` path and
tested in `test_campaign.py`'s `Next*` classes against a REAL git repo + a stub
`loop.py` (per the DoD's real-repo requirement). AC2 cost-from-state.json is proven
with divergent values (state 0.42 vs outcome-line 99.0); reservation reconciliation
(AC4) is covered across killed/live/recorded/promoted cases; escalation batching
(AC5) is verified by scope. The two side deliverables are correct: `heartbeat.py`
adds `"campaigns"` to `_NON_PROVISIONED_SERVO_DIRS` (prevents recursive self-copy of
the nested campaign worktree during `_provision_oracle`), and
`scripts/test_scaffold_runtime.py` classifies `campaign.py` as illustrative (closes a
latent 042-01 gap). Dispatch code is synced to all three vendored host copies.

SPECIFIC ISSUES:
- [nit][impl] Round 1 noted the credit/Copilot dispatch argv and the fail-open /
  fallback paths were untested. Addressed: `test_credit_item_dispatches_copilot_...`,
  `test_fallback_renderer_used_...`, `test_no_outcome_and_no_summary_...`,
  `test_cost_falls_back_to_outcome_line_when_state_json_absent` added.
- [nit][impl] `test_loop_launched_with_item_budget_and_models` now asserts the
  forwarded `--cost-ceiling` value and the models-block content (was: presence only).

RECONCILIATION NOTES:
- AC4 "re-queued at its base sha" is implemented via the HEAD-stability invariant
  (servo does no git ops, AC6): a re-dispatch re-cuts at current HEAD, == the stored
  base sha. Logged in the deviation log.
- AC6 "no git operations" = no landing ops beyond worktree isolation; `git worktree
  add/remove` are performed (reusing the heartbeat's provisioning). Logged.
- Non-pass terminals (budget/blocked/error) are status-only; only plateau escalates.
  Explicit decision, logged in the deviation log + refinement-todo.
