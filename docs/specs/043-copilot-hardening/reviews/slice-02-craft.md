---
slice: 043-02 — plan-sourced credit ceiling
pass: craft
verdict: pass
reviewer: general-purpose
reviewed_at: 2026-11-14T03:35:03Z
prompt_source: review.py pr-review --richer-skill none --non-interactive (spec 043-02)
substrate: non-interactive
---

VERDICT: pass (no blockers)

The implementation matches the spec's stated scope exactly and is correct across
every flag/plan/precedence/minimum/wrong-unit permutation traced. The core change
is a reordering in `loop.py:main()` — the ADR-0041 unpriced-oracle safety
preflight and the plan-consumption block are hoisted above the Copilot launch
gate, and a flag-or-plan-resolved `credit_ceiling` feeds the gate — done without
breaking the downstream USD-knob resolution. Host mirrors byte-identical; all
touched tests pass locally.

Strengths:
- `test_plan_only_credit_ceiling_200_reaches_the_brake_not_the_gate` is an
  exemplary anti-horizontal-phasing test: asserts the worker was invoked
  (counter.exists) AND the halt is a brake decision (credit_ceiling_insufficient),
  proving the `--plan` path reaches the credit brake end-to-end.
- The credit-vs-USD clamp divergence (refuse-below-30 rather than clamp-to-default)
  is consistently documented at every site; `credit_ceiling` correctly bypasses
  `_clamp_plan_value`; the divergence is surfaced in `## Decisions needed`, not
  silently assumed.
- `test_plan_usd_ceiling_refused_under_copilot` pairs a VALID credit_ceiling with
  a cost_ceiling_usd to test units-never-mix at its sharp edge.

Non-blocking nits (folded this pass):
- The original `test_plan_credit_ceiling_wrong_type_refuses` was VACUOUS for its
  AC1 shape-check target (under `--host claude` the wrong-unit guard shadows the
  shape check — the test would pass even if the type check were deleted). FOLDED:
  replaced with a Copilot-host isolation test
  (`test_plan_credit_ceiling_wrong_type_refused_under_copilot`) where only the
  shape check can refuse a non-numeric; the <30 range check was already covered
  non-vacuously under copilot.
- The hoisted-unpriced-preflight comment overstated "changes no behavior." FOLDED:
  comment now acknowledges the host-gate precedence shift.
- `_copilot_plan` stamped `provenance="compiled"` though the compiler never emits
  `credit_ceiling`. FOLDED: switched to `human_edited` for artifact fidelity
  (inert to what's under test).

Scope is clean, no creep; the unpriced-preflight hoist is in-scope and necessary
so a bad `--plan` cannot preempt the ADR-0041 safety refusal.
