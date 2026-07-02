---
status: DONE
dependencies: [016-01, 003-08, adr-0016, adr-0018, adr-0023]
last_verified: 2026-07-02
frame_review: true
---

## Slice 016-02 — run-consume

**Goal:** Teach Servo Run to read its *run configuration* from a present plan.
`loop.py` gains a `--plan <path>` flag that reads `budget` and `driver` from a
compiled `plan.json` as run defaults for any knob the caller did not pass on the
command line. With **no** `--plan`, behavior is byte-for-byte today's (CLI flags +
`loop.py` defaults) — the plan is opt-in glue, not a precondition. This is the first
end-to-end "compile a plan, then run against it" path.

> **`prompt_ref` consumption is out of scope — split to
> [016-05](slice-05-prompt-render.md).** 016-01 emits `prompt_ref = str(spec_path)`
> (the whole `spec.md`), but `loop.py` feeds the seed prompt **verbatim** to
> `claude -p` as the per-iteration task instruction (`loop.py:1300`, `:464`) —
> feeding a multi-slice planning document is a category mismatch. Making
> `prompt_ref` usable requires the producer to *compile an actionable prompt* from
> the spec (a section-parse + rendering contract `execution_plan.py` does not have
> today — it never reads `spec.md`). That is a distinct capability, not a knob-read;
> it gets its own slice. **016-02 therefore keeps `--prompt` required** and consumes
> only `budget` + `driver`.

> **Consumer scope (ADR-0016 refined / [ADR-0018](../../decisions/adr-0018-suitability-gates-compile-not-heartbeat.md)).**
> The plan's sole consumer is `loop.py` (Compile → Run for a real spec). The
> heartbeat dispatcher is out of scope — its findings are spec-less.

> **Plan location unchanged (`.servo/plans/<spec-id>/plan.json`)** per
> [ADR-0023](../../decisions/adr-0023-colocate-durable-spec-oracle-artifacts.md);
> `--plan` takes a **generic path** (no `spec-id` derivation in `loop.py`).

## Current state (verified 2026-07-02)

- `execution_plan.py compile` writes `.servo/plans/<spec-id>/plan.json` with
  `schema_version: 1`, `budget {max_iterations, cost_ceiling_usd,
  context_fill_threshold, plateau_window}`, `driver`, `prompt_ref`, and
  `provenance: "compiled"`. This slice does **not** modify the producer.
- `loop.py`'s budget flags default to `None` at argparse and resolve via
  `x if x is not None else DEFAULT_*` inside `run_loop` / `run_goal_loop`
  (`loop.py:2787`, `:1537`, `:3072`); a fresh run persists the resolved budget to
  `state.json` (`loop.py:1650`) — the observable AC1 asserts against.
- `--driver` is `default=DRIVER_AUTO` (concrete, not `None`) and consumed by the
  routing probes at `loop.py:2937`/`:3002`/`:3025` — **before** the `run_loop` call
  at `:3072`. Driver resolution is therefore **not** co-located with budget
  resolution (A1).
- **Under the goal driver, two budget knobs are structurally dropped.**
  `loop.py:3049-3063` discards `--context-fill-threshold` and `--plateau-window`
  under `DRIVER_GOAL` (they are loop-mode brakes the `/goal` primitive owns) and
  emits a warning naming them. `driver: auto` routes to goal on a supported host, so
  a `compiled` plan carrying all four budget fields must not silently no-op two of
  them nor misattribute them to the user (AC3).

## Assumptions

- **A1 — two resolution points, not one.** Budget flags resolve just above the
  `run_loop` / `run_goal_loop` call (`loop.py:3072`), where they are already
  `None`-sentinels. `--driver`, which AC2 pulls into plan-precedence, is consumed by
  the routing probes *earlier* (`loop.py:2937`/`:3002`/`:3025`), so its plan-value
  resolution + `default=DRIVER_AUTO` → `None` migration must happen **above** those
  sites (~5 read-sites). This split is the main risk to AC5's byte-for-byte
  guarantee. *To verify:* an omitted `--driver` with a plan uses the plan's driver at
  every routing site; with no plan, routing is identical to today.
