---
status: DONE
kind: feature
dependencies: [adr-0016, adr-0048, 016-02, 041-02]
last_verified: 2026-11-13
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

### Deviation log (after reconciliation)

The six ACs above are preserved as authored; no AC changed. The reviews surfaced
framing/comment/test-coverage refinements (folded), not AC changes.

Review rounds (a fresh `general-purpose` reviewer per pass):
- **Implementation reviews — all PASS, no `[blocker]`:** frame-critique,
  compliance, craft, arch (recorded under `reviews/slice-02-*`). The non-blocking
  nits below were folded in this pass.
- Reconciliation is a separate independent gate over this deviation log; by
  ADR-0014 its verdict is captured as its own review-evidence file (sweep row
  below), not restated in this log — so the log never asserts its own
  reconciliation outcome.

Non-blocking nits folded (from compliance / craft / arch):

1. **Hoist comments corrected.** The ADR-0041 unpriced-preflight comment and the
   plan-consumption comment over-claimed "no behavior change / no-op for
   `--emit-routine-prompt`"; both now state the real ordering shifts (a plan-read
   error no longer precedes the unpriced refusal; the unpriced refusal now
   precedes the Copilot gate; a malformed `--plan` on the `--emit-routine-prompt`
   path now refuses before emission).
2. **AC1 shape-check isolation.** The non-numeric `credit_ceiling` test moved
   under `--host copilot`
   (`test_plan_credit_ceiling_wrong_type_refused_under_copilot`), where the
   wrong-unit guard cannot shadow the shape check — so the test is non-vacuous.
3. **Precedence pinned.**
   `test_unpriced_oracle_refused_before_capability_gate_under_copilot` locks the
   intended "oracle-safety refusal wins over `native_capability_unavailable`"
   ordering under copilot.
4. **Emit-path regression test** added
   (`test_emit_routine_prompt_validates_plan_before_emitting`).
5. **Test-artifact fidelity.** The `_copilot_plan` helper now stamps
   `provenance: human_edited` (the compiler never emits `credit_ceiling`).

Load-bearing choices made during implementation:

