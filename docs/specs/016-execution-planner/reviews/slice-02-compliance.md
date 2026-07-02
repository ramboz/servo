---
slice: 016-02 — run-consume
pass: compliance
verdict: pass
reviewer: general-purpose
reviewed_at: 2026-07-02T22:31:22Z
prompt_source: review.py implementation docs/specs/016-execution-planner/spec.md 016-02 (re-review after --background fix)
---

Compliance pass (`jig:independent-review`) on 016-02 — run-consume. Reviewer:
general-purpose (fresh, read-only, no implementation context).

**Verdict: PASS** (on re-review, after one fix cycle).

**First pass → needs-changes:** one Medium blocker — `--plan` + `--background`
silently dropped the plan's budget (the detached branch returned before budget
resolution), violating AC1 with no carve-out and no test. Fixed by hoisting budget
resolution above the routing + `--background` branches and forwarding the
plan-resolved `max_iterations`/`cost_ceiling` into `run_goal_loop_background` →
`_build_detached_child_argv` → the child's argv; a regression test
`PlanDriverAwareBudgetTests.test_background_launch_forwards_plan_budget` asserts the
plan's 7/$3.50 land in the detach summary (not the DEFAULT 5/$2.00).

**Re-review → PASS:** blocker confirmed fixed and meaningfully tested; all 8 ACs
hold. AC3 preserved — plan brakes live in fresh locals, never written to `args.*`,
so the goal-driver brake-drop keys only on explicit flags (no stray-brake warning
for plan-sourced brakes; explicit brake still warns). AC5 preserved — no `--plan` ⇒
`plan_budget`/`plan_driver` stay `None`, `_resolve_from_plan` returns `args.*`
unchanged (byte-for-byte), including the `--background` no-plan path.

Independently verified: full suite 1258 passed, ruff (0.15.17) clean, test_loop.py
280 passed.

**Non-blocking nit → deviation log:** `loop.py:3221-3224` — the `goal_unavailable`
refusal summary echoes `args.*`/DEFAULT budget rather than the plan-resolved budget.
Informational echo on a no-run refusal path; no AC or guardrail affected. Log it;
fold into 016-03's clamp work or justify as "refusal echoes user intent."

No design-principle violations (refuse-on-missing-prerequisite + clamp-never-loosen
both honored: compiled-only consumption, rc=2 fail-closed reads, no brake loosened).
