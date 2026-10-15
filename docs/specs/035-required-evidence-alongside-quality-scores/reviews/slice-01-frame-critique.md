---
slice: 035-01 - installed-required-gate
pass: frame-critique
verdict: pass
reviewer: jig:reviewer / servo-proposal-frame (fresh context)
reviewed_at: 2026-10-14T23:59:07Z
prompt_source: review.py frame-critique docs/specs/035-required-evidence-alongside-quality-scores/spec.md 035-01 docs/specs/035-required-evidence-alongside-quality-scores/spec.md docs/specs/035-required-evidence-alongside-quality-scores/plan.md docs/specs/035-required-evidence-alongside-quality-scores/tasks.md
---

VERDICT: pass

REASONING:
The load-bearing assumption is that existing component seams can produce a score and complete required evidence from the same invocation without concurrent-run aliasing. Existing checks already produce structured outcomes; invocation binding and atomic publication are correctly treated as additional work requiring installed controls. The proposed policy prevents high quality, zero weight or THRESHOLD=0 from waiving a failure, while missing, stale or incomplete evidence refuses.

SPECIFIC ISSUES:
None identified by the fresh-context frame reviewer.

RECONCILIATION NOTES:
No deviation identified. Single-invocation/concurrency proof and explicit migration remain pending implementation obligations, not evidence obtained here (docs/specs/035-required-evidence-alongside-quality-scores/slice-01-installed-required-gate.md:40-46,53-62).
