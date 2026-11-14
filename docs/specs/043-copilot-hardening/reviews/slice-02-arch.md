---
slice: 043-02 — plan-sourced credit ceiling
pass: arch
verdict: pass
reviewer: general-purpose
reviewed_at: 2026-11-14T03:35:03Z
prompt_source: review.py arch-review --richer-skill none --non-interactive (spec 043-02)
substrate: non-interactive
---

VERDICT: pass (no blockers)

Slice 043-02 is architecturally sound. The core design — hoisting the ADR-0041
unpriced-oracle safety preflight above plan consumption, and plan consumption
above the Copilot launch gate — is the MINIMAL ordering that satisfies both hard
invariants at once (the safety refusal fires before any plan read; the
plan-sourced credit ceiling reaches the gate). The credit unit's
clamp-never-disable is correctly realized as a refuse-below-30 floor rather than
reusing the USD disable-sentinel clamp, matching the credit unit's reality (no
`0` sentinel, no default ceiling per ADR-0048 part 4). Unit boundaries stay clean
on both producer (execution_plan.py) and consumer (loop.py) sides; ADR-0016's
example is refreshed correctly; all three host trees byte-identical.

- (a) The hoist PRESERVES "safety gate fires before plan read": the preflight sits
  above the plan read, so a malformed `--plan` can never preempt the unpriced
  refusal; the preflight writes no state and its decision depends only on the
  install manifest marker, so moving it changes position, not outcome; every
  reordered path still fails closed.
- (b) Refuse-below-30 (NOT `_clamp_plan_value`) is right: that helper only clamps a
  `0` sentinel up to a DEFAULT, which credits lack; the refusal preserves
  never-disable fail-closed; no upper magnitude cap (consistent with ADR-0016's
  2026-07-04 amendment); ADR-0048 part-4 "mandatory, no default" honored.
- (c) Unit boundaries enforced at all four corners (flag/plan × USD-under-copilot /
  credit-under-claude); a plan carrying both keys is always refused; producer only
  documents the optional key and never emits it; a human-added credit_ceiling
  survives recompile-preserve (hashed order-independently).
- (d) ADR-0016's refreshed example shows `credit_ceiling: 200`, omits
  `cost_ceiling_usd` (units never coexist), and states no-default / min-30 /
  resolve-before-gate / refuse-below-minimum-floor. AC6 satisfied.

Strengths: the added `args.credit_ceiling is not None` guard prevents a `None < 30`
TypeError now that the gate keys on the resolved (possibly plan-sourced) ceiling;
AC2 anti-horizontal-phasing is proven end-to-end by the 200-reaches-the-brake test.

Non-blocking nits (folded / addressed this pass):
- The `--emit-routine-prompt --plan <malformed>` combo now refuses where it
  previously emitted; the comment's "no-op for emit-routine" claim was wrong.
  FOLDED: comment corrected + regression test added + deviation-log line.
- Reason-precedence: copilot + no-credit + unpriced-oracle now returns the unpriced
  refusal instead of native_capability_unavailable (safety wins). FOLDED: pinned by
  `test_unpriced_oracle_refused_before_capability_gate_under_copilot` + deviation
  log. Intentional.
- claude plan `credit_ceiling < 30` gets the min-value message before the unit
  message (cosmetic, both fail-closed). Acknowledged in the deviation log.

Ready to transition to REVIEWED from the architecture pass.
