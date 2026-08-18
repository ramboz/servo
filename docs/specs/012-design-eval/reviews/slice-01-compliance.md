---
slice: 012-01 — freeze-and-aggregation-core
pass: compliance
verdict: pass
reviewer: jig:reviewer
reviewed_at: 2026-08-18T22:47:28Z
prompt_source: independent subagent review (spec-012 retro-ceremony, round 2 after needs-changes)
---

VERDICT: pass

Round 2, after a round-1 `needs-changes`. All five ACs met and independently
verifiable in the committed code.

Round 1 blocked on AC1 describing behaviour `definition_hash` does not have
(it does not hash the rubric — `_common/fidelity_eval.py:87-101`), and on
`capture_app`'s three `EnvError` branches being implemented but untested.
Both resolved: AC1/AC2 now split the frozen definition correctly between
`definition_hash` (judge, samples, threshold, viewport, screen set) and
`artifact_hashes` (inline rubric text + per-screen files), and
`CaptureAppHonestyTests` + `MalformedDefinitionHonestyTests` cover the
capture-failure and malformed-config paths. `main()` now catches
(OSError, ValueError, KeyError, TypeError) so a bad definition surfaces as
`design-eval: env_error — …` rather than a traceback; rc 2 with empty stdout
is asserted on both refusal paths — never a silent 0.0.

DoD count verified accurate: Aggregation 4 + Freeze 8 + ScoreHonesty 3 +
CaptureAppHonesty 3 + MalformedDefinition 2 = 20.
