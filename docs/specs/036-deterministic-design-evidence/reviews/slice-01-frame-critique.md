---
slice: 036-01 - bound-card-evidence
pass: frame-critique
verdict: pass
reviewer: jig:reviewer / servo-band-binding-frame (fresh context)
reviewed_at: 2026-10-15T00:53:49Z
prompt_source: review.py frame-critique docs/specs/036-deterministic-design-evidence/spec.md 036-01 docs/specs/036-deterministic-design-evidence/spec.md docs/specs/036-deterministic-design-evidence/plan.md docs/specs/036-deterministic-design-evidence/tasks.md
---

VERDICT: pass

REASONING:
The highest-risk assumption, equal declared card and band widths permit interchangeable evidence, is explicitly rejected: spec.md:116-123 and slice-01-bound-card-evidence.md:46-57 require state-specific band observations through approved bindings. The slice's lines 74-89 require card240/band242 failures despite quality0.99/THRESHOLD=0, band-based geometry boundaries, and refusal for missing-band/card-only evidence. spec.md:151-156 preserves generic versus quoted named CSS-family semantics, disclaims rendered-face detection, and leaves normalizer/vector ownership with Vellum rather than defining a competing normalizer. Ordering, owner approval, schema separation, overall-gate authority and 0/1/2 outcomes remain explicit; this verdict covers only the affected pre-implementation frame.

SPECIFIC ISSUES:
No consumer-frame issues reported.

RECONCILIATION NOTES:
No consumer-frame deviations found. The fetched vellum-c0-453945c.txt:106 still contains the overbroad quote-stripping equivalence vector; its exact correction and revision-bound owner approval remain Vellum's responsibility before C0 clears, as required by docs/specs/036-deterministic-design-evidence/spec.md:155-156. The appendix remains proposed/unapproved.
