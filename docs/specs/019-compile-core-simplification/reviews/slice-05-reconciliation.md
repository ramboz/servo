---
slice: 019-05 — single-component-oracle
pass: reconciliation
verdict: pass
reviewer: jig:reviewer (independent read-only subagent)
reviewed_at: 2026-07-02T18:50:06Z
prompt_source: review.py reconciliation
---

VERDICT: pass

REASONING:
All three named reconciliation fixes are real and accurate: README.md and
templates/oracle.sh.template correctly describe the runtime branch (single-component
direct-compare vs. >=2-component weighted average). The new test
test_rendered_single_component_oracle_shellcheck_clean is genuinely differentiated
from the multi-detector fixture -- it seeds only one detector and asserts exactly
one COMPONENTS entry rendered. The docs/memory/learnings.md PYTHONUTF8=1 entry
matches the deviation log. The "Primer surfaces: deferred" disposition is
corroborated by spec.md's status and the board showing 019-02/019-03 still open.

One nit found: docs/architecture.md's "Composite weighting heuristic" open-question
note still framed weighted-average as the sole scoring approach without mentioning
019-05's single-component branch. Fixed with a one-line addendum during this
reconciliation pass; the sweep table's docs/architecture.md disposition updated
from no-op to updated accordingly.

RECONCILIATION NOTES:
No further deviations. The stale docs/specs/README.md board row and REVIEWED
frontmatter are consistent with the documented lifecycle -- not a defect, just
pending close-out (board regen happens next).
