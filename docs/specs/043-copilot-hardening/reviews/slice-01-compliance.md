---
slice: 043-01 — refuse known-USD-priced oracle components under Copilot
pass: compliance
verdict: pass
reviewer: general-purpose
reviewed_at: 2026-11-14T01:41:02Z
prompt_source: review.py implementation spec.md 043-01 loop.py test_usd_priced_oracle.py
---

VERDICT: pass (round 1)

All 5 acceptance criteria of slice 043-01 are met, with non-vacuous tests.

- AC1 (marker reader + validator) — MET. `_usd_priced_oracle_error` reads
  `usd_priced_components`, validated as a unique list of nonempty names that is a
  subset of `components`, fail-closed on malformed. `test_marker_protocol`
  (PROTOCOL_CASES) covers absent/empty→None, valid→refuse, ~20 malformed/subset
  violations→invalid.
- AC2 (copilot refuse, fail-closed, distinct reason naming components + ADR-0048
  part 5) — MET. Preflight gated to HOST_COPILOT → `_refuse_preflight` →
  rc=EXIT_ENV_ERROR(2), same as the existing launch-refusal; message lists the
  offending components and cites "ADR-0048 part 5"; reason
  `usd_priced_oracle_components` ≠ `unpriced_oracle_components`. `forbid()` +
  `snapshot(target)==before` prove no subprocess / no run-dir write before refusal.
- AC3 (independent of credit-ceiling value) — MET. Preflight takes no
  credit_ceiling; `test_run_loop_refuses_under_copilot_any_credit_ceiling`
  parametrizes [30,100,1000,30.5].
- AC4 (claude + non-null cost_ceiling unaffected) — MET. Preflight returns None
  when host != HOST_COPILOT; `test_run_loop_claude_passes_gate_to_signal_install`
  uses a sentinel to prove control reaches `_install_signal_handlers` (gate is a
  genuine no-op, not mocked away).
- AC5 (unpriced path unchanged; both refusals separately identifiable) — MET.
  `_unpriced_oracle_error` untouched; `test_reasons_are_distinct`,
  `test_reader_is_host_agnostic_and_independent_of_unpriced`,
  `test_both_markers_under_copilot_unpriced_takes_precedence` (asserts
  `"usd_priced_components" not in captured.err` when unpriced fires).

Full suite green; three host copies byte-identical (`build_host_packages.py
--check` in sync). No bugs/edge cases found. Open items are DRAFT→close-out
bookkeeping (refinement-todo item 2 → resolved; deviation log/sweep), not AC
failures. Benign ordering note (not an issue): under copilot with no credit
ceiling the `_refuse_copilot_capability` gate pre-empts the usd_priced refusal —
the run is still refused fail-closed, no unbounded-USD hole; the usd_priced reason
surfaces on the normal copilot launch (credit ceiling supplied).
