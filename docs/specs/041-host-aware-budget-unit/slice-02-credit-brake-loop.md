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

**Acceptance Criteria (to sharpen after 041-01):**

1. **Opt-in launch.** `--host copilot` runs the loop only when both
   `--credit-ceiling N` (N ≥ 30, from the flag or plan
   `budget.credit_ceiling`) and an explicit `--max-iterations` are given.
   Otherwise the ADR-0043 refusal is unchanged (`env_error`, rc=2, no
   subprocess, no state). It also refuses when ADR-0048's computed overrun
   bound for the worker model is at least the ceiling, naming the smallest
   sensible ceiling.
2. **Brake.**
   - The running total is `cumulative_credits = Σ` of each iteration's credits
     (from `totalNanoAiu / 1e9`, per 041-01's semantics).
   - Pre-iteration: halt `credit_ceiling_reached` when the credits left are
     under 30.
   - Each invocation gets `--max-ai-credits <left>`, session-adjusted if
     041-01 shows the cap is session-scoped.
   - Post-iteration: halt when `cumulative_credits > credit_ceiling`.
3. **Fail closed.** A missing, unreadable or partial usage report, a missing,
   empty or unparseable OpenTelemetry span file (the exporter env vars are
   pinned per invocation), span sums that disagree with the usage report, or a
   timed-out invocation with no report all halt `credit_usage_unavailable` with
   rc=2. Spend for that invocation is `null`, and the run's
   `cumulative_credits` is then unknown and reported as `null`, never 0. The
   parser no longer truncates.
4. **Recorded.**
   - State and summary carry `credit_ceiling`, `cumulative_credits` and the
     overrun (`max(0, cumulative − ceiling)`).
   - Each invocation that ran past its `--max-ai-credits` records its overrun
     next to ADR-0048's bound. When the bound is broken, it sets
     `overrun_exceeds_bound: true` and prints a stderr breadcrumb; this is the
     trigger for the ADR's kill criterion.
   - Partial detection uses per-call OpenTelemetry cost (ADR-0048 part 3).
   - 038-01's per-iteration record gains `cost_native: {unit: "ai_credits",
     value}`.
   - USD fields stay `null` under Copilot.
   - Context is recorded as unavailable (`null`).
5. **No USD mixing.** The USD flags (`--cost-ceiling`) are refused under
   `--host copilot`, and `--credit-ceiling` is refused under `--host claude`.
6. **Single-threaded worker, uncovered oracle spend refused.**
   - The Copilot worker invocation never passes `--fleet`, and it denies
     subagent spawning with the tool-denial flag 041-01 verified (ADR-0048
     part 2).
   - Under `--host copilot`, a target whose oracle has USD-priced components
     is refused before any model call (ADR-0048 part 5), unless the owner
     approved a USD oracle ceiling.
7. **Role placement honoured or refused.** The Copilot invocation path
   currently drops 038-02's `role_args`, which is unreachable today. It must
   either map them to Copilot's own flags, or refuse a `models` block that
   sets a field it cannot honour. `requested` must never record a flag that
   was not passed.

**DoD:** ACs pass with a mock `copilot` fed 041-01's real usage and
OpenTelemetry span files; full CI
gate; docs (agent-loop SKILL.md, architecture, Copilot host README) updated;
host packages regenerated; reviews (compliance, craft, arch).

**Anti-horizontal-phasing check:** a Copilot user can run servo's loop on a
Copilot worker capped in AI credits, and the run stops on that cap or on a
missing usage report, never silently.
