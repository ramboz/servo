---
status: DRAFT
kind: feature
dependencies: [adr-0016, adr-0048, 016-02, 041-02]
last_verified:
arch_review: true
frame_review: true
---

## Slice 043-02 — plan-sourced credit ceiling

**Goal:** Let a `--plan` file supply the Copilot credit ceiling via its `budget`
block, the way it already supplies the USD `cost_ceiling_usd`. Today only the
`--credit-ceiling` flag is wired: `loop.py`'s `_PLAN_BUDGET_KEYS` /
`_resolve_from_plan` / `_validate_plan_budget` omit a credit knob, and the
Copilot launch gate runs *before* plan-budget resolution, so a plan-only credit
ceiling is refused `native_capability_unavailable`. This slice resolves
`credit_ceiling` from flag-or-plan (≥ 30) before the Copilot gate, adds it to
the plan budget schema, and extends ADR-0016's clamp-never-disable semantics to
the credit unit.

**Honest framing — NOT a campaign enabler.** This is a `--plan`-file-path
completeness fix, not a prerequisite for spec 042 campaigns. Campaign dispatch
(`campaign.py`) launches each item with flat flags —
`loop.py … --host copilot --credit-ceiling <n> --max-iterations 5 --models
<json>` — and passes **no** `--plan` file, so per-item credit ceilings and 038
model tiering already reach Copilot workers. The gap this slice closes is
strictly the `--plan`-file path, for a user (or a future planner) who expresses
the budget in a plan rather than on the flag. The refinement-todo's stated
trigger ("plan-sourced budgets are needed for spec 042 campaigns") overstates
the dependency; this slice corrects it.

**DoR:**
- ADR-0016 (execution-plan artifact, plan budget schema + clamp semantics) is
  Accepted. ✓
- ADR-0048 (credit unit + the Copilot launch gate) is Accepted. ✓
- Spec 016-02 (plan-budget consumption: `_resolve_from_plan` /
  `_validate_plan_budget`) and spec 041-02 (Copilot credit brake + launch gate)
  are DONE.

**Acceptance Criteria:**

1. The plan budget schema accepts a `credit_ceiling`. `execution_plan.py`'s
   budget block (today `{max_iterations, cost_ceiling_usd, context_fill_threshold,
   plateau_window}`) gains an optional `credit_ceiling`, and `loop.py`'s
   `_PLAN_BUDGET_KEYS`, `_resolve_from_plan` and `_validate_plan_budget`
   recognize and validate it. A `credit_ceiling` below the 30-credit CLI minimum
   (ADR-0048) is refused fail-closed (rc=2) with a single reason — the same
   minimum the `--credit-ceiling` flag enforces.
2. `loop.py` resolves the effective credit ceiling from flag-or-plan **before**
   the Copilot launch gate runs, so a plan-only credit ceiling (no
   `--credit-ceiling` flag) launches instead of being refused
   `native_capability_unavailable`.
3. Flag-and-plan precedence follows ADR-0016's clamp-never-disable semantics,
   extended to the credit unit: the `--credit-ceiling` flag, when present, is
   the authoritative loop-driver ceiling; the plan supplies the ceiling when the
   flag is absent; and in all cases a resolved ceiling may clamp the loop lower
   but can never disable the credit brake or raise the ceiling past the policy
   bound (mirrors the USD clamp). See `## Decisions needed` to confirm the exact
   USD rule the credit unit inherits.
4. A credit ceiling resolved from the plan is otherwise identical to one from
   the flag: the same `cumulative_credits` / `credit_ceiling` state fields
   (ADR-0048 part 1), the same pre- and post-iteration halts, and the same
   launch-refusal when the computed overrun bound swamps the ceiling (ADR-0048
   part 2).
5. The USD and credit units stay apart (ADR-0048 parts 1 and 6): a plan budget
   carries `cost_ceiling_usd` or `credit_ceiling` as appropriate, and feeding a
   credit ceiling into a USD-host run (or a USD ceiling into a Copilot run) is
   refused with the existing wrong-unit reason — never silently converted.
6. ADR-0016's plan-shape example is refreshed to show the `credit_ceiling`
   budget key (a known refinement-todo item).

**DoD:** ACs pass with tests (TDD, witnessed red); compliance + craft + arch
reviews (slice declares `arch_review: true`); frame-critique
(`frame_review: true`); host-sync gate green (loop.py + execution_plan.py
vendored to the three host trees); reconciliation sweep + deviation log;
`docs/refinement-todo.md` item 1 marked resolved.

**Anti-horizontal-phasing check:** a user writes a plan whose `budget` block
sets `credit_ceiling: 200` with no `--credit-ceiling` flag and runs it against a
Copilot target; the worker launches under a 200-credit brake instead of being
refused `native_capability_unavailable` — the `--plan` path reaches the credit
brake end to end.

## Decisions needed

- **The exact flag-vs-plan clamp rule for the credit unit.** AC3 proposes the
  credit ceiling inherit ADR-0016's USD clamp-never-disable semantics verbatim
  (flag authoritative, plan clamps lower, never disables/raises — the 2026-07-04
  amendment). Confirm that is the exact rule ADR-0016 defines for
  `cost_ceiling_usd`, so the credit unit inherits it rather than inventing a
  parallel rule, and confirm the 30-credit CLI minimum composes cleanly with
  clamping (a plan clamp must not drop the effective ceiling below 30 — it
  should refuse, per AC1, not silently floor). Within ADR-0016; not ADR-shaped.

## Assumptions

- **A1 (clamp semantics transfer cleanly to credits).** ADR-0016's
  clamp-never-disable semantics, defined for the USD `cost_ceiling_usd`, carry
  to the credit unit without a new policy decision — the credit ceiling is just
  another budget knob under the same "a plan may tighten but never loosen the
  brake" rule, with no unit conversion (ADR-0048 part 1 keeps the units apart).
  If credits need a different clamp rule — for example because the 30-credit CLI
  minimum interacts with clamping — that is a real divergence the frame-critique
  must surface rather than assume away.
