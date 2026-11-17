---
slice: 043-05 — recover the Copilot kill-resume baseline from a persisted sound floor
pass: compliance
verdict: pass
reviewer: general-purpose
reviewed_at: 2026-11-16T17:21:27Z
prompt_source: review.py implementation (R1 needs-changes + R2)
---

**VERDICT: PASS** (compliance, round 2 — fresh general-purpose reviewer, no `[blocker]`).

Round 1 found all six ACs functionally met and correct, with one gating `[blocker]`: AC3 requires the last-sound floor stamped at **both** null sites, but the invoke-failure null site (the `claude_data is None` Copilot branch — the SIGKILL/OOM production path) had no non-vacuous test; the `_apply` partial-report site was already covered. R2 confirms the fix.

- **Blocker resolved (empirically verified non-vacuous):** `test_invoke_failure_persists_last_sound_floor_at_real_site` drives a genuine fresh-run iteration-2 invoke failure (`_mock_copilot_cumulative([50cr,40cr], fail_on=2)`, `--max-iterations 2`): iteration 1 succeeds (sound cumulative 50cr), iteration 2's invoke emits no parseable event → `claude_data is None` → the invoke-failure branch → `_persist_last_sound_cumulative` stamps 50cr before the null. R2 mirrored loop.py, deleted only that site's persist line, and confirmed the new test FAILS (`None != 50000000000`) while the faked-kill e2e still passes — isolating exactly the R1 gap. Both null sites now stamp the floor.
- **All six ACs met, no regressions:** full suite 661 passed / 113 subtests. AC1 preflight admit (session + sound floor → defer via `credit_baseline_recovery_pending`); AC2/AC5 floor-sourced recovery + null-safe pre-iteration cap (recovery sets cumulative to R absolutely, retires the floor); AC4 fail-closed (no-session / unsound-floor / fork-fresh); AC6 scope (the three halt frozensets disjoint, 043-04's sets untouched). loop.py byte-identical across the three host trees; ruff clean; refinement-todo item RESOLVED.
- **DoR tweak accurate** — splitting `credit_usage_unavailable` into the invoke-failure sub-case (probe-grounded) and the partial-report sub-case (ADR-0048 A2 additivity) matches the code and proof leg 2.
