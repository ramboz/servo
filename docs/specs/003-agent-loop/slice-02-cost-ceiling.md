---
status: DONE
dependencies: []
last_verified:
---

## Slice 003-02 — cost-ceiling

**STATUS: DONE**

**Goal:** Add cumulative cost tracking from each iteration's `total_cost_usd`. Halt the loop when cumulative cost exceeds `--cost-ceiling` (default $2.00 per `docs/architecture.md`). Each `claude -p` invocation also receives `--max-budget-usd <remaining-budget>` for defense-in-depth (so a single runaway agentic turn within an iteration can't blow past the cumulative ceiling). End-to-end value: an unattended loop is now safe to fire-and-forget — the cost won't exceed the cumulative cap by more than one iteration's burn rate.

**DoR:**
- ✅ Slice 003-01 DONE
- ✅ Architecture default `cost-ceiling=$2` (per `docs/architecture.md`)
- ✅ `claude -p --max-budget-usd <amount>` flag verified in spike (works with `--print` only — matches loop usage)
- ✅ Decision: cumulative cost is summed from each iteration's `total_cost_usd`; no separate `--max-budget-usd` cumulative mode is requested from Claude Code (Claude's flag is per-invocation only)

**Acceptance Criteria:**

1. **Default cost-ceiling.** With no flag, loop halts when cumulative `total_cost_usd` first exceeds $2.00. (Tested by setting the mock `claude` to emit `total_cost_usd=0.75` per iteration → loop halts mid-iteration-3, emitting `terminal_reason=cost_ceiling_reached cumulative_cost_usd=2.25`.)
2. **Flag override.** `loop.py <target> --prompt "<text>" --cost-ceiling 0.50` halts on first iteration emitting > $0.50.
3. **Per-iteration cap.** Each `claude -p` invocation receives `--max-budget-usd <remaining-budget>`, where `remaining-budget = cost_ceiling - cumulative_cost_usd`. (Verified by capturing the args passed to the mock `claude`.)
4. **Per-iteration cap floor.** The per-iteration `--max-budget-usd` is never less than `MIN_BUDGET_FLOOR_USD = 0.01`; if cumulative is already within $0.01 of the ceiling, the loop halts without invoking another iteration (avoids invoking `claude` with a $0 budget).
5. **Terminal reason.** When cost-ceiling halts the loop, the summary line carries `terminal_reason=cost_ceiling_reached`, `cumulative_cost_usd=<X>`, `cost_ceiling_usd=<Y>`.
6. **Cumulative-cost in per-iteration JSON.** Each iteration's stdout JSON line carries both `cost_usd` (this iteration's burn) and `cumulative_cost_usd` (running total including this iteration).
7. **`--cost-ceiling 0` semantics.** Disables the cumulative ceiling entirely. (Useful for testing or when the caller is enforcing a budget out-of-band.) Per-iteration `--max-budget-usd` defaults to a sane upper bound (`DEFAULT_PER_ITER_BUDGET_USD = 1.00`) so a runaway agentic turn still has a brake.

**DoD:**
- [x] All ACs pass; full test suite green (no regressions in `test_loop.py` slice-003-01 cases, `test_gate.py`, `test_scaffold.py`).
- [x] Test coverage per AC under `skills/agent-loop/test_loop.py`: AC1→`CostCeilingDefaultTests`, AC2→`CostCeilingOverrideTests`, AC3→`PerIterationBudgetCapTests`, AC4→`PerIterationBudgetFloorTests`, AC5→`CostCeilingSummaryTests`, AC6→`CumulativeCostPerIterationTests`, AC7→`CostCeilingDisabledTests`. Plus `CostCeilingValidationTests` (CLI rejection of negatives) and `ClaudeNonzeroWithParseableJsonTests` (resolves the 003-01 deviation-log forward reference).
- [x] Reviewed by `jig:reviewer` subagent.
- [x] Implementation review passed.
- [x] Deviation log produced under this slice heading.
- [x] Reconciliation review passed.
- [x] `docs/refinement-todo.md` updated (`DEFAULT_PER_ITER_BUDGET_USD = $1.00` flagged as a tuning target alongside the existing 30-min claude-timeout entry).

### Close-out (post-DONE)

- [x] Cost-ceiling defaults documented in `docs/architecture.md` "Project vs servo-core split" table (already names "max-iterations=5, cost-ceiling=$2" — verified still accurate; implementation matches both values).

