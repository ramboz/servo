---
slice: 008-03 — reference-set
pass: craft
verdict: pass
reviewer: jig:reviewer
reviewed_at: 2026-07-12T15:41:51Z
prompt_source: review.py pr-review ... 008-03 (re-review)
---

VERDICT: pass

Craft re-review after fixes. The new composite `score()` is correct and faithful to
content-fidelity/score.py: skip_case excluded from denominator, conservative
lower-bound aggregation, documented hard-constraint gate, uniform
EnvError-never-silent-0.0. The two prior DSL nits are resolved + tested (`==`
preserves `version == 3.10` as a string; `>=`/`<=` reject non-numeric operands at
parse time). Cross-module DSL reuse is a same-skill-dir load (not the forbidden
cross-skill import) and documented; `_gather_candidate` always-raises is an honest
008-04 seam. No blockers.

Strengths: differential skip_case proof; single-exception-type discipline across
the two EnvError classes; honest missing-capability seam.

Nits → carry-forward to 008-04: `weight` used but unvalidated (guard on live path);
composite-level tests only use weight 1.0 (mixed-weight + total_w<=0 + composite
constraints-without-actuals paths untested); `==` is stringly-typed by design —
flag for 008-04's numeric actual-value extraction; the cross-module DSL import must
be resolved if 008-04 copies score.py standalone into a target's `.servo/`.
