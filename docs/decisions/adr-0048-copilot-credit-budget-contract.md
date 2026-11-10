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
ADR, followed by positive native invocation/tool/context/resume evidence".

What the CLI documents (`copilot` 1.0.109-1; spec 041 grounding has the
captures):

- **Unit:** usage is measured in **AI credits**, or in premium requests on the
  legacy billing platform. Each model call costs its tokens at the model's
  per-token price; `/model` lists "Credits Per 1M Tokens".
- **Context growth:** every call resends the conversation, so input "can reach
  millions" of tokens.
- **Report:** `--usage-output-file` writes final usage as JSON, including
  `totalNanoAiu` (10^9 nano AIU = 1 AI credit), `totalPremiumRequestCost`,
  `modelMetrics` and `agentMetrics`, when the session ends, also for `-p` runs.
- **Cap:** `--max-ai-credits <credits>` caps "this session", with a minimum of
  30. It is a soft cap: "usage is known only after a response returns, so one
  response can go past the limit; the next model call is then blocked. Hidden
  work such as compaction counts too." Subagents share the session's limit,
  and the CLI ships parallel subagent work (`--fleet`).
- **Partial reports:** `/usage` can say "Reported AI credits … (partial)",
  meaning some calls reported no cost.

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

- **Pros:** honest, since it is the host's own unit; enforceable at the
  granularity servo already uses for USD; and it unblocks 034-03's budget
  condition.
- **Cons:** within an invocation the cap is soft, so the overrun policy below
  is what the owner actually accepts. There is no context brake.

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
contract has six parts:

