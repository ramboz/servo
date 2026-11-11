---
slice: 038-02 — role model placement
pass: frame-critique
verdict: pass
reviewer: jig:reviewer
reviewed_at: 2026-11-10T19:46:32Z
prompt_source: review.py frame-critique docs/specs/038-per-node-model-tiering/spec.md 038-02 (round 2)
---

VERDICT: pass

REASONING:
Round 2. The split is no longer keyed on model equality; it is probe-grounded and applies whenever a models block is in effect, with the DoR now honest about ADR-0047's status. Remaining risk (the shared-lane judge gets no cache on every turn) was observed only for the judge's first turn; D2-A also rests on independence, an unchanged default and a cost-measuring kill criterion, so the work is not misdirected.

SPECIFIC ISSUES:
- [spec] Cache claim narrowed to the first judge turn; later judge turns re-read interleaved runner turns uncached; cache lifetime across real iterations not modelled (folded into spec/ADR/BR-2).
- [spec] Split is confounded with tiering for measurement — a block naming the default model explicitly gives a split-only baseline; documented in ADR kill criteria and the slice DoD (SKILL.md).
