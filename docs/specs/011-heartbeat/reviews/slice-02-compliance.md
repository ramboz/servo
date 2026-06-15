---
slice: 011-02 — triage-state-spine
pass: compliance
verdict: pass
reviewer: jig:reviewer
reviewed_at: 2026-06-15T16:21:30Z
prompt_source: review.py implementation docs/specs/011-heartbeat/spec.md 011-02 skills/heartbeat/heartbeat.py skills/heartbeat/test_heartbeat.py
---

VERDICT: pass

REASONING:
All 11 acceptance criteria are met by heartbeat.py and meaningfully exercised by the
named test classes — tests assert behavior end-to-end (real merge/resume/retention via
seeded inboxes, a real held flock for contention, the full 3-tier default-branch
resolution), not superficial string matches. The implementation faithfully honors
ADR-0010's schema, volatility classes, dedupe identity, uniform merge/retention,
two-axis status/actionable split, immutable provenance, persistent-never-unlinked lock
discipline, and the asymmetric discover-rebuild vs status-warn/refuse migration. No
correctness, security, or robustness blockers.

SPECIFIC ISSUES:
- [strength] heartbeat.py:312-333 — _classify_ci's main/master last-resort heuristic only
  matches the two conventional default names, never up-classifying a feature branch
  (fail-toward-not-spending); all four resolution tiers + the pull_request event gate tested.
- [strength] heartbeat.py:724-765 — _inbox_lock takes the advisory lock on a separate,
  persistent .inbox.lock (never the inbox inode, never unlinked) and distinguishes
  BlockingIOError contention (exit 0) from a propagated OSError (rc 2).
- [strength] heartbeat.py:682-695 — _merge_one re-derives provenance from source on every
  merge (heals hand-edits); _normalize_record re-emits canonical key order for byte-stable output.
- [nit] heartbeat.py:1084-1085 — _read_inbox_for_status refuses a mixed-version file with a
  new machine code schema_version_mixed not in ADR-0010's enumerated reason vocabulary.
  Faithful to AC1, but undocumented in the ADR.
- [nit] heartbeat.py:629 — discover write-path drops any record where schema_version != current
  (also evicts a higher unknown version), broader than AC10's literal "< 2". Benign (inbox is
  re-derivable).

RECONCILIATION NOTES:
- AC1 "mixed-version rejected (rc=2)" is enforced on the status read path; the discover write
  path discards non-current records and rebuilds (per ADR-0010). Consistent with the ADR; note
  the read-vs-write asymmetry in the deviation log.
- Reader introduces schema_version_mixed beyond the ADR-named schema_version_unsupported —
  reconcile into ADR-0010's reason vocabulary at close-out (ADR still mutable).
- discover write-path drops by != current (also higher versions); AC10 literally specifies "< 2".
  Note as a deliberate broadening.
- Empty-stdout-on-clean-exit path reports a healthy-but-empty source as ran(0) rather than
  skipped(unparseable) — strengthens AC5 health honesty.
- DoD boxes unticked / ADR Proposed / slice IN_PROGRESS — expected close-out tasks.

Reviewer: jig:reviewer (independent compliance pass). Context: 111 heartbeat tests green
(53 original + 58 new/extended); full suite has 2 pre-existing oracle-hook env failures
(unrelated, proven by stash); ruff 0.15.17 clean.
