---
status: DRAFT
kind: feature
dependencies: [041-01, 038-01, adr-0048]
last_verified:
arch_review: true
frame_review: true
---

## Slice 041-02 — credit brake and supported loop launch

**Goal:** `loop.py --host copilot --credit-ceiling N --max-iterations M` runs the
native loop under a brake in AI credits that servo enforces. Without a credit
ceiling, it refuses as today.

**DoR:**
- The owner has explicitly accepted ADR-0048.
- 041-01 DONE; its findings fix the per-iteration arithmetic (direct vs
  session-delta, like 038-01).
- Spec 034-03 re-opened to `DRAFT` and reconciled: its budget and launch ACs
  are delivered here, and its remaining invocation, tool and resume evidence
  is either satisfied or kept as dependencies.

**Design sharpened from 041-01 (2026-11-11).** Three findings reshape the ACs:
(a) `--max-ai-credits` is **invocation-scoped** and `totalNanoAiu` is
**session-cumulative on `--resume`** — so the per-invocation cap is passed as the
remaining headroom unadjusted, while per-iteration cost is a **session-delta** (the
Copilot mirror of `_iteration_cost_delta`); (b) the usage JSON self-marks via
**`aiCreditsStatus`** (`complete`/partial/unavailable), which becomes the **primary**
fail-closed gate, with the OTel per-call Σ as the cross-check (reconciled against the
per-invocation delta, not the raw session total); (c) the worker model is
**admin-pinned and unknown pre-launch**, and the context window is unavailable at
runtime, so the overrun **bound cannot be computed pre-launch** — servo ships a
per-worker-model bound table (seeded from 041-01: `gpt-6.1-sol` → window 272 000,
prices 10/250/1000 cr per 1M, bound ≈ 200 cr) and applies the bound guard **reactively**
once `currentModel` is known. There is **no subagent tool-kind to deny** (041-01): the
single-threaded worker is guaranteed by omitting `--fleet`, refining ADR-0048 part 2's
"tool-denial flags" wording.

**Acceptance Criteria:**

1. **Opt-in launch.** `--host copilot` runs the loop only when both
   `--credit-ceiling N` (N ≥ 30, from the `--credit-ceiling` flag; plan-sourced
   `budget.credit_ceiling` is **deferred** — see the deviation log) and an
   explicit `--max-iterations` are given. Otherwise the ADR-0043 refusal is unchanged
   (`env_error`, rc=2, no subprocess, no state). **Bound guard (reactive):** because the
   admin-pinned worker model and its context window are not known pre-launch, the
   "bound ≥ ceiling" refusal fires after iteration 1 reveals `currentModel`: if that
   model's table bound ≥ the credit ceiling, halt `credit_ceiling_insufficient` (rc=2)
   naming the smallest sensible ceiling (> bound). A `currentModel` absent from the bound
   table is itself unverifiable → fail closed `credit_bound_unavailable`.
2. **Brake.**
   - `cumulative_credits = Σ` of each iteration's **own** credits — the
     session-delta of `totalNanoAiu / 1e9` when the invocation resumed a session,
     else the invocation's `totalNanoAiu / 1e9` directly (mirrors
     `_iteration_cost_delta`; cross-checked against the per-invocation OTel Σ).
   - Pre-iteration: halt `credit_ceiling_reached` when `ceiling − cumulative < 30`.
   - Each invocation gets `--max-ai-credits <ceiling − cumulative>` — **unadjusted**
     (the cap is invocation-scoped, 041-01 A2).
   - Post-iteration: halt when `cumulative_credits > credit_ceiling`.
3. **Fail closed.** Any of — `aiCreditsStatus != "complete"` (missing / `partial` /
   `unavailable`); a missing, unreadable or non-dict usage report; a missing, empty or
   unparseable OpenTelemetry span file (both exporter env vars
   `COPILOT_OTEL_EXPORTER_TYPE=file` + `COPILOT_OTEL_FILE_EXPORTER_PATH` pinned to a
   fresh per-invocation path); the per-call OTel Σ disagreeing with the invocation's
   reported credits (session-delta); or a timed-out / killed invocation with no report —
   halts `credit_usage_unavailable` (rc=2). That invocation's spend is `null`, and
   `cumulative_credits` becomes `null` (unknown), **never 0**. `_parse_copilot_usage` no
   longer truncates with `int()` (keeps the exact nano value) and returns `None`, not 0,
   for a missing field.
