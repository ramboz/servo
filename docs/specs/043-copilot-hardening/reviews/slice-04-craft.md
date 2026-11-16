---
slice: 043-04 — lift the Copilot kill-resume fail-closed
pass: craft
verdict: pass
reviewer: general-purpose
reviewed_at: 2026-11-16T02:11:30Z
prompt_source: review.py pr-review --richer-skill none --non-interactive (R1+R2)
substrate: non-interactive
---

**VERDICT: PASS** (craft / pr-review, round 2 — fresh general-purpose reviewer, no `[blocker]`).

The round-2 tightening (fork-fresh floor, narrowed recoverable set `{interrupted, ""}`
with `credit_usage_unavailable` deferred, preflight fail-closed on unsound baseline,
distinct `credit_baseline_unavailable` reason) is sound, minimal, and well-documented.
The recovery arithmetic matches the probe (returns N as the iteration spend, sets the
cumulative to R absolutely).

**Checks performed:** ruff pinned 0.15.17 → all checks passed; host-sync → the three
host-tree loop.py copies byte-identical to source; the 043-04 cases + the Copilot
credit/resume suites green (ran them); no 043-03 regression.

**Craft findings:**
- Floor guard placement and comment are clear and accurate; it subsumes the N>R
  incoherent case.
- The three-way preflight guard (A clean / B recoverable / C other) is readable;
  `baseline_sound` / `has_session` computed once, branches disjoint, the recovery
  flag cleared on every non-recovery branch.
- The `_COPILOT_BASELINE_RECOVERABLE_HALTS` comment and the spec's
  Decisions-needed / Assumptions are accurate and carefully hedged — NOT over-claimed
  (A1 disclaims a cryptographic/adversarial guarantee; the refinement-todo precisely
  scopes the deferred `credit_usage_unavailable` gap).
- Reusing `prior_cumulative_nano` as the floor (rather than a new parameter) is clear,
  not confusing — both sides of the comparison are the same quantity computed two ways,
  and the docstring calls it out.
- The fork-fresh fixture `_simulate_kill(fork_fresh=True)` is faithful (resets the mock
  billing accumulator to 0 → R = N → recovered prior 0).

**Strengths:** the fork-fresh guard reuses the clean-path reconciliation as a floor
(`≥` not `==`) with no new parameter; the recovery-pending flag is cleared on every
non-recovery branch (good state hygiene); exceptional doc honesty; the distinct
`credit_baseline_unavailable` reason separates recovery failures from
`credit_usage_unavailable` for operators and tests; `test_clean_halt_resume_unchanged_by_recovery_path`
guards the recovery path from masking a real reconciliation failure on a clean halt.

**Nits (non-blocking, deviation-log material):**
1. the recovery-pending flag was not popped on the two runtime fail-closed paths
   (partial-read; invoke-failure) — self-healing, no correctness impact; a one-line pop
   would tidy it (**folded in the final code**).
2. the floor's `(prior_cumulative_nano or 0)` depends on a non-None prior (guaranteed by
   preflight branch B); a clarifying comment would help (**folded**).
3. `import glob` is function-local in `_simulate_kill` — purely stylistic, and
   consistent with the sibling `_state()` helper; left as-is.

**Observation (no action):** recover mode necessarily drops the clean-path
`otel == R − prior` equality check for the single discovery iteration (a stale prior
gives no sound `expected`), trusting N under the floor only — inherent to
resume-after-kill, bounded to one iteration, documented in A1/A2; equality
reconciliation resumes from iteration 2.
