---
status: RECONCILED
kind: feature
dependencies: []
last_verified: 2026-11-10
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
- [x] All ACs pass; full test suite green (no regressions). 3.13: 2567 passed,
      10 skipped. The 3.9.6 run is green except two
      `test_gate_output_readback.py [forged]` cases, which fail identically on an
      `origin/main` baseline (deviation 7).
- [x] Tests use a mock `claude` that emits session-running-total payloads
      across `--resume`d iterations, plus one with an `advisor_message` iteration.
- [x] Each new test shown to fail when its feature is removed, with two
      exception classes (deviation 6): three negative guards, which cannot fail
      by design, and six round-2 tests whose red was not independently
      witnessed.
- [ ] Bug 007 record advanced to DONE, with this slice's test class as its
      regression test. It went through its own lifecycle; FIXING witnessed red
      on the pre-fix `loop.py`.
- [x] `skills/agent-loop/SKILL.md` and `docs/architecture.md` (state.json fields)
      updated; host packages regenerated (`scripts/build_host_packages.py`).
- [ ] Reviewed (compliance pass in round 2, craft pass); deviation log +
      reconciliation sweep; reconciliation review passed.

**Anti-horizontal-phasing check:** After this slice, a person reading
`state.json` or the loop's stdout can see, per iteration, which model ran and
what it cost, and the loop's cost brake reflects real spend.

### Deviation log (after reconciliation)

The original ACs are preserved above. What changed during implementation and
review:

1. **A fifth proof condition (AC3).** The proof also requires
   `reported total_cost_usd ≥ snapshot total_cost_usd`. If the token identity
   holds but the reported cost went down, the iteration falls back to
   `"reported"` rather than clamping the delta to 0, which would under-count.
   This came from a craft review note and is fail-safe in the AC's own
   direction.
2. **Zero-delta models dropped (AC2/AC3).** In delta mode, `model_usage` leaves
   out models whose per-field deltas are all zero: models this invocation did
   not use, which AC2 says to exclude.
3. **Breadcrumb suppressed under `--host copilot` (AC3).** Copilot reports no
   `modelUsage` and a USD cost of 0.0, so every resumed Copilot iteration
   would print the fallback breadcrumb. `_warn_reported_fallback` suppresses
   it off the Claude host; SKILL.md documents this and a unit test pins it. The
   Copilot loop is refused today (ADR-0043), so this cannot be exercised end to
   end.
4. **Goal-driver accounting covers every exit after the result is parsed
   (AC4).** Round 1 attached the keys only on the final-verdict path. Round 2
   builds them as soon as a result event exists, so the interrupt and
   `goal_unavailable` exits carry them too. Refusals that happen before
   invocation keep their shape.
5. **Small consolidations beyond the ACs.**
   - `cumulative_input_tokens` / `cumulative_output_tokens` now come from the
     same `_usage_record` helper as `usage`, so the two cannot disagree.
     Numeric strings and bools now count as 0, and a bad field zeroes only
     itself instead of the whole tally.
   - A `null` `session_id` now normalizes to `""` (`_session_id_of`). The old
     code produced `"None"`, which would have been persisted and passed as
     `--resume None`.
   - Non-finite numbers (NaN/inf) in `usage` / `modelUsage` count as absent.
     The top-level `total_cost_usd` still goes through the pre-existing bare
     `float()` in `_reported_total_cost`, so a NaN/inf cost there would still
     propagate. That behaviour predates this slice; hardening is folded into
     038-02's review round together with deviation 9.
