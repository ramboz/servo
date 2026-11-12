---
status: DONE
skill: agent-loop
use_cases: []
---

# Spec 041: Copilot AI-credit budget for the native loop

> **Status: DRAFT. Next after spec 038, by owner priority.** Gated on the owner
> accepting [ADR-0048](../../decisions/adr-0048-copilot-credit-budget-contract.md),
> which stays Proposed until then, and on authorizing the billed probe in 041-01.

## Overview

servo refuses its native loop on GitHub Copilot CLI
([ADR-0043](../../decisions/adr-0043-copilot-capability-boundaries.md)), because
Copilot's only budget control, `--max-ai-credits`, is a soft cap in AI credits,
not dollars. In a recorded two-day Copilot multi-session campaign servo never
ran, and that refusal was the first cause. The workers ran with no budget,
plateau or context brake; one fixer made 1,383 calls.

This spec delivers the budget contract ADR-0048 proposes: a **brake
denominated in AI credits**, Copilot's own unit, never converted to USD. servo
enforces it between invocations, and it fails closed when usage is not
reported. With it in place, the loop driver can run under `--host copilot`.
That makes servo's per-node discipline (oracle, plateau, spec 038's ladder,
budget) available to Copilot-hosted workers.

### Grounded starting point

servo HEAD `7888d90`; CLI `copilot` 1.0.109-1, help text captured
2026-11-10 with no prompts run.

- **CLI facts:**
  - `copilot help billing`: usage is "measured in AI credits, or in premium
    requests on the legacy billing platform". `--usage-output-file` "Writes
    final usage as JSON: totalNanoAiu (10^9 nano AIU = 1 AI credit),
    totalPremiumRequestCost, modelMetrics, and agentMetrics".
  - `copilot help limits`: `--max-ai-credits` "Cap[s] this session (minimum
    30 AI credits)". It is a soft cap: "one response can go past the limit;
    the next model call is then blocked. Hidden work such as compaction counts
    too." Usage accumulates across the session, including subagents.
- **servo today:**
  - `run_loop` refuses `--host copilot` first thing (`loop.py:2527-2528`,
    `_refuse_copilot_capability` `:1169-1191`). Resume of non-Claude state
    refuses (`:2585-2595`).
  - `--max-ai-credits` is forwarded unchanged on every iteration
    (`_build_copilot_cmd` `:1857-1891`), with no remaining-budget
    recomputation and no check against the 30 minimum.
  - `_parse_copilot_usage` (`:1894-1940`) returns zeros for a missing file and
    truncates fractional values with `int()`. `_normalize_copilot_result`
    (`:2022-2073`) sets `total_cost_usd: 0.0` and builds no `modelUsage`, so
    the context gate fails open. Credit spend reaches only stderr
    (`:2964-2974`), not state or summary.
  - Heartbeat: `_outcome_from_summary` turns a non-numeric cost into `0.0`
    (`heartbeat.py:2165-2170`), and every budget sum is USD
    (`_outcome_cost_usd`, `_spent_cost_usd`).
- **Spec 034-03 (native loop, DEFERRED)** has this resolution trigger: "an
  explicit owner-approved replacement monetary/credit policy recorded in a new
  ADR, followed by positive native invocation/tool/context/resume evidence and
  normal readiness review. A CLI limit flag alone does not reactivate this
  slice." ADR-0048 is that ADR; 041-01 and 041-02 provide the evidence and the
  enforcement.

### Boundaries

- No USD conversion, ever (ADR-0043 Option B). Credit and USD fields never mix.
- Unavailable is `null`, not zero (ADR-0043 §3): a missing usage report halts
  the run.
- The oracle stays authoritative. Copilot's Autopilot has no oracle-gated stop,
  so the goal driver stays refused (034-07).
- Serial, no fan-out, never merges, the runner does no git operations, and
  servo never depends on jig.

## Assumptions

ADR-0048 A1–A5: per-invocation `totalNanoAiu`, session-scope semantics on
`--resume`, the usage file after a timeout or kill, legacy-billing fields, and
partial-report marking. All of them are unverified until 041-01's billed probe.

## Decomposition (SPIDR)

- **Spike, justified.** The session-scope semantics (A2) decide the
  arithmetic of the brake, exactly as bug 007 did for Claude. Only a billed run
  can settle them, and P/I/D/R cannot split around an unknown in the core
  rule. So it is a time-boxed spike, the first slice.
- **Path:** the loop driver comes first (041-02). The heartbeat's credit ledger
  is the second path (041-03).

## Slices

- [041-01 — Copilot contract probe](slice-01-copilot-contract-probe.md) (spike;
  needs owner authorization for about 60 AI credits)
- [041-02 — credit brake and supported loop launch](slice-02-credit-brake-loop.md)
- [041-03 — heartbeat credit ledger](slice-03-heartbeat-credit-ledger.md)
