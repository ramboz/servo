---
slice: 015-01 — verdict-contract
pass: craft
verdict: pass
reviewer: maintainer-self-review
reviewed_at: 2026-06-28T02:39:16Z
prompt_source: review.py pr-review docs/specs/015-edd-suitability/spec.md 015-01 skills/edd-suitability/suitability.py skills/edd-suitability/test_suitability.py (subagent declined; maintainer self-review)
---

VERDICT: pass

PROVENANCE NOTE:
Independent craft subagent was declined by the maintainer; this is a maintainer
self-review against sibling conventions. Independence is weaker than the
compliance pass (which ran as a fresh subagent). Flagged for transparency.

REASONING:
Scope matches the slice boundary exactly — emits + persists the verdict only,
wires no caller, leaves `missing_evidence` empty for 015-02. Craft follows servo
conventions (subprocess seam to oracle_plan.py with fixed/str-coerced args and no
shell; tmp + os.replace atomic write; importlib test-load idiom; iso_now matching
006). One consistency nit found and fixed during this pass.

SPECIFIC ISSUES:
- [nit][fixed] suitability.py main() — originally hand-rolled subcommand dispatch
  (manual argv[0] check) instead of the standard argparse add_subparsers +
  dispatch-on-args.command pattern used by heartbeat.py:2011 and gate.py. Refactored
  to the sibling idiom; tests + lint still green.
- [strength] suitability.py decide() — pure ordered rule table with a True
  catch-all makes the fail-closed default structurally guaranteed and exhaustive;
  unit-tested with an exhaustive truth-table grid.
- [strength] test_suitability.py — injects a deterministic oracle_plan stub via
  SERVO_SUITABILITY_ORACLE_PLAN AND keeps one real-classifier integration test,
  decoupling the rule-table tests from 006's classifier behavior while still
  exercising the live seam.

RECONCILIATION NOTES:
- The CLI-dispatch nit was fixed in-pass (no follow-up needed).
- Carry forward the two compliance-pass Low notes (manifest_malformed taxonomy
  extension; v1 lint-not-a-signal) into the deviation log.
