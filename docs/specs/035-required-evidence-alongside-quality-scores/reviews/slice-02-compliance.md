---
slice: 035-02 - required-verdict-consumers
pass: compliance
verdict: needs-changes
reviewer: jig:reviewer / 03502-compliance (fresh context)
reviewed_at: 2026-10-15T06:28:00Z
prompt_source: review.py implementation; 035-02-compliance-prompt.txt
---

VERDICT: needs-changes

REASONING:
Core veto propagation has meaningful installed controls, but unavailable-evidence
reporting and two hook error paths remain incorrect. The 1,245 consumer and 159
runtime/install passing results were inspected, not rerun. Existing stdlib
allowlist test assertions remain intact.

SPECIFIC ISSUES:
- heartbeat.py:2166-2175 unconditionally replaces final unavailable status with
  the retained earlier gate's status. After an evaluated iteration followed by
  invocation failure/interruption, preserve final env_error/unknown_interrupted
  separately from prior evidence; add multi-iteration controls and rereads.
- meta-judge.sh.template:26 inserts an unquoted absolute consumer path. Valid
  runtime paths containing spaces can abort without advice/warning. Safely
  quote rendered paths and test actual installations with spaces.
- meta-judge.sh.template:70 calls d.get() before protected validation. Valid
  non-object JSON []/null silently continues; validate root type in the guarded
  warning path and test non-object outputs. Generated templates share both bugs.

RECONCILIATION NOTES:
AC1/3/4 are partial until these blockers clear; AC2/5/6 have substantial evidence.
Legacy minimal no-policy compatibility and absolute-sidecar isolation refusal
are explicit bounded deviations. Record corrections and obtain fresh review
evidence before close-out. DoD review/reconciliation remain pending.
