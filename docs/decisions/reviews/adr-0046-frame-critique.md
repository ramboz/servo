---
adr: 0046
pass: frame-critique
verdict: pass
reviewer: jig:reviewer static-evidence-frame-review
reviewed_at: 2026-10-22T18:00:40Z
prompt_source: review.py frame-critique docs/decisions/adr-0045-component-agnostic-static-evidence.md (identity-only move to ADR-0046 afterward)
---

VERDICT: pass

REASONING:
The highest-risk assumption is that pilot-specific behavior can be removed without changing the bounded observer/source semantics. The cited f0041335 source supports the observer side: comparison consumes supplied policy, and bindings derive roles from that policy (static_contract.py:110-200,617-640). Producer-side neutrality remains unverified, but Spec 037 explicitly makes verification an integration prerequisite, and the ADR prohibits shipping workarounds that would invalidate the premise; this survives as a bounded decision, not established end-to-end reuse.

SPECIFIC ISSUES:
- Non-blocking residual: the clean producer must preserve source semantics while accepting non-card inventories. The inspected predecessor still pins approved_card.py (f0041335, skills/design-eval/static_contract.py:516), so manifest-driven observer logic alone does not establish producer independence. If neutral extraction requires new source semantics or retained component policy, helper-only reuse cannot deliver the promised workflow. Cite the verified successor cut and corresponding probe when available; spec 037 already requires verification before integration.

PROVENANCE:
Independent jig:reviewer frame-critique task static-evidence-frame-review returned pass on 2026-10-22. Reviewed as provisional ADR-0045; the coordinating session then directed an identity-only move to ADR-0046 to avoid ambiguity with the historical unmerged effort. Only the file name and ADR heading number changed; the decision text above was not changed.
