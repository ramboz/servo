---
slice: 036-03 - static-source-contract-app
pass: compliance
verdict: needs-changes
reviewer: jig:reviewer/036-03-final-compliance
reviewed_at: 2026-10-20T14:35:16Z
prompt_source: review.py implementation; exact2cd integration-base qualification; actual c2c9 native526 evidence and d38 independent byte audit
---

VERDICT: needs-changes

REASONING:
AC1-3 and AC5-6 have substantive implementation, test and retained native evidence: Dashboard 16/4, independent control 15/15, Bug006 refusal/restoration, and output/currentness controls. However, AC4's visibility logic can classify a browser-visible binding as a conclusive failure, despite the successful finite controls. AC7's boundaries are honestly disclosed; this review inspected source and selected retained records without rerunning evaluations or treating parent verification as lifecycle approval.

SPECIFIC ISSUES:
- skills/design-eval/static_contract.py:208,254 - [High confidence] Both visibility walkers reject any ancestor whose computed visibility is hidden. CSS permits a descendant to override this with visibility:visible: a correctly bound visible heading inside a hidden wrapper therefore receives visible:false and conclusive failures at line 135. Check effective visibility at the element/text node rather than treating ancestor visibility as non-overridable; cover this positive case in browser tests.

RECONCILIATION NOTES:
Preserve expected Jig NONCLEARANCE for actual vellum-confirmed-source/0.2 / static_source_contract_evidence: the existing Jig pure-consumer negative remains unexecuted, an integration gap, not bridge DONE. Preserve historical evidence and renew exact helper approvals/evidence after correction rather than rebinding old results. Craft/architecture reviews, reconciliation, lifecycle gates and publication remain; no full-app, visual, backend, actual-face, Jig DONE or merge approval is conveyed.
