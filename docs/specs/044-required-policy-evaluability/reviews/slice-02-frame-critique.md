---
slice: 044-02 — required-policy-has-signal
pass: frame-critique
verdict: pass
reviewer: general-purpose
reviewed_at: 2026-11-20T01:00:56Z
prompt_source: review.py frame-critique docs/specs/044-required-policy-evaluability/spec.md 044-02 slice-02-required-policy-has-signal.md (R1 needs-changes → R2 pass, 2 fresh rounds)
---

Frame-critique ran TWO rounds against fresh, independent `general-purpose`
reviewers, each grounding its critique against the live `suitability.py`. The
decision frame — crediting the live required-policy check toward `has_signal` as a
low-tension corollary of ADR-0050 (no new ADR) — **held through both rounds**; the
load-bearing **safety claim was conceded in both**. R1 found the slice's
*self-description* understated; R2 passed on the corrected scope.

- **R1 (needs-changes):** conceded the safety frame — because the *same* single
  `policy_evaluable` boolean supplies both legs (`n_evaluable = n_evaluable_acs +
  _policy_credit(policy_evaluable)` AND the new `has_signal` disjunct), there is no
  state where the signal leg is met while evaluability is unmet, no new
  "all-residual + vacuous oracle" false pass, and the a-fortiori-from-030-01
  argument is sound; the env-error residual is 044-01's already-settled benign "no
  false green". ADR adjudication: still a slice-captured corollary (no new ADR).
  What did NOT survive: the slice described the change as "one `OR` term + removing
  dead `evaluable_required_policy_with_eval_signal` code" — **false against the
  live code**. `eval_only = has_signal and not det_signal` with `det_signal`
  tests/CI only (`_SIGNAL_KEYS`), so adding the disjunct alone leaves `eval_only`
  True on the vellum pairing; the code is dead only AFTER a deliberate
  `eval_only`/`_facts`/`render_human` reclassification of a live policy check into
  the deterministic-signal class, which also discharges the ADR-0033/g5
  counterweight advisory and needs the policy reason-code messages restructured for
  the new static-contract-only signal provenance. → Rewrote the slice with a "What
  the change actually is (honest scope)" section naming all four coordinated edits
  (all gated on `policy_evaluable` for byte-identity); corrected the dead-code
  sequencing; fixed AC1 (the new provenance-(c) message, not 044-01's "test/CI
  present" string); re-made the no-ADR argument on the accurate, larger scope.

- **R2 (PASS):** re-confirmed the safety claim is airtight against the live code
  (`:856` + `:858-861`: `policy_evaluable` both adds +1 to `n_evaluable` and is
  threaded into `decide`, so the signal leg can never be met while evaluability is
  unmet); verified the "dead code" claim is now correct (after the `eval_only`
  redefinition `policy_only_evaluable and eval_only` requires
  `policy_evaluable AND NOT policy_evaluable`); verified the motivating gap is real
  (the static-source-contract is an independent install path, not always paired
  with a judge); and verified the honest-scope edits match the module's actual
  structure. Two non-blocking notes, both applied before recording:
  1. PRIMARY (precision): the g5 "counterweight stand-down" justification
     overclaimed *mechanism-equivalence* ("the policy check IS the deterministic
     counterweight"). A required-policy check is a different, narrower mechanism —
     per ADR-0044 a separate pass/fail veto, not a composite-score component; per
     design-eval CSS-only, not whole-view fidelity. Reworded to the accurate basis:
     g5's trigger ("the judged eval is the *sole* signal / don't let a single judge
     carry the oracle") is simply **no longer met** once the policy check is a
     recognized deterministic signal — the advisory is suppressed by recomputing
     g5's condition over the widened signal set, not by mechanism-equivalence. And
     it is operationally inert (a non-blocking line on an already-`suitable`
     verdict; the Compile refusal path reads `missing_evidence` only on
     `verdict != "suitable"`), which firmly keeps it no-ADR.
  2. SECONDARY (craft): named the two module constants
     (`_POLICY_EVALUABLE_REASON_CODES` / `_EVAL_SIGNAL_REASON_CODES`, suitability.py
     ~130-139) that reference the removed code and must be updated in the honest-scope
     edit list.

Verdict: **pass.** The decision (credit the live required-policy check toward
`has_signal`, a corollary of ADR-0050, no new ADR) and its load-bearing safety
claim (the single `policy_evaluable` boolean couples both legs, so the signal leg
never stands alone) are sound and grounded in the live code; the honest scope is a
small coordinated set of pure-layer edits, all gated on `policy_evaluable` for
byte-identity. The integration is the implementing slice's work, under test.
