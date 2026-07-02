---
slice: 019-05 — single-component-oracle
pass: craft
verdict: pass
reviewer: jig:reviewer (independent read-only subagent)
reviewed_at: 2026-07-02T18:45:59Z
prompt_source: review.py pr-review
---

VERDICT: pass

REASONING:
The template change is scoped exactly as promised (only templates/oracle.sh.template's
aggregation section; gate.py and oracle_overlay.py are verifiably untouched), the
runtime branch is correct bash (consistent %.4f formatting between the
direct-compare and weighted-average paths, consistent quoting/rc-capture idiom
copied verbatim from the pre-existing branch, empty-array and zero-threshold edge
cases unaffected since they only ever reach the else branch), and the new tests
are genuinely load-bearing.

SPECIFIC ISSUES:
- [nit] templates/oracle.sh.template header comment described the composite as
  unconditionally a weighted average -- fixed during reconciliation.
- [nit] the shellcheck fixture only ever exercised the >=2-component branch --
  a single-detector fixture closing this gap was added during reconciliation.

RECONCILIATION NOTES:
- Strength: test_no_weighted_sum_arithmetic_on_taken_branch uses bash -x tracing
  and a carefully-crafted regex to prove the weighted-sum arithmetic path is not
  silently still happening -- good model for future tests of this shape.
- Strength: SingleToMultiComponentUpgradeTests exercises the exact DoR-flagged
  AC4 risk end-to-end via the real oracle_overlay.py::install regexes.
- No deviations from the spec/DoR beyond the two nits above, both closed during
  reconciliation.
