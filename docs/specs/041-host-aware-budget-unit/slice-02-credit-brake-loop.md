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
   `--credit-ceiling N` (N ≥ 30, from the flag or plan `budget.credit_ceiling`) and an
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
   - Under `--host copilot`, a target whose oracle has USD-priced components is refused
     before any model call via the existing `_unpriced_oracle_error` /
     `_unpriced_oracle_preflight` path (ADR-0048 part 5), unless the owner approved a USD
     oracle ceiling.
7. **Role placement honoured or refused.** Under `--host copilot`: a `models` block that
   sets `model` is **refused** (`REASON_MODELS_INVALID`, the renders stay model-neutral,
   spec 032-03 / ADR-0048); an `effort` field **maps** to Copilot's `--reasoning-effort`
   (041-01 verified the flag + its levels); `advisor` is refused (no Copilot analogue).
   `requested` never records a flag that was not passed.

**DoD:** ACs pass with a mock `copilot` fed 041-01's real usage and
OpenTelemetry span files; full CI
gate; docs (agent-loop SKILL.md, architecture, Copilot host README) updated;
host packages regenerated; reviews (compliance, craft, arch).

**Anti-horizontal-phasing check:** a Copilot user can run servo's loop on a
Copilot worker capped in AI credits, and the run stops on that cap or on a
missing usage report, never silently.
