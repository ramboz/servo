---
status: DRAFT
kind: spike
dependencies: []
last_verified:
frame_review: true
---

## Slice 041-01 — Copilot contract probe

**Goal:** Settle ADR-0048 A1–A5 with executed Copilot CLI runs, so the credit
brake's arithmetic rests on evidence rather than on help text.

**Question:** Does `copilot -p --usage-output-file` report per-invocation AI
credits (`totalNanoAiu`)? Specifically:
- does a report exist after a timeout or kill;
- on `--resume=<sid>`, are the cap and the report scoped to the session or to
  the invocation;
- does a report mark itself partial?

**Time-box:** 2 hours, and at most 150 AI credits of billed usage (ADR-0048
open question 4 shows the arithmetic).

**DoR:**
- The owner authorizes the billed probe (ADR-0048 open question 4).

**Acceptance Criteria:**

1. A fresh `copilot -p` run with `--usage-output-file` and
   `--max-ai-credits 30` records `totalNanoAiu`, `totalPremiumRequestCost`,
   `modelMetrics` and `agentMetrics`. Raw files are kept under
   `docs/specs/041-host-aware-budget-unit/evidence/`, redacted of any account
   identifiers.
2. A `--resume=<sid>` second run shows whether `totalNanoAiu` is the
   invocation's or the session's running total (A2), compared against the first
   run. It also shows whether `--max-ai-credits` measures the session total
   (cap set below the session total but above one call's cost).
3. A run killed by servo's timeout path shows whether a usage file is written
   (A3).
4. Subagent and compaction usage appear in `agentMetrics` / `totalNanoAiu` (A1),
   or are recorded as unobserved.
5. Legacy-billing behaviour (A4) is recorded as observed, or as unobservable on
   this account. For partial cost (A5), the probe records whether the JSON
   carries a partial marker, and whether ADR-0048's derived check can be
   computed from `modelMetrics` (tokens present with zero credits). If neither
   is possible, ADR-0048's partial-cost kill criterion fires, and 041-02 stays
   blocked.
6. **Overrun (A6).** On the run whose spend crosses its `--max-ai-credits` cap,
   record `spend − cap` and how many model calls were in flight at the
   crossing, from `agentMetrics` and the timeline. Also record whether subagent
   spawning can be denied for the worker invocation, so *k* = 1. Compare the
   overrun against the per-call maximum computed from `/model`'s "Credits Per 1M
   Tokens" and the model's context window.

**Findings:** _Filled during IN_PROGRESS._

**Outcome:** _One of `spec 041-02 unblocked` / `ADR-0048 revised` / `abandoned (reason)`._

**DoD:** findings recorded with raw evidence; ADR-0048's Assumptions updated
to cite them; compliance review passed.

**Anti-horizontal-phasing check:** the credit brake's per-iteration
arithmetic is chosen from observed CLI behaviour, the way bug 007's fix was
for Claude.
