---
slice: 043-04 — lift the Copilot kill-resume fail-closed
pass: compliance
verdict: pass
reviewer: general-purpose
reviewed_at: 2026-11-16T02:11:30Z
prompt_source: review.py implementation (R1+R2)
---

**VERDICT: PASS** (compliance, round 2 — fresh general-purpose reviewer, no `[blocker]`).

All six acceptance criteria are met by the implementation, with meaningful
(non-vacuous) tests at the unit and cross-process-e2e levels.

- **AC1** — `_COPILOT_BASELINE_RECOVERABLE_HALTS = {interrupted, ""}`; each carries
  a sound stale baseline. `credit_usage_unavailable` correctly falls to the else
  branch (always nulls its baseline) and is tracked as a deferred follow-up in
  `docs/refinement-todo.md`. `None` stays refused. Covered by the admit +
  non-recoverable refusal tests.
- **AC2** — recovery sets `cumulative_credits_nano = R` (the resumed
  session-cumulative) absolutely and records the OTel Σ (N) as the iteration
  spend; verified ≠ R−stale and ≠ stale+N by `test_recovery_sets_absolute_cumulative`
  (100cr not 50cr) and `test_kill_resume_recovers_baseline_from_resumed_read`
  (105cr exactly, asserting ≠90 orphan-drop and ≠the 55≠40 delta-failure).
- **AC3** — the distinct `credit_baseline_unavailable` reason is preserved on every
  fail-closed branch: preflight (no-session / unsound-baseline) and runtime
  (partial read / missing OTel / fork-fresh floor / unresumable-invoke). The
  fork-fresh guard is the literal `nano - otel_nano < (prior ...)` floor plus (in
  the final code) the non-positive-prior rejection.
- **AC4** — post-iteration ceiling and next-iteration ≥30-credit floor both read
  `state["cumulative_credits_nano"]`, which recovery set to R; the first resumed
  iteration's pre-iteration cap uses the stale B before R is known, per A2.
  Confirmed by `test_kill_resume_post_iteration_ceiling_on_recovered_baseline`.
- **AC5** — clean halts take the `_COPILOT_RESUMABLE_HALTS` branch, never set the
  recovery flag, still require a sound baseline, use the normal delta
  reconciliation; `test_clean_halt_resume_unchanged_by_recovery_path` proves a
  clean halt with an injected orphan halts `credit_usage_unavailable` (NOT absorbed
  by recovery).
- **AC6** — the `backend_mismatch` / `state_schema_version == 2` refusal runs before
  the credit-guard block; order preserved, absent from the diff.

**Vacuous-test check:** the floor tests (`test_recover_mode_floor_rejects_fork_fresh`,
`test_kill_resume_fail_closed_on_fork_fresh_session`) genuinely fail if the floor
guard is removed (recovery would succeed and the assertions flip). The recover-mode
missing-OTel / missing-usage / partial-status / N>R tests each exercise distinct
fail-closed branches.

**Verification run:** `test_copilot_capability.py` 13 passed/48 subtests; the
043-04 cross-process/recover subset 16 passed; full both-file baseline 643 passed,
exit 0. Host-sync `build_host_packages.py --check` → in sync (loop.py byte-identical
across the three host trees). Ruff `--target-version py39` clean (no bare PEP-604).

**Non-blocking observations (deviation-log material):** the partial-read recovery
failure did not pop the one-shot recovery flag (harmless self-healing; addressed in
the final code); and the fork-fresh floor `>= B` degenerates at `B == 0` (addressed
structurally in the final code by the `R − N > 0` clause). No principle violation;
deterministic fail-closed arithmetic; no module-boundary / public-contract change
(`arch_review: false`, consistent with 043-03).
