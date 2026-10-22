---
adr: 0045
pass: frame-critique
verdict: pass
reviewer: jig:reviewer/static-adr-final-frame
reviewed_at: 2026-10-19T19:52:49Z
prompt_source: review.py frame-critique ADR0045; final required-observation settlement clarification
---

VERDICT: pass

REASONING:
Changed-document scope reviewed: docs/decisions/adr-0045-finite-static-source-contract-app.md:69-74 and docs/specs/036-deterministic-design-evidence/static-app-contract.md:91-97, in context of both current documents. The load-bearing assumption is that the finite required observation vector can settle without whole-subtree stability. Unselected activity can affect required observations indirectly, but the protocol requires atomic required-property, correspondence and visibility sampling rather than excluding those effects. The frame survives; actual APP feasibility remains an implementation obligation, not established by this review or the reported isolated-browser controls.

SPECIFIC ISSUES:
- static-app-contract.md:91-105: Nonblocking residual: an unselected counter could change required text or fully clip a bound heading through reflow. Ignoring those effects would falsely establish settlement; the stated required-property/visibility boundary keeps them in scope, while allowing genuinely unrelated activity. Real-APP settlement remains unproved.

RECONCILIATION NOTES:
The clarification explicitly rejects whole-card descendant stability as an APP readiness condition; no further frame-level deviation identified. This pass does not accept the Proposed ADR or certify code, APP results, approvals or installed gates.

Provenance: genuine jig:reviewer/static-adr-final-frame, agent 5c65498b-0425-43b5-aeb4-d296366d1bc0, clarification refresh response. The reviewer lacked a hash/command tool. The orchestrator bound the unchanged reviewed document bytes before commit:
- ADR0045 SHA256 f7dd927c46d4ee41c4c053fd623b168f4af684729f351a38ce953f9dd3f4eebe.
- Protocol SHA256 067dab49b553e71af3f01d7facf8610d365edcc17f2d8aa894006b9d28ae6e85.

Hash-bound HUMAN acceptance remains outstanding. No approval or actual APP result is inferred from this frame review.

## Publication cleanup (2026-10-22)

The protocol and ADR context later had application-specific examples removed
at the owner's request. The hashes above identify only privately archived
historical originals, not the edited current documents. This historical review
is not a new acceptance or a rebinding of those hashes to reduced exports.
