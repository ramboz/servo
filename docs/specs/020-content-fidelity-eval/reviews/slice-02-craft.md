---
slice: 020-02 — content-fidelity-skill
pass: craft
verdict: pass
reviewer: jig:reviewer
reviewed_at: 2026-07-04T04:04:20Z
prompt_source: review.py pr-review docs/specs/020-content-fidelity-eval/spec.md 020-02 ...
---

VERDICT: pass (round 2, after a blocker fix)

Round 1 blocker: AC2 requires a case's "artifact source" to be pinned and
sha256-hashed as part of the definition, but the source descriptor
(file/command config) wasn't included in definition_hash, so a project could
silently swap it post-freeze with no stale refusal -- an integrity gap.
Fixed by splitting the single field-list constant into _REFERENCE_FILE_FIELDS
(artifact_hashes, on-disk content hashing -- unchanged) and _CASE_PIN_FIELDS
(definition_hash/validate_freeze, value-pinning, now includes "source").
Three new tests verify the split correctly: source changes now refuse as
stale, while source's target content is still correctly never content-hashed
(it's the moving artifact under test). Non-degenerate fixtures confirmed the
tests exercise real divergence, not coincidence.