4. **Recorded.**
   - State and summary carry `credit_ceiling`, `cumulative_credits` and the overrun
     (`max(0, cumulative − ceiling)`).
   - Each invocation that ran past its `--max-ai-credits` records its overrun next to the
     worker model's table bound. When the observed overrun exceeds that bound, it sets
     `overrun_exceeds_bound: true` and prints a stderr breadcrumb — the ADR kill-criterion
     trigger.
   - Partial detection uses `aiCreditsStatus` (primary) + per-call OpenTelemetry cost
     (cross-check), ADR-0048 part 3.
   - 038-01's per-iteration record gains `cost_native: {unit: "ai_credits", value}`.
   - USD fields (`cost_usd`, `cumulative_cost_usd`, `cost_ceiling_usd`) stay `null` under
     Copilot.
   - Context is recorded as unavailable (`null`).
5. **No USD mixing.** `--cost-ceiling` is refused under `--host copilot`, and
   `--credit-ceiling` is refused under `--host claude` (both `env_error`, rc=2).
6. **Single-threaded worker, uncovered oracle spend refused.**
   - The Copilot worker invocation never passes `--fleet`. 041-01 found **no subagent
     tool-kind to deny** (only `shell/write/read/memory/url/<mcp>` exist); subagent
     spawning is gated solely by the `--fleet` launch flag, so omitting it is the control
     (ADR-0048 part 2, refined). No fabricated `--deny-tool` subagent rule is passed.
   - Under `--host copilot`, a target whose oracle has **unpriced** (unknown-USD-cost)
     components is refused before any model call via the existing `_unpriced_oracle_error` /
     `_unpriced_oracle_preflight` path (ADR-0041), which already runs on the Copilot path.
     This covers the common case (an API judge registered as unpriced). A component with a
     **known** USD price is not distinguishable from servo's install metadata (no
     `usd_priced` marker), so refusing it under Copilot per ADR-0048 part 5 is a
     **deferred** limitation — see the deviation log.
7. **Role placement refused.** Under `--host copilot` a `--models` block is **refused
   whole** (`REASON_MODELS_INVALID`): Copilot renders are model-neutral (spec 032-03) and
   servo does not tier under Copilot (ADR-0047 is Claude-only), so no `role_args` reach the
   worker and `requested` records nothing unpassed. (Effort-mapping to Copilot's
   `--reasoning-effort` was considered — 041-01 verified the flag — but refusing the whole
   block is simpler and fully compliant with the ADR's "refuse" option; mapping is
   deferred.)

**DoD:** ACs pass with a mock `copilot` fed 041-01's real usage and
OpenTelemetry span files; full CI
gate; docs (agent-loop SKILL.md, architecture, Copilot host README) updated;
host packages regenerated; reviews (compliance, craft, arch).

**Anti-horizontal-phasing check:** a Copilot user can run servo's loop on a
Copilot worker capped in AI credits, and the run stops on that cap or on a
missing usage report, never silently.

### Deviation log

- **AC1 bound guard is REACTIVE, not pre-launch.** The admin-pinned worker model and its
  context window are not known pre-launch, and the window is unavailable at runtime
  (041-01), so ADR-0048 part 2's bound cannot be computed before the first invocation.
  Pre-launch refusal enforces only the checkable preconditions (credit ceiling ≥ 30,
  explicit `--max-iterations`); the bound-vs-ceiling guard fires after iteration 1 reveals
  `currentModel`, halting `credit_ceiling_insufficient`. Two **new reasons** support this:
  `credit_ceiling_insufficient` and `credit_bound_unavailable`.
- **Shipped per-model bound table.** `COPILOT_MODEL_BOUNDS` is seeded from 041-01
  (`gpt-6.1-sol` only: window 272 000, 10/250/1000 cr per 1M, max-output 32 768 →
  bound ≈ 201.5 cr). A `currentModel` not in the table **fails closed**
  (`credit_bound_unavailable`) — a new, intentional safety; later models add a row.
- **AC7 = refuse, not map.** Chose to refuse a `--models` block whole under Copilot rather
  than map `effort` to `--reasoning-effort` (the ADR permits either; refuse is simpler and
  no `role_args` then reach the worker). Effort-mapping deferred.