1. **Unit:** AI credits (`totalNanoAiu / 1e9`), held in its own fields
   (`cumulative_credits`, `credit_ceiling`), never mixed with USD fields.
   038-01's per-iteration accounting gains `cost_native: {unit: "ai_credits",
   value}`.
2. **Hard between invocations, soft within, with a stated overrun bound.**
   - Total spend can exceed the ceiling by at most the overrun of the last
     invocation.
   - That overrun is **(1 + c) × the per-call maximum**:
     - *1* is the main model call that crosses the cap;
     - *c* is the number of background calls that can be in flight with it.
       Compaction cannot be denied, and it fires near full context, which is
       exactly when the crossing call is largest. So *c* = 1 unless 041-01
       observes a compaction crossing and shows otherwise.
     - The per-call maximum is the model's context window × max(input price,
       cache-write price), plus maximum output × output price, all from
       `/model`'s "Credits Per 1M Tokens".
   - servo's Copilot worker runs with **no subagents**: no `--fleet`, and
     subagent spawning denied via the CLI's tool-denial flags. If 041-01 shows
     spawning cannot be denied, the native loop **stays refused**; the bound is
     not weakened to an observed sample.
   - With no context brake (part 4), the call that crosses the cap is also the
     run's largest. So the overrun bound and the missing context brake are one
     acceptance (Open question 1).
   - **Launch refuses when the bound swamps the budget.** If the computed
     bound for the worker model is at least the credit ceiling, `loop.py`
     refuses to launch and names the smallest sensible ceiling. Otherwise a
     small ceiling would be a budget in name only.
3. **Fail closed on missing or partial telemetry.**
   - A missing or unreadable usage report halts the run, and spend is reported
     as `null`, not 0. So does a timed-out or killed invocation whose usage
     file was not written.
   - A report that is partial halts the run the same way. The CLI defines
     partial as "some calls reported no cost", which is a per-call property.
     The usage JSON is per model and per agent, so it cannot detect a mixed
     partial. servo therefore reads **per-call** cost from the CLI's
     OpenTelemetry file export, which carries `github.copilot.nano_aiu` and
     token counts per call. Any call with tokens and no cost means the report
     is partial. If per-call telemetry is unavailable for `-p` runs, the A5
     kill criterion fires.
   - The span stream must itself be complete, or an empty file would read as
     "no partial calls" and fail open:
     - servo pins the exporter env vars (`COPILOT_OTEL_EXPORTER_TYPE`,
       `COPILOT_OTEL_FILE_EXPORTER_PATH`) on every worker invocation, so an
       inherited or managed setting cannot redirect them;
     - a missing, empty or unparseable span file is **unavailable**: halt
       `credit_usage_unavailable` with spend `null` (ADR-0043 §3);
     - if Σ per-call `nano_aiu` ≠ `totalNanoAiu`, or the span token sums ≠
       `modelMetrics`, the report counts as partial.
4. **Explicit bounds required.** `--host copilot` runs only with a credit
   ceiling and an explicit `--max-iterations`. Context is recorded as
   unavailable (`null`).
5. **Oracle spend is not covered by the credit ceiling.** The ceiling bounds the
   worker's Copilot session only. Under `--host copilot`, an oracle whose
   components spend USD, such as API-priced eval judges, is **refused** unless
   the owner approves a separate USD oracle ceiling (Open question 5). This
   keeps ADR-0041's rule: no unbounded spend, and no priced component without
   an approved accounting policy.
6. **Heartbeat keeps units apart.** A heartbeat pass uses one unit. A whole-pass
   credit ceiling sums credit outcomes only, and mixing USD and credit outcomes
   in one ceiling refuses.

**What accepting this relaxes, explicitly.** ADR-0043's refusal is lifted for
the **loop driver** only, once the contract is implemented (spec 041-02) and
034-03's invocation, tool and resume evidence is in place. Accepting this ADR
also **relaxes two of 034-03's conditions**:

- its "context" evidence: context stays unavailable, replaced by an explicit
  `--max-iterations` (part 4);
- its "hard in-flight bounds": the in-flight bound is part 2's stated overrun,
  not a hard cap.

The goal driver stays refused (034-07).

## Consequences

**Becomes easier:**

- servo's per-node discipline (oracle, plateau, ladder, budget) can wrap a
  Copilot worker. That is the precondition for host-driven campaigns.
- Spend is visible in the host's own unit instead of being silently 0.

**Becomes harder:**

- Two budget units exist, so every budget surface must keep them apart.
- A ceiling below 30 credits can never run.
- Copilot targets with USD-priced oracle components stay refused until Open
  question 5 is answered.

## Assumptions

All six come from the CLI documentation alone; spec 041-01's billed probe
settles them.

- **A1:** per-invocation `totalNanoAiu` is written for completed `-p` runs and
  covers subagents and compaction.
- **A2:** whether `--max-ai-credits` and `totalNanoAiu` count the whole session
  on `--resume=<sid>` or only the invocation. This is the Copilot analogue of
  Claude's bug 007. It decides whether the per-invocation cap and the
  per-iteration cost are computed directly or as a difference from a session
  snapshot. Either answer is workable.
- **A3:** whether a usage file is written after a timeout or kill. Either answer
  is workable, because part 3 fails closed.
- **A4:** whether legacy-billing accounts populate `totalNanoAiu` at all.
- **A5:** whether the OpenTelemetry file export gives per-call cost and tokens
  for `-p` runs, so that part 3's per-call partial check can run.
- **A6 (the overrun bound):**
  - the overrun past a cap is at most (1 + c) × the per-call maximum, with
    *c* = 1 for compaction;
  - subagent spawning can be denied;
  - no other background model work runs concurrently.

## Kill criteria

- **No usable report.** If 041-01 shows no usage report for *completed* `-p`
  runs, or a report that leaves out subagent or compaction spend, keep
  refusing (Option D). The brake would undercount.
- **Partial cost undetectable.** If A5 is negative (no per-call cost telemetry
  for `-p` runs), keep refusing. A subtotal read as a total fails open.
- **Overrun beyond the stated bound.** Part 2's bound does not hold if any
  observed invocation's overrun past its `--max-ai-credits` exceeds part 2's
  (1 + c) × the per-call maximum. That maximum is computed for the model that
  ran, from `/model` prices and its context window. Revisit before relying on
  the bound. The comparison runs in the 041-01 probe and in every later run:
  041-02 records the overrun next to the bound and emits
  `overrun_exceeds_bound` when the bound is broken.
- **Subagent spawning cannot be denied.** Keep refusing (part 2).

## Open questions (owner)

1. **Overrun and context, one decision.** Is part 2's overrun bound
   acceptable as ADR-0043's "separately recorded budget policy", given that
   the context brake is unavailable so the crossing call is the run's largest?
   The bound is (1 + c) × the per-call maximum, with *c* = 1 for compaction;
   for a large model this can be a large number of credits. 041-01 computes it
   for the default worker model from `/model` prices, giving the owner a
   number rather than a formula before acceptance. It is checked again on every
   later run, and launch refuses when it is at least the ceiling.
2. **Legacy-billing accounts:** refuse, or brake on premium requests as a
   second unit?
3. **Single-threaded worker:** is denying subagent spawning acceptable, given
   it may reduce what the Copilot worker can do?
4. **Billed probe:** authorize spec 041-01's probe, capped at **150 AI
   credits**? Run 1 needs to spend past the 30-credit minimum cap so the
   resume test means something (about 40–60). The resumed run (about 30–40)
   and the timed-out run (about 30) come on top, plus margin.
5. **USD-priced oracle components under Copilot:** keep refusing them (the
   default), or approve a separate USD oracle ceiling?
