---
slice: 044-02 — required-policy-has-signal
pass: compliance
verdict: pass
reviewer: general-purpose
reviewed_at: 2026-11-20T02:02:12Z
prompt_source: review.py implementation docs/specs/044-required-policy-evaluability/spec.md 044-02 (compliance)
---

Compliance pass (fresh general-purpose reviewer, read-only, against committed HEAD + worktree).

VERDICT: pass

All six ACs met with substantively non-vacuous tests. The slice extends `has_signal`
to credit a live required-policy check via the *same* unchanged `policy_evaluable`
boolean that credits `n_evaluable`, so the signal leg can never be met while
evaluability is unmet (the load-bearing safety claim holds structurally).
Byte-identity for non-`fidelity_contract` specs is preserved both by construction
(all new logic gated on `policy_evaluable`, default False, never persisted) and by
the pre-existing `_GOLDEN_DECIDE` / `test_tests_ci_decide_byte_identical_to_pre_slice_golden`
fence (frozen pre-slice goldens). The removed `evaluable_required_policy_with_eval_signal`
code is genuinely unreachable (contradiction: `policy_only_evaluable` ⟹
policy_evaluable=True vs new `eval_only` ⟹ policy_evaluable=False) and fully
removed with no dangling references. Full suite green (3161 passed, 10 skipped,
415 subtests); ruff clean; 3.9 floor respected; host-package drift clean.

Per-AC: AC1 (static-contract-only → suitable) MET + non-vacuous (deleting the
`or policy_evaluable` disjunct flips to needs_evidence); AC2 (existing sources
unchanged) MET, judge-exclusion by construction; AC3 (non-live floor fail-closed)
MET via a mutation matrix; AC4 (byte-identity non-fc) MET strongly (golden fence +
the new judged-only-with/without-live-static isolator is strongly non-vacuous);
AC5 (vellum pairing + dead code) MET (updated 044-01 test + DeadReasonCodeUnreachableTests);
AC6 (docs) MET. Principles: aligns with "oracle is the source of truth, never the
transcript-only judge". ADR signal: the no-new-ADR corollary claim is defensible and
the code does not contradict it; frame-critique (R1→R2) independently confirmed the
coupling and unreachability.

Two minor NON-BLOCKING issues (no AC failure), both resolved in reconciliation:
1. AC1's prose said "the identical fixture was needs_evidence before this slice — a
   companion pins that delta," but the companion (declare=False) yields
   unsuitable(all_acs_residual_no_signal), pinning that the DECLARATION is
   load-bearing. The literal pre-slice needs_evidence state is now unreachable (the
   coupling is the point). → AC1 prose reworded to describe this accurately (the
   delta is pinned by the positive test's has_signal/policy_evaluable assertions +
   the declaration-discriminator companion).
2. AC3 enumerates five breaks incl. "unsafe path"; the test covers four; AC says
   "a representative set" and the declared-path-traversal case is covered by
   044-01's reused `_safe_target_relpath` / `_required_policy_evaluable` tests
   (predicate reused unchanged). → AC3 prose reworded to note this coverage.
