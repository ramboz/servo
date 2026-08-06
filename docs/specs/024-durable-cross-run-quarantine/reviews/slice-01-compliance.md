---
slice: 024-01 — cross-run quarantine record, quarantined status, and evidence-gated re-admission
pass: compliance
verdict: pass
reviewer: jig:reviewer
reviewed_at: 2026-08-06T17:40:07Z
prompt_source: independent compliance review (024-01)
---

Independent compliance review of slice 024-01 (jig:reviewer, read-only, no impl-conversation access).

VERDICT: pass

All four ACs implemented and covered by non-vacuous tests driving the real dispatch/discover
subprocess paths:
- AC1: heartbeat.run_dispatch writes `.servo/quarantine/<finding_id>.json` on
  `terminal_reason == oracle_plateau`, sets status `quarantined`; key is the content-derived
  finding_id (run-id-independent, verified across two targets). loop.py is unchanged.
- AC2: open-only `_select_candidates` skips quarantined; `quarantine` added to
  `_NON_PROVISIONED_SERVO_DIRS` (worktree-exclusion test passes).
- AC3: evidence-gated re-admission on discover (changed pointer OR missing record → re-admit;
  unchanged → stay; run_url-only change → no re-admit); volatile-key projection excludes
  url/*_url/*_at.
- AC4: servo-owned record schema round-trips against `_QUARANTINE_RECORD_KEYS`; exposes
  finding_id + evidence_location + reserved bug_ref:null; no jig invoked.

Negative controls (pass→passed, non-plateau→tried, run_url-only→no-readmit, write-failure→tried)
rule out vacuous passes. Reconciliation note: the record carries a reserved `bug_ref: null`
field beyond AC1's literal key list — intentional per AC4's jig-mapping requirement; logged in
the deviation log.
