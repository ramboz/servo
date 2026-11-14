---
status: DRAFT
skill: heartbeat
use_cases: []
---

# Spec 043: Copilot hardening

> **Status: DRAFT, slices authored.**
> Three deferred fail-closed follow-ups from spec 041-02's compliance review,
> recorded in [`docs/refinement-todo.md`](../../refinement-todo.md) under
> "Copilot credit brake — deferred follow-ups (spec 041-02)". Each is a future
> `loop.py` change that hardens servo's Copilot host contract. **No new ADR** —
> [ADR-0048](../../decisions/adr-0048-copilot-credit-budget-contract.md) part 5
> and its resolved Open Question 5 already decide 043-01; 043-02 and 043-03 sit
> inside the ADR-0016 / ADR-0048 envelope. Suggested build order by impact:
> **043-01 → 043-02 → 043-03**. The three touch different code paths and are
> otherwise independent.

## Overview

Spec 041 (ADR-0048, DONE) gave servo's native loop a Copilot AI-credit budget
brake, so a Copilot worker can run under `loop.py`. Spec 041-02's compliance
review surfaced three fail-closed follow-ups, deferred because none blocked the
parity release. This spec authors them as vertical slices:

- **043-01 — refuse known-USD-priced oracle components under Copilot.** The one
  real safety hole. ADR-0048 part 5 (and its resolved OQ5) already decide the
  policy: under `--host copilot` an oracle whose components spend USD — e.g. an
  API-priced eval judge — is **refused**, and no separate USD oracle ceiling is
  approved. `loop.py` enforces that only for *unknown*-cost components today
  (`_unpriced_oracle_error`); a *known*-USD-priced component runs with
  `cost_ceiling` null — no USD bound — in violation of the accepted ADR. This
  slice enforces an already-accepted policy that is not enforced yet.
- **043-02 — plan-sourced `budget.credit_ceiling`.** A consistency fix on the
  `--plan` path, non-blocking. The credit ceiling reaches Copilot workers today
  only via the `--credit-ceiling` flag; a plan that expresses the budget in its
  `budget` block is refused, because the Copilot launch gate runs *before*
  plan-budget resolution and the plan schema carries no credit knob. This slice
  resolves the ceiling from flag-or-plan before the gate and adds the credit
  knob to the plan budget schema. It is strictly `--plan`-path completeness,
  **not** a spec 042 campaign enabler (campaigns already pass flat
  `--credit-ceiling` flags; see Assumptions).
- **043-03 — cross-process `--resume` of a Copilot run.** A capability
  extension. The `backend_mismatch` guard refuses to resume any persisted run
  whose `backend != claude`, so an interrupted Copilot run restarts fresh and
  re-spends its budget, even though its `cumulative_credits_nano` /
  `credit_ceiling` already persist in `state.json`. This slice narrows the guard
  to allow a same-backend Copilot resume, relying on the persisted session-delta
  credit accounting (ADR-0048 A2).

### Boundaries

- **Docs-only authoring.** This spec changes no runtime code. Each slice is a
  future `loop.py` change + tests + host-vendoring (the loop code is mirrored
  byte-identically to the three host trees under the CI host-sync gate).
- **No new ADR.** 043-01 enforces ADR-0048 part 5 (extending ADR-0041's
  refusal from unpriced to known-priced); 043-02 and 043-03 sit inside
  ADR-0016 / ADR-0048. Genuine open design points surfaced while authoring are
  recorded as `## Decisions needed` notes in the owning slice — not silently
  decided, and not promoted to an ADR unless a later review finds one
  load-bearing.
- **The credit unit stays a unit of its own** (ADR-0048 part 1): AI credits are
  never converted to USD. 043-02 adds a credit knob to the plan budget; it does
  not add a credit→USD bridge.
- servo never merges and the runner does no git operations; landing stays with
  jig `slice-land` or the host (unchanged by this spec).

## Assumptions

- The three follow-ups are transcribed verbatim-in-intent from
  `docs/refinement-todo.md` as deferred by 041-02's compliance review. The
  load-bearing premises each slice's frame-critique must test live in the
  per-slice `## Assumptions` sections.
- **The refinement-todo trigger for 043-02 overstates its dependency.** That
  entry states the resolution trigger as "plan-sourced budgets are needed for
  spec 042 campaigns." This is **not** accurate: spec 042 campaign dispatch
  (`campaign.py`) launches each item with flat flags
  (`--host copilot --credit-ceiling <n> --max-iterations 5 --models <json>`) and
  passes no `--plan` file, so per-item credit ceilings and 038 model tiering
  already reach Copilot workers. 043-02 is a `--plan`-file-path completeness
  fix, not a campaign enabler — its own framing says so.

## Decomposition (SPIDR)

- **Rules:** each slice changes one refusal/capability rule in `loop.py`, so the
  split is by rule, not by layer. The three rules are independent and touch
  different code paths (the oracle-cost guard; the plan-budget resolver + the
  launch-gate ordering; the resume `backend_mismatch` guard).
- Suggested order by impact: 043-01 (the safety hole) first, then 043-02
  (`--plan`-path consistency), then 043-03 (a resume capability extension).

## Slices

- [043-01 — refuse known-USD-priced oracle components under Copilot](slice-01-usd-priced-oracle-refusal.md)
  — add a `usd_priced` install-metadata marker and refuse, at the Copilot
  launch gate, any oracle carrying a known-USD-priced component absent an
  approved USD oracle ceiling (ADR-0048 part 5 / OQ5; extends ADR-0041's
  refusal from unpriced to known-priced). `arch_review`, `frame_review`.
- [043-02 — plan-sourced credit ceiling](slice-02-plan-sourced-credit-ceiling.md)
  — resolve `credit_ceiling` from flag-or-plan (≥ 30) before the Copilot launch
  gate; add it to the plan budget schema (`_PLAN_BUDGET_KEYS`,
  `_resolve_from_plan`, `_validate_plan_budget`) and extend ADR-0016's
  clamp-never-disable semantics to the credit unit. `arch_review`,
  `frame_review`.
- [043-03 — cross-process resume of a Copilot run](slice-03-copilot-cross-process-resume.md)
  — narrow the `backend_mismatch` guard to allow `--resume` when the persisted
  `backend == copilot`, relying on the persisted session-delta credit
  accounting. `frame_review`.

Dependencies: ADR-0048 (DONE), ADR-0041 (DONE), ADR-0016 (DONE), spec 041-02
(DONE), spec 016-02 (DONE). No new ADR.