- **aiCreditsStatus is the primary partial gate** (ADR part 3 assumed no such marker); the
  OTel per-call Σ cross-check reconciles against the session-**delta** on `--resume`
  (not the raw session-cumulative total — 041-01 A2), implemented in
  `_copilot_iteration_nano`.
- **USD fields are `null` (not 0) under Copilot.** The loop branches every USD arithmetic
  site on host; `_escalation_guard` gained a `None`-guard (the ladder is Claude-only).
- **A Copilot invocation failure is `credit_usage_unavailable`** (AC3), not the generic
  `claude_invocation_failed` — no usable credit report means fail-closed with spend `null`.
- **AC6 oracle-USD refusal reuses existing machinery** (`_unpriced_oracle_error` /
  `_unpriced_oracle_preflight`), which already runs on the Copilot path; no new code. It
  refuses **unpriced** (unknown-USD-cost) components (ADR-0041) — the common API-judge case.

**Deferred (surfaced by the independent compliance review; all fail-closed):**

- **Plan-sourced `budget.credit_ceiling` not wired (AC1).** `credit_ceiling` comes from the
  `--credit-ceiling` flag only; `_PLAN_BUDGET_KEYS` / `_resolve_from_plan` /
  `_validate_plan_budget` do not carry it, and the Copilot launch gate runs before the plan
  budget is resolved. A plan that supplies only `budget.credit_ceiling` (no flag) is
  **refused** `native_capability_unavailable` — fail-closed, not fail-open. Wiring it
  (moving the Copilot gate after plan resolution, extending the 016 clamp semantics to
  credits) is a follow-up; the flag is the primary operator surface. See
  [refinement-todo](../../refinement-todo.md).
- **Known-USD-priced oracle components under Copilot (AC6 / ADR-0048 part 5).** The
  `unpriced_components` guard refuses components whose USD cost is *unknown*, not components
  with a *known* USD price. servo's install metadata has no `usd_priced` marker, so a
  known-priced oracle component is not distinguishable and would run under Copilot (where
  `cost_ceiling` is `null`) with no USD bound. Refusing it per part 5 needs a new metadata
  marker — deferred. (The worker **credit** brake is unaffected; this is oracle USD.)
- **Copilot runs are not cross-process `--resume`-able.** The `backend_mismatch` resume
  guard refuses a persisted run whose `backend != claude`, so an interrupted Copilot run
  restarts fresh (re-spending credits), even though its state persists
  `cumulative_credits_nano` / `credit_ceiling`. The spec's "resume" is the intra-run Copilot
  session resume (the session-delta), which works. Cross-process resume of a Copilot run is
  a follow-up.

### Reconciliation sweep

- **Code:** `skills/agent-loop/loop.py` (telemetry gate, OTel pinning, bound table, brake
  helper, loop-body host branches, state/summary, CLI). The **Claude path is byte-identical**
  (`backend` is `HOST_CLAUDE` there, no credit keys, USD arithmetic unchanged) — verified by
  the unchanged 541-test baseline.
- **Tests:** `skills/agent-loop/test_loop.py` — mock-`copilot` OTel extension; brake-helper
  unit tests; credit-gate unit tests; and e2e launch/refusal/brake tests driving `loop.py`
  with a mock `copilot` fed matched usage + OTel (DoD). Full `test_loop.py` suite green.
- **Docs:** agent-loop `SKILL.md` (Copilot boundary rewritten, `--credit-ceiling` row, the
  four credit terminal reasons); `docs/architecture.md` (Copilot credit-brake note). No
  separate "Copilot host README" exists — SKILL.md + ADR-0048 are the operator surface.
- **Host packages:** regenerated (`build_host_packages.py`); `--check` in sync.
- **034-03 (native loop, DEFERRED):** its budget + launch ACs are delivered here; its
  invocation/tool/resume evidence came from 032-05 + 041-01. Its reconciliation is a
  follow-up bookkeeping item (not re-opened in this slice).
- **Contract surface:** new state/summary fields (`credit_ceiling`, `cumulative_credits`,
  `overrun_credits`, `overrun_exceeds_bound`, `credit_bound`) are additive (ADR-0004
  "pure additive MAY keep version at 1"); USD fields become `null` under Copilot only.