- **A2 — no separate "policy ceiling" exists in `loop.py`.** The configured budget
  *is* the operative ceiling (the `DEFAULT_*` constants are defaults, not caps), so
  an over-ceiling **hand-edited** plan consumed raw would *loosen* a brake — which
  ADR-0016 forbids. 016-02 consumes `provenance: compiled` plans only and refuses
  `human_edited` plans pending 016-03's clamp (AC7). No clamping logic ships here.

**Implementation note (surfaced by frame-critique, 2026-07-02).** AC1 (fill knobs
the caller did not pass) and AC3 (silently drop plan-sourced loop-only brakes under
the goal driver) collide **if** plan values are resolved by mutating
`args.<brake>` in place: the goal-driver drop warns iff `args.<brake> is not None`
(`loop.py:3058`), so a plan value written into `args.context_fill_threshold` would
trip the "user passed a stray brake" warning AC3 forbids. The resolution layer must
therefore track **source-of-value** (user-passed vs plan-sourced vs default)
*separately* from the `None`-sentinel — do not overload `args.*` to carry the plan
value.

**DoR:**
- ✅ **016-01 DONE** — `plan.json` is emitted with the `budget` + `driver` fields
  this slice reads (producer untouched by this slice).
- ✅ **003 DONE** — `loop.py` is the consumer; budget flags already `None`-sentinel.
- ✅ **ADR-0016 Accepted** — the read / precedence / clamp-never-loosen contract.
- ✅ **ADR-0018 Accepted** — scopes the consumer to `loop.py`, not the heartbeat.
- ✅ **ADR-0023 Accepted** — execution plan stays under `.servo/plans/`.
- ✅ Decision (surface): a generic `--plan <path>` flag (not `--spec`).
- ✅ Decision (scope): `prompt_ref` consumption + the spec→prompt renderer is
  [016-05](slice-05-prompt-render.md); 016-02 keeps `--prompt` required.
- ✅ Decision (exit contract): every new refusal is `rc=2` with a structured stderr
  reason; never exit 1; never a partial run.

**Acceptance Criteria:**

1. **`--plan <path>` supplies budget + driver defaults.** Given a
   `provenance: compiled` `plan.json`, `loop.py <target> --plan <path> --prompt "…"`
   runs with the plan's `budget` and `driver` as the effective configuration for each
   knob the caller did **not** pass — subject to the active driver (AC3). The
   enforced budget is observable in `state.json` (`loop.py:1650`). *Test:*
   `PlanConsumeDefaultsTests`.

2. **Precedence: explicit CLI flag > plan value > loop.py default.** An
   explicitly-passed budget flag or `--driver` overrides the plan; the plan overrides
   the built-in default. `--driver`'s argparse default migrates to `None` and
   `DRIVER_AUTO` is resolved **before the routing probes** (A1), leaving the no-plan
   routing path unchanged. *Test:* `PlanPrecedenceTests`.

3. **Driver-aware budget (goal-driver carve-out).** Under the loop driver, all four
   plan budget knobs apply. Under the goal driver (including `driver: auto` routed to
   goal), the loop-only brakes `context_fill_threshold` and `plateau_window` from the
   plan are dropped **exactly as explicit flags are** (`loop.py:3049`), and **no**
   "user passed a stray brake" warning is emitted for plan-sourced values (they are
   plan defaults, not a user request). `max_iterations` / `cost_ceiling_usd` still
   apply under goal. *Test:* `PlanDriverAwareBudgetTests`.

4. **`--prompt` remains required.** 016-02 does **not** consume `prompt_ref`. A fresh
   `--plan` run still refuses without `--prompt` (or `--resume`), exactly as today —
   the prompt handoff is [016-05](slice-05-prompt-render.md). *Test:*
   `PlanPromptStillRequiredTests`.

