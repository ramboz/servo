---
status: DONE
dependencies: []
last_verified:
---

## Slice 003-03 — context-fill-gate

**STATUS: DONE**

**Goal:** Compute the context-fill ratio from each iteration's JSON output (`(usage.input_tokens + usage.cache_read_input_tokens + usage.cache_creation_input_tokens) / modelUsage.<model>.contextWindow`) and refuse iteration N+1 when the ratio exceeds `--context-fill-threshold` (default 75%). This is the **hard refusal gate** cousin of jig's `jig-context-check.sh` soft warning. End-to-end value: an unattended loop won't run iteration N+1 with a context window already 95% full — it halts cleanly with a parseable terminal reason instead of producing garbage output.

**DoR:**
- ✅ Slice 003-02 DONE
- ✅ Spike: context-fill ratio is exposed via `usage` + `modelUsage.<model>.contextWindow` in the per-iteration JSON (no subprocess gymnastics needed)
- ✅ Decision: threshold default 0.75 (75%). Picked as the midpoint of the spike's 60–75% range. **Flagged in `docs/refinement-todo.md` for tuning** once real-world iteration data accumulates.
- ✅ Decision: ratio is computed from the **prior iteration's** JSON output; applied as a precondition to issuing the next `claude -p`. (Iteration 1 has no prior — always proceeds.)

**Acceptance Criteria:**

1. **Threshold gate (default).** With a synthetic mock `claude` returning `usage.input_tokens=160000` against `modelUsage.<model>.contextWindow=200000` (ratio = 0.80), the loop refuses to invoke iteration N+1 and exits 0 with `terminal_reason=context_full`, `context_fill_ratio=0.80`, `context_fill_threshold=0.75`.
2. **Threshold gate (override).** `loop.py <target> --prompt "<text>" --context-fill-threshold 0.50` refuses at ≥ 50%.
3. **No premature refusal.** Iterations with ratio below threshold continue normally; the ratio is logged per-iteration in stdout JSON under `context_fill_ratio`.
4. **Threshold equals threshold (≥, not >).** Exact-equal ratio `0.75` triggers refusal. Documented because off-by-one in the comparison direction is a classic bug.
5. **Iteration 1 unconditional.** With no prior iteration to read context from, iteration 1 always proceeds regardless of threshold setting.
6. **Refusal happens before `claude -p` invocation.** The loop driver inspects the prior iteration's JSON, decides "refuse," and never invokes `claude -p` for iteration N+1. Verified by counting mock-claude invocations.
7. **`--context-fill-threshold 0` disables the gate.** Useful for tests or callers enforcing the limit out-of-band. (Same shape as `--cost-ceiling 0`.)
8. **Missing `contextWindow` field tolerated.** If a future Claude Code release omits `modelUsage.<model>.contextWindow`, the gate refuses to enforce (logs a one-line breadcrumb to stderr, continues without the gate). This is fail-open for *this specific gate*; the iteration cap and cost ceiling still apply.

**DoD:**
- [x] All ACs pass; full test suite green (no regressions in `test_loop.py` slice-003-01/02 cases, `test_gate.py`, `test_scaffold.py`).
- [x] Test coverage per AC under `skills/agent-loop/test_loop.py`: AC1→`ContextFillThresholdDefaultTests`, AC2→`ContextFillThresholdOverrideTests`, AC3→`ContextFillBelowThresholdTests`, AC4→`ContextFillEqualThresholdTests`, AC5→`ContextFillIterationOneTests`, AC6→`ContextFillRefusalBeforeClaudeTests`, AC7→`ContextFillDisabledTests`, AC8→`ContextFillMissingContextWindowTests`.
- [x] Reviewed by `jig:reviewer` subagent.
- [x] Implementation review passed.
- [x] Deviation log produced under this slice heading.
- [x] Reconciliation review passed.
- [x] `docs/refinement-todo.md` updated (default threshold 0.75 flagged for tuning).

### Close-out (post-DONE)

- [x] Default threshold (0.75) flagged in `docs/refinement-todo.md` as a tuning target.
- [x] `docs/architecture.md` "Why this spec" framing updated to note that 003-03's refusal gate is the hard cousin of jig's `jig-context-check.sh` warning.

