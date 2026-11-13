---
slice: 042-02 — servo-driven serial dispatch
pass: reconciliation
verdict: pass
reviewer: general-purpose
reviewed_at: 2026-11-12T23:37:50Z
prompt_source: review.py reconciliation docs/specs/042-campaign-orchestration/spec.md 042-02
---

VERDICT: pass

The deviation log's 10 load-bearing choices each correspond to a real, accurately
described change in the diff — nothing invented, overstated, or silently altered. The
two load-bearing frame claims hold in code: `_record_loop_outcome` appends the ledger
entry BEFORE `outcome_path.unlink()` (the re-spend-window fix), and `_run_is_live`
pairs `_pid_alive` (`os.kill(pid, 0)`) with `_process_start` (`ps -o lstart=`). The
reconciliation sweep is complete and its dispositions credible: every file in the diff
maps to a sweep row, and the `no-op` / `deferred` rows don't conflict with touched files.

Verified (all pass):
- Host sync: `build_host_packages.py --check` → exit 0 (the three vendored copies of
  campaign.py / heartbeat.py / SKILL.md match source).
- Choices 1–9 in campaign.py: `next` wired into the existing argparse; dynamic
  `spec_from_file_location` loads of loop.py AND heartbeat.py, reusing the five named
  provisioning helpers (`_dispatch_one` is NOT called); split test hooks
  (`SERVO_CAMPAIGN_RUNNER_PY` vs `SERVO_CAMPAIGN_LOOP_PY`); cost from state.json; the
  three reconcile dispositions (cleaned_recorded / promoted_orphan / released_requeued);
  base-sha-unresolvable → env_error; `escalation_scope` additive with unknown keys still
  rejected + single-default-scope batching; only plateau escalates (budget/blocked/error
  status-only); non-blocking `.next.lock`; `coordinator_decision` entry distinguished by
  `kind`.
- Choice 10: heartbeat.py `"campaigns"` in `_NON_PROVISIONED_SERVO_DIRS`;
  test_scaffold_runtime.py classifies campaign.py illustrative.
- Tests source-only (no host copy); `DependencyFreeTests` AST scan forbids static
  cross-skill imports; the drift guard + constants parity tests present; dispatch
  exercised against a REAL `git init` repo (DoD met).
- Sweep rows: architecture.md updated (stale "no worker runs yet" clause replaced);
  refinement-todo.md has all four deferred follow-ups with resolution triggers; SKILL.md
  updated; the four slice-02 content-review verdicts exist and match the round narrative.
- ADR-0049 (accepted) is the decision of record; new deferred debt tracked in
  refinement-todo. No design-principle violation. No untracked TODO/FIXME.

SPECIFIC ISSUES: none

RECONCILIATION NOTES: none — the sweep is accurate and complete. (The sweep's
`reviews/` row lists `reconciliation` under `new`; this verdict file is that artifact,
written at landing, so the row is accurate once this file lands.)