5. **No plan ⇒ byte-for-byte today's behavior.** With no `--plan` flag, `loop.py`
   takes exactly today's path (CLI flags + defaults): no plan file is read and none
   of the AC6/AC7 refusals is reachable. Resolved configuration and run summary are
   identical to a pre-slice invocation with the same flags. *Test:*
   `NoPlanUnchangedTests`.

6. **Fail-closed plan-read contract.** `--plan` pointing at a missing file,
   unreadable/malformed JSON, or a `schema_version` ≠ `1` refuses with exit `2` and a
   structured stderr reason (`plan_missing` / `plan_malformed` /
   `plan_schema_mismatch`). No run starts; no `state.json` is written. *Test:*
   `PlanReadContractTests`.

7. **`human_edited` budget deferred to 016-03 (clamp, never loosen).** A
   `provenance: human_edited` plan refuses with exit `2` + reason
   `plan_requires_clamp`, naming 016-03 — 016-02 consumes only `compiled` plans (A2).
   *Test:* `PlanHumanEditedDeferredTests`.

8. **`--plan` and `--resume` are mutually exclusive.** On resume the persisted
   `state.json` is authoritative, so passing both is a `parser.error`. *Test:*
   `PlanResumeExclusiveTests`.

**DoD:**
- [x] All ACs pass; new `test_loop.py` cases green (21 plan tests); full suite green
      (1258 passed, no regressions); `ruff check .` clean (pinned 0.15.17).
- [x] Implementer coverage exercises each AC with ≥1 fixture, including the
      no-plan-unchanged baseline (AC5), the goal-driver carve-out (AC3), and every
      fail-closed reason (AC6/AC7).
- [x] Reviewed by jig compliance + craft; `frame_review: true` ⇒ frame-critique pass
      cleared before READY_FOR_REVIEW (4-pass; evidence under `reviews/`).
- [x] Deviation log produced under this slice heading.
- [x] Reconciliation sweep produced under this slice heading.
- [x] Reconciliation review passed.
- [x] `docs/refinement-todo.md` — n/a: the deferred decisions are tracked in the
      deviation log and are 016-03 clamp scope (no new servo-dev refinement entry).

### Close-out (post-DONE)

- [x] `docs/specs/README.md` regenerated; the `--plan` flag + precedence + goal-driver
      carve-out recorded in the Notes column.
- [x] 016-03's trigger (`016-02 DONE`) marked met (breadcrumb added to
      slice-03-clamp-and-review.md); 016-03 stays DEFERRED until re-opened.

**Anti-horizontal-phasing check:** After this slice, a user can `execution_plan.py
compile` a plan and then `loop.py <target> --plan plan.json --prompt "…"` to run with
the plan's compiled budget + driver and zero repeated configuration flags — a real
Compile→Run handoff for a spec. (The prompt itself is still passed explicitly until
016-05 renders it.) That is user-facing value, not intermediate state.

### Deviation log (after reconciliation)

Original ACs preserved above. Implementation notes:

1. **AC count grew 7 → 8 during frame-critique.** The `frame_review: true`
   adversarial pass ran 4 times pre-implementation; the first three each caught a
   real wrong-frame issue (evidence: `reviews/slice-02-frame-critique.md`). Net
   effects on the frame: (a) the heartbeat was dropped as a plan consumer and the
   `--plan` addressing mechanism named (spec.md sync); (b) **`prompt_ref` consumption
   was split out to a new slice [016-05](slice-05-prompt-render.md)** once it proved
   to require a *spec→prompt compiler* (`execution_plan.py` reads no spec content),
   a distinct capability — so 016-02 keeps `--prompt` required (AC4); (c) the
   **goal-driver carve-out was added as AC3** after the pass found the goal driver
   structurally drops two of four budget knobs (`loop.py:3049`).

2. **`--plan` + `--background` budget-drop — found in compliance review, fixed.**
   The first compliance pass returned needs-changes: the `--background` detached
   branch returned before budget resolution, so a plan's budget was silently ignored
   on that path (AC1 violation). Fixed by **hoisting the four `_resolve_from_plan`
   budget locals above the routing + `--background` branches** and forwarding the
   plan-resolved `max_iterations`/`cost_ceiling` into `run_goal_loop_background`;
   regression test `PlanDriverAwareBudgetTests.test_background_launch_forwards_plan_budget`
   added. Re-review PASS. AC3/AC5 confirmed unaffected by the hoist.

