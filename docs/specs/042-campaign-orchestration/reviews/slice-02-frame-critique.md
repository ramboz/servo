---
slice: 042-02 — servo-driven serial dispatch
pass: frame-critique
verdict: pass
reviewer: jig:reviewer
reviewed_at: 2026-11-12T23:29:19Z
prompt_source: review.py frame-critique docs/specs/042-campaign-orchestration/spec.md 042-02 skills/heartbeat/campaign.py skills/heartbeat/test_campaign.py skills/heartbeat/SKILL.md skills/heartbeat/heartbeat.py (round 2)
---

VERDICT: pass (round 2)

REASONING:
Round 1 raised three frame blockers; round 2 confirms all are substantively resolved
and test-covered, and both nits are closed.
- Blocker 1 (pid-only liveness broke AC4): liveness is now pid + `ps -o lstart=`
  start-time (`_run_is_live`), so a recycled pid (incl. across a reboot) reads dead; a
  finished-but-unrecorded worker is PROMOTED (`promoted_orphan`), not re-run.
- Blocker 2 (scope = oracle_ref, degenerate): scope is now an explicit optional
  `escalation_scope`, with a single default batch for unscoped items, so a plan of
  independent items batches into ONE escalation rather than one-per-item.
- Blocker 3 (readiness/escalation coherence): an explicit, SKILL.md-documented
  decision — non-pass terminals are status-only, only plateau escalates, transient-
  error auto-retry deferred.
Nits closed: stale sink unlinked before launch; non-blocking `_next_lock`.

SPECIFIC ISSUES:
- [nit][impl] (round 2) `_record_loop_outcome` unlinked the sink BEFORE appending the
  ledger entry — a crash in that window would lose the record and re-run the finished
  worker (a narrow re-spend edge). FIXED before landing: append-then-unlink, so a
  crash leaves a recorded outcome + a harmless leftover sink (reconciliation →
  `cleaned_recorded`), never a double-run.

RECONCILIATION NOTES:
- Plan-schema extension: an additive optional per-item `escalation_scope` grounds
  AC5's scope; the 042-01 required-set is unchanged and unknown keys still rejected.
  Logged as a forward-compatible schema addition.
- Deferral decision (non-pass terminals status-only; transient-error retry deferred)
  recorded in the deviation log + refinement-todo.
- `_run_is_live` degrades to pid-only when `pid_start` was not captured (a rare `ps`
  miss at spawn); documented. Note only.
