---
slice: 015-02 — missing-evidence
pass: craft
verdict: pass
reviewer: maintainer-self-review
reviewed_at: 2026-06-28T03:24:00Z
prompt_source: review.py pr-review docs/specs/015-edd-suitability/spec.md 015-02 skills/edd-suitability/suitability.py skills/edd-suitability/test_suitability.py (independent compliance subagent ran; craft is maintainer self-review)
---

VERDICT: pass

PROVENANCE NOTE:
The compliance pass ran as a fresh independent subagent; this craft pass is a
maintainer self-review against sibling conventions. Independence is weaker than
the compliance pass — flagged for transparency (mirrors 015-01's craft posture).

REASONING:
Scope matches the slice boundary exactly — populates `missing_evidence` and
makes it load-bearing for `needs_evidence` only; wires no caller (acting on the
list stays 015-03). The code reuses 015-01's pure-decision idiom: `decide()`
stays IO-free and deterministic, and `_missing_evidence()` is a sibling pure
helper with the same shape. The closed `MISSING_EVIDENCE_KINDS` tuple doubles as
the stable display order (taxonomy index, then detail), so re-runnability is a
property of the data structure, not bolted on.

CRAFT NOTES:
- Naming + structure follow the file's existing conventions (module-level closed
  tuple beside `_SIGNAL_KEYS`; helper above `decide()`; reasons as
  `{code, message}` objects per the 015-01 deviation).
- Coherence is structural, not coincidental: blocking items emit a paired
  `missing_<kind>` reason; advisory items deliberately do not. Both directions
  are tested.
- Details are genuinely actionable (each names a concrete "add …" step), not a
  vague "needs more" — satisfies the DoR's "concrete absent input" rule.
- The `oracle_signal` umbrella + advisory `tests`/`ci` choice is the honest model
  for "one signal suffices" and is documented in the deviation log.

No blocking craft issues. No new tech debt; no TODO/FIXME introduced.
