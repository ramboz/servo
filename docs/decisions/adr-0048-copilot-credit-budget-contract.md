---
status: Proposed
dependencies: [adr-0038, adr-0041, adr-0043, adr-0047]
last_verified:
frame_review: true
---

# ADR-0048: Copilot AI-credit budget contract for the native loop

## Status

Proposed (2026-11-10). **Owner acceptance required.** This ADR is the
"separately recorded budget policy" that ADR-0043's kill criterion asks for.
It stays Proposed until the owner explicitly accepts its text. A relayed
priority is not acceptance.

## Context

servo refuses its native loop on GitHub Copilot CLI (ADR-0043). In a recorded
two-day multi-session Copilot campaign, servo never ran, and that refusal was
the first cause. The workers that ran instead lacked a budget, a plateau brake
and a context brake; one fixer made 1,383 calls.

ADR-0043 refused for two reasons. `--max-ai-credits` is a **soft** cap, and
"credits are not dollars", and converting them to USD was rejected (its
Option B). Its kill criterion: revisit "when an executed native contract proves
the requested guarantees, or the owner accepts a separately recorded budget
policy". Spec 034-03 (native loop, DEFERRED) carries the same trigger: "an
explicit owner-approved replacement monetary/credit policy recorded in a new
ADR".

What the CLI documents (`copilot` 1.0.109-1; spec 041 grounding has the
captures):

- **Unit:** usage is measured in **AI credits**, or in premium requests on the
  legacy billing platform. Each model call costs its tokens at the model's
  per-token price.
- **Report:** `--usage-output-file` writes final usage as JSON, including
  `totalNanoAiu` (10^9 nano AIU = 1 AI credit), `totalPremiumRequestCost`,
  `modelMetrics` and `agentMetrics`, when the session ends, also for `-p` runs.
- **Cap:** `--max-ai-credits <credits>` caps "this session", with a minimum of
  30. It is a soft cap: "usage is known only after a response returns, so one
  response can go past the limit; the next model call is then blocked. Hidden
  work such as compaction counts too." Usage accumulates across the whole
  session, including subagents.

servo today stores no credit spend. It reads a missing usage file as zero
(`skills/agent-loop/loop.py` `_parse_copilot_usage`), and the heartbeat turns a
non-numeric cost into `0.0`. Both contradict ADR-0043's "unavailable is null,
not zero" rule.

## Decision Options Considered

### Option A (recommended): a credit-denominated brake that servo enforces between invocations

The brake is in AI credits, a unit of its own, never converted. servo keeps a
cumulative credit total from each invocation's reported `totalNanoAiu`:

- **Pre-iteration:** halt `credit_ceiling_reached` when the credits left are
  under the 30-credit CLI minimum.
- **Each invocation:** pass `--max-ai-credits` set to the credits left, adjusted
  for session-scope semantics as spec 041-01 establishes.
- **Post-iteration:** halt when the total exceeds the ceiling.
- **Missing or partial usage report:** halt `credit_usage_unavailable`. It is
  never zero.

**Overrun policy, stated for the owner to accept:** total spend can exceed the
ceiling by the overrun of the last invocation, meaning its over-cap model
call(s) and any compaction. The CLI documents this overrun but gives no bound
for it. The USD brake has the same between-invocation shape. The context brake
is **unavailable** under Copilot (no context window is reported), so it is
recorded as `null`, and a Copilot run must set an explicit `--max-iterations`.

- **Pros:** honest, since it is the host's own unit; enforceable at the
  granularity servo already uses; and it unblocks 034-03's budget condition.
- **Cons:** the overrun has no documented numeric bound; no context brake.

### Option B: premium requests as the unit (the first spec 041 sketch)

- **Cons:** premium requests are the legacy billing unit; one prompt ×
  model multiplier; fractional values are truncated by today's parser. They also
  don't track token-heavy autonomous continuation. Rejected as the primary
  unit. On legacy-billing accounts it is the only unit; see Open questions.

### Option C: convert credits to USD

Rejected by ADR-0043 Option B. Nothing new justifies revisiting it.

### Option D: keep refusing (status quo)

- **Cons:** servo stays unusable on the host where its per-node discipline was
  most missed. Rejected if the owner accepts Option A's overrun policy.

## Recommended Decision

Option A, effective only once the owner explicitly accepts this ADR. The
contract has five parts:

1. **Unit:** AI credits (`totalNanoAiu / 1e9`), held in its own fields
   (`cumulative_credits`, `credit_ceiling`), never mixed with USD fields.
   038-01's per-iteration accounting gains `cost_native: {unit: "ai_credits",
   value}`.
2. **Hard between invocations, soft within:** the brakes are as in Option A,
   and the overrun policy is as stated.
3. **Fail closed on missing telemetry.** A missing, unreadable or partial usage
   report halts the run, and spend is reported as `null`, not 0. A timed-out or
   killed invocation whose usage file was not written is treated the same way.
4. **Explicit bounds required.** `--host copilot` runs only with a credit
   ceiling and an explicit `--max-iterations`. Context is recorded as
   unavailable (`null`).
5. **Heartbeat keeps units apart.** A heartbeat pass uses one unit. A whole-pass
   credit ceiling sums credit outcomes only, and mixing USD and credit outcomes
   in one ceiling refuses.

ADR-0043's refusal is lifted for the **loop driver** only, once the contract is
implemented (spec 041-02) and 034-03's remaining native invocation, tool and
resume evidence is in place. The goal driver stays refused (034-07).

## Consequences

**Becomes easier:**

- servo's per-node discipline (oracle, plateau, ladder, budget) can wrap a
  Copilot worker. That is the precondition for host-driven campaigns.
- Spend is visible in the host's own unit instead of being silently 0.

**Becomes harder:**

- Two budget units exist, so every budget surface must keep them apart.
- A ceiling below 30 credits can never run.

## Assumptions

All five come from the CLI documentation alone; spec 041-01's billed probe
settles them.

- **A1:** per-invocation `totalNanoAiu` is written for `-p` runs and covers
  subagents and compaction.
- **A2:** whether `--max-ai-credits` and `totalNanoAiu` count the whole session
  on `--resume=<sid>` or only the invocation. This is the Copilot analogue of
  Claude's bug 007. It decides whether the per-invocation cap and the
  per-iteration cost are computed directly or as a difference from a session
  snapshot.
- **A3:** whether a usage file is written after a timeout or kill.
- **A4:** whether legacy-billing accounts populate `totalNanoAiu` at all.
- **A5:** whether a partial report is marked as partial in the usage file.

## Kill criteria

- If 041-01 shows `totalNanoAiu` is not reported per invocation, or not after
  an interrupted invocation, the brake cannot fail closed reliably. Keep
  refusing (Option D).
- If observed overruns past the cap routinely exceed a stated multiple of the
  cap, the "one response" policy is not a budget. Revisit.

## Open questions (owner)

1. Is Option A's overrun policy acceptable as ADR-0043's "separately recorded
   budget policy"? Its only bound is one over-cap response plus compaction,
   with no numeric limit.
2. Legacy-billing accounts: refuse, or brake on premium requests as a second
   unit?
3. Is "context unavailable, explicit `--max-iterations` required" acceptable in
   place of a context brake?
4. Authorize spec 041-01's billed live probe (about 60 AI credits across a fresh
   run, a resumed run and a timed-out run)?
