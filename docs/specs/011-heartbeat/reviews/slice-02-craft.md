---
slice: 011-02 — triage-state-spine
pass: craft
verdict: pass
reviewer: jig:reviewer
reviewed_at: 2026-06-15T16:21:30Z
prompt_source: review.py pr-review docs/specs/011-heartbeat/spec.md 011-02 skills/heartbeat/heartbeat.py skills/heartbeat/test_heartbeat.py
---

VERDICT: pass

REASONING:
The implementation faithfully extends 011-01 into a resuming state spine and follows every
established house pattern: the {0,2} closed exit contract preserved across both verbs, atomic
<name>.tmp + os.replace writes (mirroring loop.py's STATE_TMP_SUFFIX), gh/git invoked list-form
via a single bounded _run_subprocess and never imported, stdlib-only (fcntl guarded for non-POSIX
degradation), docstring density matching the codebase. The highest-risk choices — separate-never-
unlinked advisory lock, immutable/sticky/volatile field classes, key-order normalization that
heals hand-edits, two-rule schema migration — are implemented cleanly and exercised by meaningful
tests. The single flaw is a cosmetic reason-code misattribution, deferrable, affecting no
actionability verdict.

SPECIFIC ISSUES:
- [strength] heartbeat.py:724-765 — _inbox_lock: separate persistent .inbox.lock, never
  inbox.jsonl (whose inode os.replace swaps), never unlinked (unlink→close race named),
  kernel-released, non-blocking refuse → lock_contended exit 0. test_lock_file_not_unlinked_across_runs
  asserts inode stability.
- [strength] heartbeat.py:698-721 + 682-695 — _normalize_record / _merge_one re-emit canonical v2
  key order and re-derive immutable provenance from source, healing hand-edited inboxes.
- [strength] heartbeat.py:373-386, 447-450 — empty-stdout-vs-[] distinction keeps the AC5 health
  header honest; covered by test_empty_stdout_reports_ran_not_skipped.
- [nit] heartbeat.py:331-333 — _classify_ci: a pull_request run whose headBranch equals the default
  branch is correctly actionable:false, but the reason returned is ci_non_default_branch (factually
  wrong — the branch IS the default; the disqualifier is the event). Consider an additive
  ci_non_actionable_event code. Deferrable.
- [nit] heartbeat.py:790-796 — _status_counts (consumed by _render_markdown) duplicates the
  by-status tally that _summarize_inbox reimplements inline (1144-1162); a shared helper would
  prevent drift. Nice-to-have.

RECONCILIATION NOTES:
- The actionable_reason for an event-disqualified CI run on the default branch is
  ci_non_default_branch (not branch-accurate) — log as a deferred reason-code refinement (additive
  ci_non_actionable_event), not a behavior bug.
- Markdown rendering of contributor-controlled title/detail into inbox.md is verbatim (detail
  line-1-trimmed, title not newline-sanitized) — correctly out of scope for 011-02 (ADR scopes
  untrusted-text handling to 011-03; artifact is human-reviewed; provenance recorded to enable
  downstream treatment). Track as an 011-03 concern.
- Slice IN_PROGRESS with unchecked DoD + ADR Proposed is consistent with a pre-landing slice.

Reviewer: jig:reviewer (independent craft / pr-review pass, applying the installed pr-review
SKILL.md). Context: 111 heartbeat tests green; ruff 0.15.17 clean.
