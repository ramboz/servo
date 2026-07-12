---
slice: 008-04 — frozen-params-and-emit
pass: craft
verdict: pass
reviewer: jig:reviewer
reviewed_at: 2026-07-12T16:25:51Z
prompt_source: review.py pr-review ... 008-04
---

VERDICT: pass

Faithful reuse of fidelity_eval.py; mirrors content_fidelity.py freeze/install/uninstall
with no parallel harness. `emit` collapses freeze + optional --target install into one
verb (matches the spec's `emit`). validate_freeze correctly wired into score() (008-03
carry-forward); vendored-DSL duplication well-justified + behaviorally guarded;
spec-id-namespaced component_name resolves the collision; weight guard sound; the
inverted 008-03 placeholder test is a legitimate consequence of AC5 now enforcing freeze.
Strong AC6 evidence (real gate.py over the real oracle.sh driver). No blockers.

Nits → reconciliation: DSL drift-guard pins a narrow input space + the two EnvError
classes differ (1-arg vs 2-arg); `_case_weight` invoked twice per case (redundant);
uninstall_target validates spec_id explicitly while emit_target validates indirectly.
Founded architectural deviation (self-install via harness, no spec-006 step) + the added
`uninstall` verb should be logged.
