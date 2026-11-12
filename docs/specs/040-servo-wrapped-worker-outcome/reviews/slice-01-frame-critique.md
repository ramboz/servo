---
slice: 040-01 — outcome line
pass: frame-critique
verdict: pass
reviewer: general-purpose
reviewed_at: 2026-11-12T18:10:35Z
prompt_source: review.py frame-critique docs/specs/040-servo-wrapped-worker-outcome/spec.md 040-01
---

VERDICT: pass (re-review, after the revision addressed the first-round `needs-changes`)

Round 1 (`needs-changes`) found the load-bearing A2 assumption — "`result` is a
faithful function of `terminal_reason` alone" — false: `max_iterations_reached` /
`oracle_plateau` / `cost_ceiling_reached` / `context_full` / goal
`iteration_cap_reached` are overloaded across (a) a clean below-threshold stop
(`final_oracle_status = below_threshold`, `EXIT_OK`) → genuinely budget/plateau,
and (b) a run whose oracle never produced a valid verdict
(`final_oracle_status ∈ {env_error, unknown_interrupted}`, `EXIT_ENV_ERROR`,
`required_evidence_unavailable` breadcrumb, loop.py:4105–4117) → actually error.
Reporting (b) as `budget` would re-dispatch a broken-oracle worker with a raised
ceiling — the wasted-spend failure spec 040 exists to kill.

Resolution (round 2, PASS): the A2 mapping now keys on
`(terminal_reason, final_oracle_status)` and demotes a budget/plateau terminal
with an `env_error`/`unknown_interrupted` oracle status to `error`, mirroring the
loop's own `unavailable` EXIT_ENV_ERROR branch. The reviewer verified the correct
cases hold at source (a real below-threshold stop stays plateau/budget; an
oracle that env-errored every iteration demotes to error). The secondary
`context_full` note is resolved: it stays in the `budget` family (a resource — the
context window — was exhausted) but the gloss now names its distinct lever
(compaction / larger-context model / decomposition), and `reason` is preserved
verbatim so the coordinator sees the specific lever.

Non-blocking note from round 2 (ADDRESSED by the implementer, not required for the
pass): the demotion originally applied to the whole budget row, which would have
wrongly demoted a `credit_ceiling_reached` halt that fires BEFORE any scoring
(fresh Copilot run, sub-floor `--credit-ceiling`, `iterations == 0`, default
`env_error` status) to `error`, contradicting the `credit_ceiling_reached → budget`
decision. Fix applied: the demotion is now gated on a scoring attempt
(`iterations ≥ 1`), so a pre-scoring starved budget halt stays `budget` while a
run whose oracle ran-but-errored becomes `error`. The slice prose + table and the
`_outcome_result(terminal_reason, final_oracle_status, iterations)` signature were
reconciled to match; a dedicated test (`test_starved_budget_halt_before_scoring_
stays_budget`) pins it.

Reviewer: general-purpose subagent (read-only), two rounds.
