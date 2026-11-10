---
slice: 038-01 — per-iteration accounting
pass: frame-critique
verdict: needs-changes
reviewer: jig:reviewer
reviewed_at: 2026-11-10T19:38:28Z
prompt_source: review.py frame-critique docs/specs/038-per-node-model-tiering/spec.md 038-01
---

VERDICT: needs-changes

REASONING:
Round 1. Unprobed sibling assumption: `--max-budget-usd` caps per-invocation spend on a resumed session (if session-scoped, the corrected cumulative would truncate iterations). Also the running-total proof was tuned on a single-turn probe.

SPECIFIC ISSUES:
- [spec] Probe --max-budget-usd scope on --resume (T > B > invocation cost).
- [spec] AC5 "argv byte-identical" contradicts AC3 (the --max-budget-usd value changes once cumulative is corrected).
- [spec] Proof test unverified on multi-turn invocations; failures invisible — record a cost basis.