**Anti-horizontal-phasing check:** After this slice, the loop refuses to continue with a near-full context window — the single most common cause of degraded agent output. The slice is independently useful; it doesn't depend on checkpoint/resume or runner/judge to deliver its value.

### Deviation log (after reconciliation)

**Slice 003-03 — implemented 2026-05-19.** 31 new tests under `skills/agent-loop/test_loop.py` (83/83 total green: 8 AC test classes + `ContextFillValidationTests` + `ExtractContextFillRatioUnitTests`); full regression suite still green (75/75 `test_gate.py`, 40/40 `test_scaffold.py`, 18/18 `test_skill_surface.py` gate, 13/13 `test_skill_surface.py` scaffold). The context-fill refusal gate is now wired: each iteration's `(usage.input_tokens + cache_read + cache_creation) / modelUsage.<model>.contextWindow` ratio is computed externally; iteration N+1 refuses (rc=0, `terminal_reason=context_full`) when the prior ratio is ≥ threshold.

Deviations from spec text:

- **`_extract_context_fill_ratio` fail-opens on more shapes than AC8 enumerates.** AC8 names only "omits `modelUsage.<model>.contextWindow`"; the helper also fail-opens on (a) missing `usage` block, (b) non-dict `usage` block, (c) non-numeric token values, (d) missing `modelUsage` block, (e) empty `modelUsage` dict, (f) non-dict model entries (skipped, then if no good entry remains → fail-open), (g) `bool`-as-int `contextWindow` (explicit `isinstance(cw, bool)` exclusion at `loop.py:_extract_context_fill_ratio`), (h) zero or negative `contextWindow`. Each path emits a distinct stderr breadcrumb naming the specific cause. Pinned by `ExtractContextFillRatioUnitTests` (12 cases). Fits AC8's "fail-open for this specific gate" semantics — additive on top of the literal "omits contextWindow" case.
- **Pre-iteration gate order: context-fill check fires *before* cost-ceiling floor check.** When both brakes would fire on the same iteration boundary, the summary's `terminal_reason` is `context_full`, not `cost_ceiling_reached`. Not pinned by spec; documented here so a future structured-output consumer knows the precedence rule. Rationale: a high context-fill ratio means the *next* iteration would degrade regardless of budget; reporting `context_full` is the more informative cause.
- **`ContextFillValidationTests` adds CLI bounds rejection for `[0.0, 1.0]`.** Not pinned by spec ACs; mirrors the `--max-iterations < 1` (003-01) and `--cost-ceiling < 0` (003-02) rejection patterns. Negative thresholds always-fire (would gate iter-2 unconditionally); thresholds > 1.0 never-fire (ratio is bounded in `[0, 1]`). Both are user-error shapes; rejected upstream with `parser.error` + rc=2 + breadcrumb `--context-fill-threshold must be in [0.0, 1.0]`. Closed exit-code-contract cleanliness; `0` remains the documented disable value.
- **`context_fill_ratio` per-iter line is added beyond AC3's "logged per-iteration" wording.** AC3 says "logged per-iteration in stdout JSON under `context_fill_ratio`" — the implementation puts it on every per-iter line (success or failure to compute → null). Summary lines also carry `context_fill_ratio` (last observed, or null) for forensic continuity. Spec's "at minimum" language for the per-iter JSON (003-01 AC5) absorbs this additive emission.
- **`context_fill_threshold` is emitted on every summary line, not just on `context_full` halts.** AC1 specifies the field on the gate-halt summary; the implementation adds it to all summary paths (preflight refusal, `claude_invocation_failed`, `gate_invocation_failed`, `oracle_passed`, `max_iterations_reached`, `cost_ceiling_reached`, `context_full`). Mirrors how 003-02 generalized `cost_ceiling_usd` beyond its AC; downstream consumers see the configured bound regardless of how the run ended.
- **Multi-model `modelUsage` resolution: first dict entry with a positive non-bool numeric `contextWindow` wins.** Deterministic given Python 3.7+ dict insertion order — adequate for the single-model case the spike captured, documented in the helper's docstring as the explicit semantics for the (unlikely) multi-model hypothetical. Pinned by `ExtractContextFillRatioUnitTests.test_non_dict_model_entry_skipped`.
- **`input_tokens=null` (and `cache_*=null`) is mapped to zero, not fail-open.** The `.get(key, 0) or 0` idiom collapses both missing and explicit-null to zero; a future Claude Code release that emits `"input_tokens": null` is treated as "zero input tokens" rather than fail-open. Pinned by `ExtractContextFillRatioUnitTests.test_none_tokens_treated_as_zero`. Rationale: a null token count almost certainly means "no input was sent" rather than "the schema broke" — fail-open would be too aggressive here.
- **AC5 (iter 1 unconditional) is exercised by *two* complementary tests.** `test_iteration_one_runs_with_very_low_threshold` (max-iter=1 + threshold=0.05 → iter 1 runs, ends on `max_iterations_reached`) and `test_iter_one_runs_then_iter_two_gated` (max-iter=5 + threshold=0.05 → iter 1 runs, pre-iter-2 gate fires, ends on `context_full`). Either alone is necessary but not sufficient; the pair pins both "iter 1 unconditional" and "iter 2 is gated by iter 1's ratio."
- **`schema_version: 1` propagates to all new emission paths.** The auto-injection in `_emit_json` extends cleanly to the `context_full` summary, the context-aware preflight summaries, and the per-iter line's `context_fill_ratio` field. Not re-asserted in 003-03 tests; `SchemaVersionTests` (003-01) cover the principle.
- **Default cost (`$0.05` per iteration) in the context-fill mock is chosen to keep the cost ceiling out of the way.** The context-fill tests have an implicit cost-budget of $0.05 × 5 iterations = $0.25, well under the default $2.00 ceiling, so cost-ceiling halts can't mask context-fill behavior. Documented in the `_mock_claude_input_tokens_per_iter` helper.
- **`context_fill_threshold: 0` is emitted as the Python float `0.0`, displayed in JSON as `0` (no fractional part by `json.dumps` for clean integers).** A downstream consumer expecting `0.0` (with decimal) will need to round-trip via `float()`. The test `ContextFillDisabledTests.test_disabled_gate_runs_all_iterations` uses `assertEqual(..., 0)` which passes for both. Documented as the JSON-emission shape; not a contract violation.