3. **`goal_unavailable` refusal echoes DEFAULT/args budget, not the plan's
   (`loop.py:3221-3224`) — deferred (cosmetic).** On an unsupported host, the rc=2
   refusal summary echoes `args.*`/`DEFAULT_*` budget rather than the plan-resolved
   locals now available just above. No run starts and no AC covers the refusal
   summary's echoed bounds; flagged by both the implementer and the compliance
   re-review as a non-blocking consistency nit. Left as-is; fold into 016-03's clamp
   work or justify as "a refusal echoes user intent, not plan defaults."

4. **Plan-value validation deferred to 016-03 (craft nits, unreachable today).**
   Plan-sourced budget values skip the argparse range/type guards, and a plan-sourced
   `driver` bypasses the `choices` guard (an unrecognized value routes as `auto`).
   Both are **unreachable via the current `compiled` producer** (`execution_plan.py`
   emits fixed valid constants and `DEFAULT_DRIVER="auto"`), and validating/clamping
   hand-authored plan values is exactly 016-03's job — recorded here, not fixed.

5. **Craft nit fixed inline:** `_load_plan` / `_resolve_from_plan` gained the
   return-type annotations their sibling helpers carry.

6. **Test-harness detail:** `NoPlanUnchangedTests.test_no_plan_uses_builtin_defaults`
   uses `_run_raw` with explicit `--driver loop` (not the `_run_loop` harness, which
   injects `--plateau-window 0`) so the default `plateau_window=3` surfaces — a
   harness choice, not a behavior change.

### Reconciliation sweep

| Artifact | Disposition | Rationale |
|----------|-------------|-----------|
| `README.md` | `no-op` | Skill-internal flag on `loop.py`; the project front door covers install + high-level usage, not per-flag detail. |
| `docs/specs/README.md` | `updated` | Regenerated by `workflow.py status-board` (67 slices; 016-05 added). **The final regen reflecting 016-02's terminal status is intentionally deferred to Close-out (per the Close-out checklist), so mid-reconciliation the board row lags the slice frontmatter by one transition** — expected, not stale. |
| `docs/product-vision.md` | `no-op` | No behavior/scope drift; `--plan` is within the existing loop capability. No design-principle violation (refuse-on-missing-prereq + clamp-never-loosen both honored). |
| `docs/architecture.md` | `deferred` | The ADR-status table lists ADR-0014/0015/**0016** all as `Proposed` though all are Accepted — **systemic table lag**, pre-existing and independent of this slice. Fixing one row inconsistently is worse; owner: a separate `chore(docs)` ADR-table refresh. The "016 (planned)" skill row stays accurate (the `/servo:execution-plan` skill is 016-04, still deferred). |
| agent-loop `SKILL.md` | `deferred` | `--plan` narrative deferred to the **016-04 Interface slice** (the skill-surface home). The flag is self-documenting via `loop.py --help` (full argparse help text) in the meantime, so it is discoverable, not silent. |
| `docs/inbox.md` | `no-op` | No items resolved by this slice. |
| `docs/refinement-todo.md` | `no-op` | The deferred loose ends (cosmetic refusal echo; plan-value validation) are captured in the deviation log above and are 016-03 clamp scope — no new servo-dev refinement entry warranted. |
| `docs/memory/**` | `updated` | `[[servo-016-execution-planner-started]]` refreshed with the final 016-02 shape + the 016-05 split. (Out-of-repo artifact under `~/.claude/projects/.../memory/` — no in-repo diff; the in-repo `docs/memory/` was not touched.) |
| `docs/decisions/README.md` / ADR index | `no-op` | No ADR authored or modified; ADR-0016's contract was implemented as-accepted (the prompt_ref clarification was avoided by the 016-05 split). |
| Additional live prose / generated templates | `no-op` | No install-contract or template surface touched (loop.py is already a vendored skill file). |
