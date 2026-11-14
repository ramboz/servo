---
slice: 043-02 — plan-sourced credit ceiling
pass: frame-critique
verdict: pass
reviewer: general-purpose
reviewed_at: 2026-11-14T03:35:03Z
prompt_source: review.py frame-critique (spec 043-02)
---

VERDICT: pass (no blockers)

The single load-bearing assumption A1 — ADR-0016's clamp-never-disable carries to
the credit unit without a new policy decision — survives the strongest attack. It
is not merely asserted: it is settled in accepted ADR-0016 (amended for the credit
unit to state the rule is realized as a refuse-below-minimum floor rather than a
clamp-to-default, because credits have no `0` disable sentinel and no default
ceiling). The refuse-below-30 divergence is HONESTLY SURFACED in all three places
(slice A1 + `## Decisions needed` + AC1; loop.py docstrings/comments; the ADR),
not assumed away — and it is logically forced (nothing to clamp toward) and
consistent with the `--credit-ceiling` flag, which also refuses below 30.

- A1 GROUNDED, honestly surfaced. `_clamp_plan_value` is never called for
  credit_ceiling; `_validate_plan_budget` refuses `< 30` fail-closed. This is
  exactly the "real divergence the frame-critique must surface" that A1 names.
- "NOT a campaign enabler" framing ACCURATE — verified against live `campaign.py`:
  dispatch builds flat `--host copilot --credit-ceiling <n> --max-iterations <n>`
  argv per item and passes no `--plan`, so per-item credit ceilings reach Copilot
  workers today without this slice. The slice correctly corrects the
  refinement-todo's overstated "needed for spec 042" trigger.
- Anti-horizontal / phantom-path check PASSES on real evidence: resolution is
  hoisted above the gate and the resolved value threads to run_loop; two
  end-to-end subprocess tests prove launch (one runs a plan-only ceiling to
  completion; one asserts the worker is invoked and halts on the brake, not the
  gate). AC1/AC3/AC4/AC5 each have a matching end-to-end test. Genuine vertical
  slice.
- Thinnest point (residual, not a flaw): the only producer of a plan-sourced
  credit ceiling today is a human-authored `human_edited` Copilot plan
  (execution_plan.py never emits the key; no Copilot-aware planner exists). Not
  overclaimed — the slice scopes itself as a non-blocking `--plan`-path
  completeness fix, and the human-producer path is blessed by accepted ADR-0016.
- Cosmetic (not a frame issue): the illustrative `credit_ceiling: 200` in the
  slice narrative and ADR example is below gpt-6.1-sol's ~201.5 overrun bound, so
  200 launches-then-halts credit_ceiling_insufficient; the test author split the
  proof (500 for a full run, 200 for launch-then-brake), so the suite is correct —
  only the prose slightly oversells 200 as a usable budget. Noted in the deviation
  log.
