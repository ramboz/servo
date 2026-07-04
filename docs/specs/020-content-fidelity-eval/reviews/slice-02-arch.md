---
slice: 020-02 — content-fidelity-skill
pass: arch
verdict: pass
reviewer: jig:reviewer
reviewed_at: 2026-07-04T04:04:20Z
prompt_source: review.py arch-review docs/specs/020-content-fidelity-eval/spec.md 020-02 ...
---

VERDICT: pass (round 2, confirming a craft-flagged fix reconciles correctly)

Round 1: content-fidelity confirmed as a genuine second consumer of
skills/_common/fidelity_eval.py requiring zero changes to that module's
public API -- proving 020-01's generalization was real. A craft-review
[blocker] (source descriptor not pinned into definition_hash) was raised
independently; round 2 confirmed the fix correctly reconciles both concerns
simultaneously: source's descriptor (type/path/run) is now definition-pinned
via a new _CASE_PIN_FIELDS list (closing the blocker), while source's target
content remains correctly excluded from content-hashing via the separate,
unchanged _REFERENCE_FILE_FIELDS list (preserving "freeze the definition,
not the output"). Two independently-driven field lists, not one mechanism
serving two masters -- no remaining tension.
