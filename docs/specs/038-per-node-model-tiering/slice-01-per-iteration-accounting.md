---
status: IN_PROGRESS
kind: feature
dependencies: []
last_verified:
frame_review: true
claimed_by: claude/model-tiering
---

## Slice 038-01 — per-iteration accounting

**Goal:** Every scored iteration of the loop driver, and the goal driver's single
invocation, records which model(s) ran, the effort servo requested, what the
invocation actually cost and its token usage in `state.json` and on stdout. As
part of this, the loop's running cost becomes accurate on resumed sessions
(fixes [bug 007](../../bugs/007-agent-loop-overcounts-resumed-session-cost.md)).

**DoR:**
- ✅ Real `claude -p` JSON shape probed (spec 038 "Grounded starting point"):
  per-invocation `usage`; session-running-total `total_cost_usd` / `modelUsage`
  on `--resume`; advisor consults visible as `usage.iterations[].type ==
  "advisor_message"` with a `model`.
- ✅ Bug 007 diagnosed (root cause + closure inventory recorded).
- ✅ `--max-budget-usd` probed as per-invocation on a resumed session, and the
  running-total identity probed on a two-turn invocation (spec 038 grounding).

**Acceptance Criteria:**

1. **History entries carry accounting.** Each `oracle_score_history` entry the
   loop driver appends after a scored iteration keeps its existing keys and
   adds `agent` (`runner`|`judge`), `session_id`, `cost_usd`, `cost_basis`,
   `usage`, `model_usage`, `model` and `requested`. `usage` is
   `{input_tokens, cache_read_input_tokens, cache_creation_input_tokens,
   output_tokens}` read from the invocation's top-level `usage` (ints;
   absent/non-numeric → 0). `requested` is `{model, effort, advisor}` naming
   the flags servo passed; all `null` in this slice, because servo passes none.
   The per-iteration stdout line carries the same keys (its existing
   `session_id` / `agent` / `cost_usd` keys keep their names).
2. **Per-model breakdown with advisor attribution.** `model_usage` maps each
   model id the invocation used to `{cost_usd, input_tokens, output_tokens,
   cache_read_input_tokens, cache_creation_input_tokens}`, taken from Claude's
   `modelUsage` (`costUSD`, `inputTokens`, …; absent/non-numeric → 0). It is
   per-invocation: on a resumed session it is the difference from the previous
   snapshot (AC3). An entry whose id appears as the `model` of a
   `usage.iterations[]` element with `type == "advisor_message"` also carries
   `"advisor": true`. `usage.iterations` covers only the final API call of the
   invocation, so this flag is best-effort (spec 038 A1); 038-02 adds servo's
   requested advisor as a second signal. `model` is the non-advisor entry with the highest
   `cost_usd` (first in `modelUsage` order on a tie), or `null` when there is
   none. A missing or malformed `modelUsage` gives `model_usage: {}` and
   `model: null`, and never fails the iteration.
3. **Cost is the invocation's own cost (bug 007).** The loop persists, in
   `state.json` as `current_session_usage_snapshot`, a snapshot of the last
   running totals Claude reported for `current_session_id` (`total_cost_usd` +
   per-model `modelUsage`), so it survives `--resume <run-id>`. Running-total semantics are
   proven when all of these hold:
   - the iteration passed `--resume S`;
   - Claude returned the same id `S`;
   - a snapshot for `S` exists;
   - the summed `modelUsage` tokens are ≥ the snapshot's summed tokens plus
     this invocation's `usage` tokens.

   When proven, `cost_usd` is `total_cost_usd − snapshot total_cost_usd`, and
   each `model_usage` value is the per-field difference from the snapshot
   (floored at 0), and `cost_basis` is `"session_delta"`. Otherwise `cost_usd`
   is the reported `total_cost_usd`, `model_usage` is `modelUsage` as
   reported, and `cost_basis` is `"reported"`. Under the probed resume
   semantics the unproven case therefore over-counts, never under-counts, and
   is visible in the record. One residual remains, never observed: a same-id
   resume whose totals were *not* reloaded, while `modelUsage` carries
   advisor/subagent tokens absent from `usage` that are at least the
   snapshot's token total. That case could pass the proof and under-count. A resumed
   iteration that falls back to `"reported"` also prints one stderr breadcrumb.
   `cumulative_cost_usd` is the sum of the
   per-iteration `cost_usd` values, and that sum also feeds the cost-ceiling
   brake and the per-iteration `--max-budget-usd`. The snapshot is
   replaced after every invocation that sets `current_session_id`.
4. **Goal driver records its invocation.** After the goal driver parses a
   `result` event, its `state.json` and summary line gain `session_id`, `usage`,
   `model_usage`, `model`, `requested` and `cost_basis: "reported"`, with the
   same shapes and rules as AC1-2.
   The invocation is fresh, so cost is the reported total and the
   existing `cumulative_cost_usd` is unchanged. Refusal paths that never invoke
   Claude keep their current summary shape.
5. **No new flags, no halt change.** No iteration's `claude` argv gains a flag.
   The one value that changes is `--max-budget-usd`: it is computed from the
   corrected cumulative (AC3). Iteration 2's value comes from iteration 1's
   fresh cost and is unchanged, so the value first differs at iteration 3 and
   is larger than before from there on. `--max-budget-usd` was probed as a per-invocation cap,
   so this is the intended correction. Apart from cost accuracy, the halt
   reasons, exit codes and per-iteration ordering are unchanged.
6. **Old state resumes.** A `state.json` written before this slice (history
   entries without accounting, no snapshot) resumes without error. Its entries
   are left as they were, and the first resumed iteration's `cost_usd` is the
   reported `total_cost_usd` (no snapshot, so it is fail-safe). `state_schema_version`
   stays `1` (ADR-0004 additive clause).

### Behavioral rules

| Rule | Operation/control | Actor | State/precondition | Outcome | Rationale | AC |
|------|-------------------|-------|--------------------|---------|-----------|----|
| BR-1 | cost of an iteration | loop driver | resumed same session, running-total semantics proven | reported total − snapshot total | Claude reports session running totals on `--resume` | AC3 |
| BR-2 | cost of an iteration | loop driver | fresh session, different id returned, no snapshot, or proof fails | reported total | fail-safe: over-count, never under-count | AC3, AC6 |
| BR-3 | primary `model` | loop + goal driver | advisor consult present | the non-advisor model with highest cost | the advisor's uncached read can out-cost the executor | AC2 |

**DoD:**
- [ ] All ACs pass; full test suite green (no regressions).
- [ ] Tests use a mock `claude` that emits session-running-total payloads
      across `--resume`d iterations, plus one with an `advisor_message` iteration.
- [ ] Each new test shown to fail when its feature is removed.
- [ ] Bug 007 record advanced to DONE, with this slice's test class as its
      regression test.
- [ ] `skills/agent-loop/SKILL.md` and `docs/architecture.md` (state.json fields)
      updated; host packages regenerated (`scripts/build_host_packages.py`).
- [ ] Reviewed (compliance + craft); deviation log + reconciliation sweep;
      reconciliation review passed.

**Anti-horizontal-phasing check:** After this slice, a person reading
`state.json` or the loop's stdout can see, per iteration, which model ran and
what it cost, and the loop's cost brake reflects real spend.

### Deviation log (after reconciliation)

_Filled at reconciliation._

### Reconciliation sweep

_Filled at reconciliation._