1. **The credit unit does NOT reuse `_clamp_plan_value`** — Assumption A1's named
   divergence, surfaced not assumed. ADR-0016's clamp-never-disable is realized
   for credits as a refuse-below-30 floor in `_validate_plan_budget`, not a clamp
   of a `0` disable-sentinel up to a default: credits have no `0` sentinel and no
   DEFAULT ceiling (ADR-0048 part 4 makes the ceiling mandatory). No upper
   magnitude cap (consistent with ADR-0016's 2026-07-04 amendment); `flag > plan
   > None` precedence (`_resolve_from_plan`) prevents a plan from raising above
   the flag. ADR-0016 was amended to record this credit-unit realization.
2. **Plan consumption + the ADR-0041 unpriced-oracle preflight hoisted above the
   Copilot launch gate.** The minimal reordering that both resolves a
   plan-sourced ceiling before the gate (AC2) and keeps a fail-closed oracle-cost
   safety refusal ahead of any plan read. Consequence: `--plan` is now consulted
   under copilot, so a missing/malformed `--plan` refuses as a plan error rather
   than the blanket `native_capability_unavailable`; a valid plan that supplies no
   ceiling still refuses `native_capability_unavailable`. The hoist also moves
   plan validation ahead of the `--emit-routine-prompt` early return (so a
   malformed `--plan` refuses before a Routine prompt is emitted — nit 1 above)
   and the `--_detached-run-id` detached-child early return (theoretical only: a
   detached child is always re-exec'd with resolved flags, never `--plan`).
3. **Illustrative `credit_ceiling: 200` vs the launch test's `500`.**
   gpt-6.1-sol's ~201.5 overrun bound (ADR-0048 part 2 / 041-01) means 200
   launches then halts `credit_ceiling_insufficient`; the end-to-end launch test
   uses 500 (a completing run) and a separate test uses 200 to prove the worker is
   invoked and reaches the *brake*, not the gate.
4. **`execution_plan.py` stays producer-silent on `credit_ceiling`.** The
   host-agnostic compiler emits a Claude/USD budget and never emits
   `credit_ceiling` (it would be wrong-unit for a Claude run); a human /
   Copilot-aware planner adds the optional key. `_budget_hash` already hashes it
   order-independently, so a hand-added key reads as a recompile-preserve edit.

Rebase note: spec 043-01 (PR #63) merged to main first; this slice was rebased
onto it. `loop.py` auto-merged (independent code paths); the
`docs/refinement-todo.md` conflict (both slices resolved items in the same
section) was resolved to keep both resolutions; the host trees were regenerated
from the merged source. #63's `usd_priced` preflight stays in `run_loop`; the
relative order unpriced-before-`usd_priced` is preserved where both apply.

### Reconciliation sweep

| Artifact | Disposition | Rationale |
|----------|-------------|-----------|
| `skills/agent-loop/loop.py` + 3 host copies | `updated` | `credit_ceiling` added to `_PLAN_BUDGET_KEYS` + `_validate_plan_budget` (refuse `< 30`); `main()` hoists the ADR-0041 unpriced preflight + plan consumption above the Copilot gate, resolves `credit_ceiling` flag-or-plan via `_resolve_from_plan`, adds plan-side wrong-unit refusals both ways, and threads the resolved ceiling to `run_loop`. Byte-identical across the three host trees (`build_host_packages.py --check` green). |
| `skills/execution-planner/execution_plan.py` + 3 host copies | `updated` | Docstring + budget-constants comment document the optional, Copilot-only `credit_ceiling` (no compiled default); `compile_plan` + `_budget_hash` unchanged (compiler never emits the key; hash already covers arbitrary budget keys). Byte-identical across host trees. |
| `skills/agent-loop/test_loop.py` | `updated` | TDD coverage (witnessed red → green) of AC1–AC5 under copilot + claude, incl. the anti-horizontal-phasing launch/brake tests and the folded shape-isolation / precedence / emit-path tests. Source-only (test files never ship to host packages). |
| `skills/agent-loop/test_copilot_capability.py` | `updated` | The `--plan` native-refusal case now uses a valid no-ceiling plan (still `native_capability_unavailable`), reflecting that `--plan` is consulted under copilot. |
| `skills/execution-planner/test_execution_plan.py` | `updated` | Schema tests: a compiled plan has no `credit_ceiling`; `_budget_hash` accepts the optional key. |
| `docs/decisions/adr-0016-execution-plan-artifact.md` | `updated` | AC6: the plan-shape example gains the optional Copilot `credit_ceiling` budget key + the refuse-below-minimum prose. |
| `docs/refinement-todo.md` | `updated` | Item 1 (plan-sourced `budget.credit_ceiling`) marked **RESOLVED** in the slice's feat commit; the overstated "needed for spec 042 campaigns" trigger corrected. |
| `docs/specs/README.md` (board) | pending close-out | Regenerated by `status-board` immediately before the DONE transition — not yet applied when this sweep was written. |
| `docs/specs/043-…/reviews/slice-02-{compliance,craft,arch,frame-critique}.md` | `new` | The four implementation-review verdicts (all `pass`), persisted by `review.py record-review`. |
| `docs/specs/043-…/reviews/slice-02-reconciliation.md` | `new` (pending close-out) | The reconciliation gate's verdict, persisted by `review.py record-review` once the gate passes — not yet written when this sweep was composed. |
| `skills/quality-gate/gate.py` | `no-op` | gate.py is host-blind; credit-ceiling resolution + the wrong-unit refusals live only in loop.py's launch path. |
| `docs/decisions/adr-0048-*.md` | `no-op` | This slice sits inside ADR-0048 (credit unit, 30-min, launch gate) and ADR-0016 (clamp-never-disable); no ADR change beyond ADR-0016's AC6 example refresh. |
