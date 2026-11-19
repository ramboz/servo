---
slice: 044-01 — required-policy-evaluable
pass: craft
verdict: pass
reviewer: pr-review
reviewed_at: 2026-11-19T21:12:58Z
prompt_source: review.py pr-review docs/specs/044-required-policy-evaluability/spec.md 044-01 <deliverables> --richer-skill none
substrate: non-interactive
---

VERDICT: pass

Fresh `general-purpose` craft reviewer (pr-review, jig baseline buckets;
`--richer-skill none`), read-only, at HEAD 4fcf531. No blockers — the gate clears.

Five `[strength]` entries: (1) RequiredPolicyFailClosedTests pairs a
baseline-credited anchor with AC4 a–i one-knob-per-predicate fixtures on a
signal-only target, so every fail-closed test is non-vacuous by construction;
(2) `_oracle_pin_matches` + the L2 `entry == binding` deep-equality precisely
mirror score-time liveness (driver_seal oracle.sh-pin + required_runtime binding
identity), with `test_h` witnessing the regenerated-`oracle.sh` honest-drift
state; (3) byte-identity is structural (`policy_evaluable` is a threaded kwarg
never persisted; `ac_counts.evaluable` keeps the AC-only count); (4) every new
helper swallows its own OSError/ValueError and `_required_policy_evaluable`
returns only True/False, so the leg can never turn a bad artifact into an
env-error or torn write (path safety via resolve + is_relative_to); (5) approach
mirrors 030-01's `eval_signal` threading as the spec prescribes.

Three non-blocking `[nit][impl]` entries, ALL APPLIED in reconciliation:
- `_read_frontmatter_scalar`'s `^\s*` matched an indented (non-top-level) key,
  contradicting its "single top-level scalar" docstring → tightened the regex to
  reject leading indentation (top-level only); added an indented-key test case.
- The "+1 policy credit" arithmetic was spread across 3 sites (analyze,
  `_run_analyze`, `_rule_table`) → extracted a single `_policy_credit()` helper
  (ADR-0002 third-caller) so the credit's value cannot drift.
- A few defensive sub-branches were not individually witnessed → added
  `test_j_binding_kind_wrong`, `test_k_malformed_required_policy_json`,
  `test_l_components_not_a_list`, `test_m_non_string_check_id`.

Post-fix: 130 tests pass, ruff clean, host packages rebuilt + in sync.

RECONCILIATION NOTES: no blockers; the three nits above are folded into the
deviation log. Out-of-scope FYI (not this slice): SKILL.md drift across host
mirrors is pre-existing host-adaptation (per-host frontmatter + plugin-root path),
not introduced here; the 044 body additions are consistent across all copies.
