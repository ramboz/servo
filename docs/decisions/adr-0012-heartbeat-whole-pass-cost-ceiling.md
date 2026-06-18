---
status: Accepted
date: 2026-06-18
deciders: ramboz
supersedes:
superseded-by:
---

# ADR-0012: Heartbeat uses one whole-pass cost ceiling

## Status

Accepted

## Context

Spec 011 turns servo into a scheduled front-end: `heartbeat.py run` discovers
project signals, dispatches actionable findings into isolated loop worktrees,
and records outcomes back to the triage inbox.

Before slice 011-04, `heartbeat.py dispatch --cost-ceiling USD` had only a
per-loop meaning inherited from `loop.py`: every candidate received the same
cap. That is correct for manual dispatch, but it is dangerous for scheduled
`run`: five candidates under a `$2` per-loop cap silently becomes a `$10`
heartbeat. The scheduled path needs the opposite contract: one budget for the
whole pass, with remaining work left `open` for the next heartbeat when the
budget is spent.

ADR-0010 already reserved the field this needs: every dispatch outcome records
`outcome.cost_usd` in `.servo/triage/inbox.jsonl`. That makes cost accounting
reviewable from the inbox alone, without joining across `.servo/runs/*/state.json`
files. The scheduled heartbeat budget is scoped to one `run` invocation; old
outcomes remain audit history but do not consume a future scheduled pass.

## Decision

`heartbeat.py run` uses one **whole-heartbeat** cost ceiling.

Concretely:

1. `heartbeat.py run <target> --cost-ceiling USD` treats `USD` as the maximum
   spend for the whole pass, not for each loop. The default is `$2`, matching
   servo's existing loop default but applying it once to the heartbeat.
2. `heartbeat.py dispatch --cost-ceiling USD` keeps its 011-03 meaning: the
   value is forwarded to each dispatched loop independently. This preserves the
   manual dispatch surface.
3. `run` captures a pass-start timestamp before discovery. Before dispatching,
   and again under the inbox lock, it sums `outcome.cost_usd` values from inbox
   outcomes whose `dispatched_at` is at or after that pass start. Historical
   `tried` / `passed` outcomes from earlier heartbeats remain audit history but
   do not drain a fresh scheduled budget.
4. Each loop receives the remaining whole-heartbeat budget as its per-run
   `--cost-ceiling`. After each outcome is recorded, remaining budget is
   recomputed from the updated spend.
5. When remaining budget is below the dispatch floor, `run` stops before the
   next candidate, exits 0 with a breadcrumb, and leaves remaining
   actionable-open findings `open`.
6. Discovery currently has no LLM assist and therefore contributes `$0`; if a
   future slice adds LLM-assisted triage, that cost must be recorded in the
   same inbox-spend model before dispatch.

## Consequences

**Positive.**

- Scheduled heartbeats have a predictable spend cap by default.
- Budget accounting is reviewable because the inbox remains the source of truth
  for outcomes and spend.
- The scheduled `run` surface and the manual `dispatch` surface keep distinct,
  explicit semantics.

**Negative.**

- A loop can still overshoot the heartbeat ceiling by the cost of its final
  in-flight turn; the heartbeat can only stop between serial candidates.
- If the process dies mid-pass, a later `run` starts a fresh scheduled budget.
  True crash-resumable budgeting would require a heartbeat pass id or separate
  ledger; this slice keeps the next scheduled heartbeat able to make progress.
- A manually edited or malformed `outcome.cost_usd` can understate prior spend.
  The implementation treats malformed values as `0.0` to keep the read path
  tolerant, matching the inbox's human-editable posture.

**Neutral.**

- This does not introduce a queue, scheduler, or daemon. The Routine still owns
  when `heartbeat.py run` is invoked.
- This does not change `loop.py`'s own cost semantics; the heartbeat composes it.

## Alternatives considered

- **Keep only per-loop ceilings.** Rejected because it creates the `$2` to `$10`
  footgun for scheduled multi-candidate passes.
- **Require callers to pass `--max-candidates 1`.** Rejected because it moves a
  guardrail into scheduler configuration.
- **Use `.servo/runs/*/state.json` as the cost ledger.** Rejected because ADR-0010
  already made the triage inbox the heartbeat state spine and reserved
  `outcome.cost_usd` specifically for outcome accounting.
- **Make budget lifetime-cumulative across all inbox outcomes.** Rejected
  because once historical spend reached the default ceiling, future scheduled
  heartbeats would stop dispatching even though the slice requires remaining
  work to stay `open` for the next heartbeat.
- **Exit 2 on budget exhaustion.** Rejected because a budget halt is a completed,
  safe pass, not an environment error. The closed `{0,2}` contract keeps `2` for
  cases that prevent the operation.

## Verification

Slice 011-04 tests cover:

- `run` discovers then dispatches with the remaining budget forwarded to each
  loop.
- historical inbox `outcome.cost_usd` values do not drain a fresh run budget;
- current-pass spend below the floor halts before the next candidate and leaves
  remaining candidates open;
- an overspending loop halts the heartbeat before the next candidate;
- discovery env-errors prevent dispatch.

## References

- [Spec 011 slice 011-04](../specs/011-heartbeat/slice-04-heartbeat-cost-ceiling.md)
- [ADR-0010](adr-0010-triage-inbox-schema.md) - triage inbox schema and
  `outcome.cost_usd`.
- [Spec 003](../specs/003-agent-loop/spec.md) - loop-level cost ceiling.
- [Spec 005](../specs/005-variant-race/spec.md) - related per-race vs per-variant
  cost-ceiling question.
