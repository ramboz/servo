---
slice: 044-01 — required-policy-evaluable
pass: compliance
verdict: pass
reviewer: general-purpose
reviewed_at: 2026-11-19T21:01:19Z
prompt_source: review.py implementation docs/specs/044-required-policy-evaluability/spec.md 044-01 <deliverables>
---

VERDICT: pass

Fresh `general-purpose` compliance reviewer, read-only, reasoning from git HEAD.
Verified every acceptance criterion (AC1, AC2, AC3, AC3b, AC4, AC5, AC6) against
the code and empirically:

- `_required_policy_evaluable` credits `n_evaluable` only from a spec-declared
  `fidelity_contract` binding resolving to a live `family: command` floor; its
  two-layer L1/L2 liveness check faithfully mirrors the real score-time code
  (`driver_seal` oracle.sh pin ~911–925, `installed_policy` 504–518, `oracle`
  binding-identity 778–779, `file_hash` `sha256:` format).
- The stochastic `design_fidelity` judge is excluded by construction (reads only
  the deterministic check plan + install manifests, never `install.json`
  `components`); non-`fidelity_contract` specs stay byte-identical
  (`policy_evaluable` defaults False, never persisted; `ac_counts.evaluable`
  keeps the AC count).
- **Vacuous-test check (central):** independently mutated a scratchpad copy
  (repo untouched) — neutering the L1 oracle.sh pin reds `test_h`, dropping the
  L2 `entry == binding` identity reds `test_i`, and neutering the per-spec
  declaration gate reds both AC3 attribution tests. The AC4 fixtures are
  non-vacuous (anchored by `test_baseline_live_contract_is_credited`).
- 125 tests pass, ruff clean, Python 3.9 floor respected, host packages in sync.
- No design-principle violations; approach matches the spec's stated approach
  (the `policy_evaluable` kwarg mirrors 030-01's `eval_signal`).

SPECIFIC ISSUES (none blocking):
- [nit] The mixed case (a spec with >=1 evaluable AC AND a declared live
  `fidelity_contract`) was verified correct by reading the code but had no
  dedicated test (optional coverage nicety, not a defect).

Applied after this pass: added `test_mixed_evaluable_ac_and_live_contract_keeps_ac_code`
closing that coverage nicety (asserts the decided code stays AC-based
`evaluable_acs_with_eval_signal` with the policy credit a non-decisive bonus, and
the `_facts` suffix still notes the policy check). Suite now 126 green, ruff clean,
host packages still in sync.

RECONCILIATION NOTES: None — the implementation follows the spec's stated approach
without deviation.
