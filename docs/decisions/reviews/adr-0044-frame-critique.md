---
adr: 0044
pass: frame-critique
verdict: pass
reviewer: jig:reviewer / servo-proposal-frame (fresh context)
reviewed_at: 2026-10-14T23:59:06Z
prompt_source: review.py frame-critique docs/decisions/adr-0044-required-constraints-cannot-be-averaged-away.md
---

VERDICT: pass

REASONING:
The highest-risk assumption is that an independent required verdict can coexist with scalar scoring without consumers silently discarding its authority. The frame survives: it explicitly requires version-aware adoption, preserves default v1 behavior and closed 0/1/2 exits, and makes unavailable evidence override evaluated failure. Cross-project agreement and running-build verification remain prerequisites, not claimed capabilities.

SPECIFIC ISSUES:
None identified by the fresh-context frame reviewer.

RECONCILIATION NOTES:
No artifact-level deviation identified. Keep output adoption and Vellum/Jig contract pins unresolved until owner reconciliation (docs/decisions/adr-0044-required-constraints-cannot-be-averaged-away.md:144-151,169-173).
