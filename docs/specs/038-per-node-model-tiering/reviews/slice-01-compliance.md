---
slice: 038-01 — per-iteration accounting
pass: compliance
verdict: needs-changes
reviewer: jig:reviewer
reviewed_at: 2026-11-10T20:13:07Z
prompt_source: review.py implementation docs/specs/038-per-node-model-tiering/spec.md 038-01 <deliverables>
---

VERDICT: needs-changes

REASONING:
Round 1. Loop driver satisfies AC1/AC2/AC3/AC5/AC6 (delta proof, snapshot persistence, corrected --max-budget-usd, old-state fallback). AC4 partially met: goal-driver interrupt and goal_unavailable exits occur after a parsed result event but finalize without accounting keys. One AC3 conjunct (returned id == resumed id) has no isolating test.

SPECIFIC ISSUES:
- [impl] Goal accounting missing on post-parse interrupt / goal_unavailable exits (High).
- [impl] No test isolates the returned_id == resumed_session_id conjunct (Medium).
- [impl] Refusal-shape test calls _goal_summary directly; negative guards cannot satisfy the feature-removal DoD item (Medium).
- [impl] Delta-mode model_usage keeps zero-delta entries for unused models (Low/Medium).
- [impl] _as_number passes NaN/inf -> int() raises (Low).