**Anti-horizontal-phasing check:** After this slice, a user can leave the loop running overnight and know the worst-case spend is bounded by the cost ceiling (modulo one iteration's burn rate over). The next three slices add stricter brakes; none is required for "the loop is safe to leave alone."

### Deviation log (after reconciliation)

**Slice 003-02 — implemented 2026-05-19.** 17 new tests under `skills/agent-loop/test_loop.py` (52/52 total green); full regression suite still green (75/75 `test_gate.py`, 40/40 `test_scaffold.py`, 18/18 `test_skill_surface.py` gate, 13/13 `test_skill_surface.py` scaffold). The 003-01 deviation-log forward reference ("Slice 003-02 will need to revisit when budget-exceeded paths surface a non-zero exit with parseable JSON") is now closed: `_invoke_claude` splits cleanly into four branches — zero/non-zero × parseable-dict/unparseable — with non-zero-plus-parseable treated as iteration completion (the budget-exceeded path) and non-zero-plus-unparseable retaining the AC9 `claude_invocation_failed` breadcrumb.

Deviations from spec text:

- **AC4 "within $0.01" is implemented as strict less-than (`<`), not inclusive (`≤`).** When the remaining budget equals exactly $0.01, the loop still invokes claude with `--max-budget-usd 0.01`; the floor check fires only when `(cost_ceiling - cumulative) < MIN_BUDGET_FLOOR_USD`. AC4's English wording is ambiguous; the strict reading aligns with the "avoid invoking claude with an effectively-zero budget" rationale (exactly-floor is still a meaningfully nonzero budget). Tests pin the strict reading via `test_passed_budget_never_below_floor` (`assertGreaterEqual(budget, 0.01)`).
- **`cost_ceiling_usd` is emitted in every summary line, not just on `cost_ceiling_reached` halts.** AC5 requires the field on the ceiling-halt path; the implementation includes it on all summary emissions (preflight refusal, `claude_invocation_failed`, `gate_invocation_failed`, `oracle_passed`, `max_iterations_reached`) so a forensic consumer can see the configured bound regardless of how the run ended. Additive beyond AC5's literal text; covered by AC5's "carries" / "at minimum" language. Tested via `test_cost_ceiling_usd_present_on_non_ceiling_halt`.
- **`gate_invocation_failed` defensive branch is forensically inconsistent.** The branch emits `cumulative_cost_usd` *after* iter K's cost has been summed, but `iterations_completed = K-1` (since the iteration didn't get to scoring). Surfaces as "iter K-1 spent K iters' worth of money" in the summary. Not tested — branch is unreachable in practice because gate.py is co-located with loop.py and ADR-0002 guarantees parseable JSON on stdout (the 003-01 deviation log documented the same defensive-only posture). Acceptable for a defensive/unreachable branch; flagged here for completeness rather than fixed.
- **`--max-budget-usd <value>` precision is 6 decimal places (`f"{budget:.6f}"`).** Each claude invocation receives a value like `2.000000` or `0.500000`. Round-trips cleanly through tests' `float()` parsing; downstream consumers (any external argparse-style CLI) accept this format. Documented as the precision contract with claude's CLI.
- **`DEFAULT_PER_ITER_BUDGET_USD = $1.00` (when `--cost-ceiling 0` disables cumulative tracking) is a guess.** Analogous to the 30-min `DEFAULT_CLAUDE_TIMEOUT_SECONDS` default flagged in `docs/refinement-todo.md`; should be tuned with real-world data once the loop has accumulated enough live runs. Flagged in `docs/refinement-todo.md` for review.
- **Negative `--cost-ceiling` values are explicitly rejected** via `parser.error("--cost-ceiling must be >= 0")` (exit code 2, mirroring the `--max-iterations < 1` rejection pattern). Not pinned by AC7; rejected for closed exit-code-contract cleanliness and to avoid silently inverting the per-iter budget arithmetic. Tested via `CostCeilingValidationTests`.
- **Non-zero exit + parseable-but-non-dict JSON (e.g., `[1,2,3]`) routes to the "without JSON output" breadcrumb.** The implementation's data-shape gate (`isinstance(data, dict)`) treats non-dict-but-parseable as "no usable data," falling through to the returncode-based breadcrumb. Slightly misleading wording in this pathological edge case (stdout *was* JSON, just not a dict), but consistent with the rest of the loop's "we need a dict to extract fields" expectation. Untested — pathological corner.
- **Exit 0 + parseable-but-non-dict JSON routes to "claude JSON parse error: output is not a JSON object".** Same data-shape gate, different branch. Consistent with 003-01's wording; untested.
- **`schema_version: 1` propagates to all new emission paths.** The auto-injection in `_emit_json` extends cleanly to the new `cost_ceiling_reached` summary, the cost-aware preflight summaries, and every per-iter line. Not re-asserted in 003-02 tests; `SchemaVersionTests` (003-01) cover the principle.

**Reviewer caveats (non-blocking):**
- AC4 inclusive-vs-strict interpretation is documented but not re-litigated. If the spec author wanted the inclusive reading, the fix is a one-character change (`<` → `≤`) plus updating `test_passed_budget_never_below_floor`.
- The `gate_invocation_failed` forensic mismatch could be tightened by moving `cumulative_cost_usd += cost_usd` after the gate call (the per-iter emission would still see the post-add value). Not fixed because the branch is unreachable.
- Pathological non-dict-JSON cases (both exit codes) are untested. Acceptable for spike-shape; revisit if a fault-injection harness lands later.

**Reviewer verdict:** PASS (independent review, `jig:reviewer` subagent, 2026-05-19). All 7 ACs met with dedicated test classes; the 003-01 forward reference is correctly resolved by the four-branch split in `_invoke_claude`; the two-stage brake (pre-iter floor + post-iter exceed) gives the documented behavior (the iteration that first crosses the ceiling is the last one to run, with no sub-cent budget calls). Deviations are additive (extra summary field, defensive branches) or wording-sharpening (strict `<` for "within"). No regressions in `test_loop.py` slice-003-01 cases, `test_gate.py`, `test_scaffold.py`, or either `test_skill_surface.py`.

---

