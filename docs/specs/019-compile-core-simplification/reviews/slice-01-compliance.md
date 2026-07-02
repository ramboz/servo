---
slice: 019-01 — freeze-parsed-acs
pass: compliance
verdict: pass
reviewer: jig:reviewer (independent read-only subagent)
reviewed_at: 2026-07-02T18:38:56Z
prompt_source: review.py implementation (jig:spec-workflow compliance pass, re-run after doc-drift fix)
---

VERDICT: pass

REASONING:
All 5 ACs are met with meaningful, non-superficial test coverage -- including
subprocess-level CLI round trips (not just unit calls) for the approve->freeze
consistency check (AC4) and living-document mutation scenarios (AC1). The two
previously-flagged stale doc surfaces (SKILL.md and docs/architecture.md) now
accurately describe the new behavior, and the historical 006-04 slice doc was
given a well-scoped amendment rather than being silently rewritten.
oracle_overlay.py::approve's out-of-scope one-time source-hash check was correctly
left untouched.

SPECIFIC ISSUES:
- skills/spec-oracle/checks.py:829-833 -- _ac_sort_key returns item.get("id", "")
  without coercing to str; a hand-edited checks.json with a non-string id (e.g. an
  int) mixed with string ids from other items raises an unhandled TypeError from
  sorted() in plan_content_hash, uncaught anywhere in main()'s --enforce-freeze
  path -- crashes with a raw traceback instead of the module's normal
  env_error/exit-2 convention. (Medium confidence -- checks.json is documented as
  a "reviewed, frozen artifact," so likelihood is low, but the fix is a one-line
  str(item.get("id", "")) and worth doing given the module's stated posture of
  defensive handling elsewhere.)

RECONCILIATION NOTES:
- The historical docs/specs/006-spec-oracle/slice-04-freeze-and-controls.md was
  left with its original AC2 text describing the raw-file hash gate, but a new
  Amendments section (2026-07-02) was appended pointing to ADR-0022/019-01 as the
  current authority -- deliberate, well-scoped, preserve-history choice.
- The _ac_sort_key non-string-id edge case should be either accepted as a known v1
  limitation or queued to docs/refinement-todo.md.
