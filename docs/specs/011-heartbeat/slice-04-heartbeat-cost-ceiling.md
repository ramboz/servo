---
status: DONE
dependencies: [011-03, adr-0012]
last_verified: 2026-06-18
---

## Slice 011-04 — heartbeat-cost-ceiling

**STATUS: DONE**

**Goal:** A **heartbeat-level** hard cost ceiling bounds *discovery (any LLM
assist) + the sum of all dispatched loops* — **not** per-loop. `heartbeat.py
run` = discover → dispatch under this one ceiling; **fail-closed** halt of the
whole pass leaves remaining findings `open` for the next run. Distinct from
`loop.py`'s per-run ceiling (003-02).

**DoR:**
- [x] 011-03 DONE and `outcome.cost_usd` is available in ADR-0010's inbox
      record shape.
- [x] The cost-ceiling decision is captured as an ADR before close-out.

**Acceptance Criteria:**

1. **`run` composes discovery and dispatch.** `heartbeat.py run <target>` first
   performs the same read-only discovery merge as `discover`, then dispatches
   actionable-open findings through the existing oracle-preflight/worktree/loop
   path. A discovery env-error exits 2 and prevents dispatch.
2. **One whole-pass budget.** `run --cost-ceiling USD` treats the value as the
   heartbeat-level ceiling, not a per-loop ceiling. The default is a hard whole
   pass ceiling, so an omitted flag cannot silently become N times `loop.py`'s
   per-run default.
3. **Current-pass spend accounting.** `run` captures a pass-start timestamp
   before discovery. Before dispatching, and again under the inbox lock, it sums
   `outcome.cost_usd` values recorded at or after that timestamp. Historical
   outcomes from earlier heartbeats do not drain a fresh scheduled budget, while
   completed candidates in the current pass count before the next loop starts.
4. **Remaining budget forwarded per loop.** Each loop receives the remaining
   whole-pass budget as its `--cost-ceiling` value. After each outcome is
   recorded, the next candidate's forwarded ceiling is recomputed from the
   updated inbox spend.
5. **Fail-closed between candidates.** When spent budget reaches the ceiling
   (or the remaining amount is below the dispatch floor), `run` stops before
   the next candidate, exits 0 with an explicit breadcrumb, and leaves remaining
   actionable-open findings `open` for the next heartbeat.
6. **Overshoot bound documented and tested.** Because `loop.py` can only be
   bounded by the forwarded per-run ceiling and heartbeat accounting happens
   between serial candidates, a run may overshoot by at most the cost of the
   last dispatched loop. Tests cover the halt-after-overshoot case.
7. **Existing dispatch remains per-loop.** `heartbeat.py dispatch
   --cost-ceiling USD` keeps its 011-03 meaning: the value is forwarded to each
   loop independently. Whole-pass accounting is only enabled by `run`.
8. **Closed exit contract preserved.** `run` uses the same `{0, 2}` surface:
   0 for completed passes, including empty candidate sets and budget halts; 2
   for env errors that prevent discovery or the pass-level oracle preflight.

**DoD:**
- [x] All ACs pass; focused `skills/heartbeat/test_heartbeat.py` tests green.
- [x] ADR for heartbeat-level cost semantics is written and indexed.
- [x] `docs/specs/README.md` regenerated.
- [x] Deviation log produced under this slice heading.

**Anti-horizontal-phasing check:** After this slice, a Routine can invoke one
real command (`heartbeat.py run`) that discovers work, dispatches it through the
existing loop, and stops spending before the next candidate once the heartbeat
budget is spent.

### Deviation log (after reconciliation)

**Reviewed implementation shape.**

- `heartbeat.py run` was implemented as `discover` followed by the existing
  011-03 `run_dispatch` pipeline with an optional `whole_cost_ceiling` mode,
  rather than a second dispatch implementation. `heartbeat.py dispatch
  --cost-ceiling` keeps its per-loop meaning.
- Review found and fixed one semantic bug before reconciliation: summing all
  historical inbox `outcome.cost_usd` values would make the default budget
  lifetime-cumulative and eventually starve future scheduled heartbeats. The
  reconciled contract is current-pass spend accounting: `run` captures a
  pass-start timestamp before discovery and only charges outcomes recorded at or
  after that timestamp.
- True crash-resumable heartbeat budgeting is not implemented. A later `run`
  starts with a fresh scheduled budget; completed historical outcomes remain
  audit history. Strict crash resume would need a heartbeat pass id or separate
  ledger and is intentionally deferred until that requirement crystallizes.
- The overshoot bound is unchanged: heartbeat can only stop between serial
  candidates, so an in-flight `loop.py` can spend up to the forwarded remaining
  budget before the next candidate is halted.

**Review evidence.**

- Compliance review: `docs/specs/011-heartbeat/reviews/slice-04-compliance.md`
  — pass.
- Craft review: `docs/specs/011-heartbeat/reviews/slice-04-craft.md` — pass.

**Verification evidence.**

- `python3 skills/heartbeat/test_heartbeat.py HeartbeatRunCostCeilingTests`
  — 5 passed.
- `python3 -m compileall -q skills/heartbeat/heartbeat.py
  skills/heartbeat/test_heartbeat.py` — passed.
- `uvx pytest skills/heartbeat/test_heartbeat.py` — 173 passed.
- `uvx ruff check skills/heartbeat/heartbeat.py
  skills/heartbeat/test_heartbeat.py` — passed.
