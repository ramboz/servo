---
status: DRAFT
skill: agent-loop
use_cases: []
---

# Spec 041: Host-aware budget unit

> **Status: DRAFT, scope capture, low priority.** Follow-up to
> [spec 038](../038-per-node-model-tiering/spec.md). Parked while Copilot
> unattended execution stays refused
> ([ADR-0043](../../decisions/adr-0043-copilot-capability-boundaries.md);
> `run_loop` refuses `--host copilot` at `skills/agent-loop/loop.py:2527`).

## Overview

servo's budget brakes are denominated in USD (`--cost-ceiling`,
`--max-budget-usd`, the heartbeat whole-pass ceiling, ADR-0012). That fits
Claude's token billing. Copilot bills per prompt: "each prompt to Copilot CLI
uses one premium request", multiplied by the model's rate, and autonomous tool
calls don't count. Its native usage reports premium-request cost and nano-AIU,
not USD.

Today servo reports `total_cost_usd: 0.0` for Copilot rather than invent a
conversion (`_normalize_copilot_result`, `loop.py:2022-2073`; ADR-0038). As a
result, the USD ceiling cannot brake a Copilot run.

This spec would add a host-aware budget unit:

- a run's budget is declared in the host's native unit (USD for Claude,
  premium requests for Copilot);
- the per-model multiplier is taken from the host's own report, never from a
  hand-maintained price table;
- every brake compares like with like.

## Constraints

- **Never fabricate a conversion.** No USD↔premium-request exchange rate is
  invented. A budget in one unit never brakes spend reported in the other.
- **Clamp-never-loosen (ADR-0016).** Adding a unit never disables the USD brake
  on the Claude host.
- **Model tiering interacts.** Spec 038's role placement and ladder change
  which model runs. Under per-prompt billing, a model rung multiplies the cost
  of each request, so the ladder's sizing guidance differs per host.

## Activation trigger

ADR-0043 is revisited and an unattended Copilot loop (spec 034-03) becomes
supported.

## Slices

- [041-01 — budget unit](slice-01-budget-unit.md) (DRAFT sketch)