6. **DoD exceptions: negative guards and unwitnessed round-2 reds.** `test_no_new_flags_added_to_argv`,
   `test_fresh_first_iteration_prints_no_breadcrumb` and
   `test_refusal_before_invoke_has_no_accounting_keys` check that behaviour is
   preserved, so they cannot fail when the feature is removed. The slice's test
   block now holds 33 tests: 25 from round 1, of which 22 were witnessed red
   before implementation, plus 8 added with the round-2 review fixes. Two of
   the 8, `test_returned_session_id_must_match_resumed_id` and
   `test_goal_unavailable_exit_carries_accounting`, were witnessed red by
   mutation. Red was witnessed for the following:
   - disabling the delta proof turns 4 of the 6 `ResumedSessionCostDeltaTests`
     red;
   - deleting the returned-id condition turns
     `test_returned_session_id_must_match_resumed_id` red;
   - turning the goal accounting off turns the two goal accounting tests red.

   The other round-2 tests were written with their fixes, and red was not
   independently witnessed for each:
   - `test_reported_cost_below_snapshot_falls_back_to_reported`;
   - `test_cost_below_snapshot_falls_back_to_reported`;
   - `test_delta_drops_models_not_used_this_invocation`;
   - `test_non_finite_numbers_count_as_absent`;
   - `test_null_session_id_is_empty_string`;
   - `test_breadcrumb_suppressed_off_claude_host`. Its Copilot case tests the
     deviation-3 suppression, which round 1 did not have. Its `session_delta`
     and no-resume cases are negative guards. Its Claude-host case expects a
     warning that round 1 already printed.

   Each asserts behaviour that the round-1 code did not have, as the round-1
   compliance and craft findings record.
7. **Pre-existing 3.9 failures.** Two `skills/quality-gate/test_gate_output_readback.py`
   `[forged]` cases fail under the macOS 3.9.6 interpreter
   (`~/Library/Caches/com.apple.python` bytecode-cache prefix). They fail
   identically on an `origin/main` baseline worktree, so they are unrelated to
   this slice.
8. **Per-iteration stdout key order.** The accounting keys sit between
   `cost_usd` and `cumulative_cost_usd`. This is additive; no key was renamed.
9. **Residual: an empty snapshot weakens the token check.** The bug-007 review
   found that when the previous response carried no `modelUsage`, the snapshot
   has no tokens. The identity check then passes trivially, and only the
   `reported ≥ snapshot cost` condition still guards. Under the evidenced
   semantics the result is still correct. Hardening, which requires snapshot
   tokens > 0, is folded into 038-02's review round, so `loop.py` has a single
   writer at a time.

### Reconciliation sweep

| Artifact | Disposition | Rationale |
|----------|-------------|-----------|
| `README.md` | `no-op` | The front door does not describe state.json fields; no user-facing claim changed. |
| `docs/specs/README.md` | `deferred` | Regenerated by `workflow.py status-board` at close, before DONE. |
| `docs/product-vision.md` | `no-op` | Checked; no scope or positioning change. |
| `docs/architecture.md` | `updated` | State.json accounting fields, the cost-basis rule, goal-driver flat accounting keys, and `agent` added to the stdout key list. |
| Primer surfaces: `CLAUDE.md` / `AGENTS.md` / scaffold templates | `no-op` | servo has no root primer; scaffold templates don't describe loop state. |
| `docs/inbox.md` | `no-op` | servo has no inbox file. |
| `docs/refinement-todo.md` | `updated` | Spike Q5 annotated: `--max-budget-usd` scope verified per-invocation (halt granularity still open). New entry "Spec 038-01 hardening carried into 038-02's review round" tracks deviations 5 and 9. |
| `docs/memory/**` | `updated` | `learnings.md`: resumed-session running totals and the delta rule (bug 007). |
| `docs/decisions/README.md` / ADR index | `no-op` | This slice adds no ADR; ADR-0047's index entry landed with its acceptance. |
| `docs/bugs/007-…` + bug board | `deferred` | The record is updated (Fix, closure, proof, learning). The bug is at FIXING with bug-review and craft evidence recorded. REVIEWED → DONE and `bug.py status-board` run at close, before 038-01 is marked DONE (the DoD item stays unticked until then). |
| `skills/agent-loop/SKILL.md` + generated `hosts/**` | `updated` | Output-shape docs; hosts regenerated and drift-checked. |
| Slice file set | `no-op` | Commit 44b72f5 touches `skills/agent-loop/{loop.py,test_loop.py,SKILL.md}`, `docs/architecture.md`, generated `hosts/**`, bug 007 and review evidence. `agents/runner.md` / `agents/judge.md` are unchanged; a stale local `main` makes `git diff main...HEAD` unusable for this check. |