**Reviewer caveats (non-blocking):**
- The pathological "both `usage` and `modelUsage` missing" case routes to the *first* failure path (missing `usage`). A consumer reading the breadcrumb would only see the `usage`-missing message and not learn that `modelUsage` was also absent. Acceptable for spike-shape — a forensic reader can re-inspect the iteration's full JSON if more detail is needed.
- Pre-iter gate ordering (context-fill before cost-floor) is documented in this log but not pinned by tests. A future refactor that reorders the brakes could change the precedence rule silently. Cheap to pin if it ever matters; today the two brakes are independent in practice (cost-floor fires near $2 cumulative; context-fill fires when ratio ≥ 0.75 — uncorrelated events).
- `_extract_context_fill_ratio`'s "first model with contextWindow wins" semantics for multi-model `modelUsage` is documented but uncovered by an end-to-end test (the unit test exercises non-dict-entry-skipping but not "two valid models, pick first"). Pathological corner; not gated.

**Reviewer verdict:** PASS (independent review, `jig:reviewer` subagent, 2026-05-19). All 8 ACs met with meaningful tests that exercise the spec's pinned behaviors (0.75 default, `>=` direction, iter-1 unconditional, refusal-before-claude via counter file, fail-open with stderr breadcrumb + null ratios). The reviewer's actionable caveats — (a) add unit tests for the helper's six internal failure paths, (b) document the bool-exclusion and pre-iter gate ordering — were addressed in-slice: `ExtractContextFillRatioUnitTests` (12 cases) lands, the bool/zero/negative `contextWindow` exclusions are pinned, and the deviation log captures the gate ordering. 83/83 green post-fix; no regressions in `test_gate.py` / `test_scaffold.py` / either `test_skill_surface.py`.

---

