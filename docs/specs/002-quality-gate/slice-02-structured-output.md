---
status: DONE
dependencies: []
last_verified:
---

## Slice 002-02 — structured-output

**Goal:** Parse the oracle's `composite=X threshold=Y` stdout line and emit a normalized summary on the gate's own stdout. Add a `--json` flag that switches output to a structured payload (`{exit_code, composite, threshold, status, missing}`). End-to-end value: callers (and humans) get a stable, parseable score record without grepping the oracle's free-form output.

**DoR:**
- ✅ Slice 002-01 DONE
- ✅ Oracle stdout format frozen by spec 001-02 (`oracle: composite=%s threshold=%s\n`)
- ✅ Decision: gate emits a single line on stdout by default; `--json` switches to one-line JSON

**Acceptance Criteria:**

1. **Default summary line.** `gate.py <target>` (exit 0 path) prints a single normalized line on stdout: `gate: composite=<X> threshold=<Y> status=pass exit=0`. The exit-1 path prints `status=below_threshold exit=1`. The exit-2 path prints `status=env_error exit=2` and (when applicable) a `missing=name1,name2` field.
2. **JSON mode emits one-line JSON.** `gate.py <target> --json` writes a single JSON object to stdout: keys are `exit_code` (int), `composite` (float or null), `threshold` (float or null), `status` (string: `pass`/`below_threshold`/`env_error`), `missing` (list of component names — empty list when none). On the exit-2 path where the oracle never produced a score line, `composite` and `threshold` are `null`.
3. **Oracle stdout still surfaces in `--verbose`.** A `--verbose` flag re-prints the oracle's raw stdout/stderr beneath the gate's summary (or alongside, in JSON mode under a `raw` key). Without `--verbose`, the oracle's free-form output is suppressed.
4. **Unparseable oracle output → env error.** If the oracle exits 0 but the `composite=...` line is missing or malformed, `gate.py` exits **2** with `status=env_error reason=unparseable_oracle_output` and surfaces the raw output on stderr. The contract is: a passing oracle MUST emit a parseable summary.
5. **No regression on AC 002-01-1.** Exit-code passthrough still holds when no flags are supplied.

**DoD:** _(same shape as 002-01)_
- [x] All ACs pass; full test suite green. _39/39 in `test_gate.py` (up from 20 in 002-01); 40/40 `test_scaffold.py` regression check; total 79 tests green._
- [x] Test coverage per AC: AC1→`SummaryLineTests` (6 tests), AC2→`JsonOutputTests` (6 tests), AC3→`VerboseTests` (4 tests), AC4→`UnparseableOracleTests` (3 tests), AC5→regression coverage in `PassthroughTests` (3 tests).
- [x] Reviewer subagent review (`jig:reviewer`). _2026-05-18, PASS verdict. Five non-blocking caveats: two fixed in-flight (test rename to match ADR-0002, loop extension to cover unparseable branch); three documented below._
- [x] Implementation review passed.
- [x] Reconciliation review passed.
- [x] `docs/refinement-todo.md` updated. _Pre-existing 002-01 caveats remain (signal-killed test substring match, missing `is_file()` guard). No new entries — caveats #2 and #4 are reconciled in the deviation log; caveats #1 and #3 fixed in code._

### Close-out (post-DONE)

- [ ] If `--json` schema needs evolution post-slice (added fields), document in `docs/architecture.md` under a new "Quality-gate JSON contract" section. _Deferred to 002-03 close-out (manifest-aware adds the `audit` JSON contract; both will land in architecture.md together)._

**Anti-horizontal-phasing check:** After this slice, agent-loop's future per-iteration logging has a stable schema to consume — without writing a single line of agent-loop code. The gate is itself useful (no consumer required) for any human running it from the shell.

### Deviation log (after reconciliation)

**Slice 002-02 — implemented 2026-05-18.** 39 tests green via `python3 skills/quality-gate/test_gate.py` (up from 20 at 002-01 close-out); scaffold regression suite still 40/40. End-to-end dogfood across four modes: default text pass, `--json` pass, `--json --verbose` pass (with `raw` key), `--json` refusal on missing target — all four shapes match the ADR-0002 contract.

Deviations from spec text:

- **Refusal modes also emit a structured stdout summary** (reviewer-noted). The spec AC #1 scopes the summary to "the exit-0/1/2 path" with the implication of oracle-invocation outcomes; the implementation extended the same structured summary to every gate exit including early refusals (`target_missing`, `target_not_directory`, `oracle_missing`, `oracle_not_executable`, `invocation_failed`). Rationale: downstream callers (003 agent-loop, 004 oracle-hook, 005 variant-race) shouldn't need to branch on "did the gate get as far as invoking the oracle?" — every gate call should produce one parseable stdout line / JSON payload. The stderr human-readable message is preserved in addition. Documented now so 003+ can rely on this uniformity. Tests `MissingOracleTests.test_summary_line_on_stdout`, `BadTargetTests.test_*_refused`, `NonExecutableOracleTests.test_summary_carries_not_executable_reason`, and `JsonOutputTests.test_refusal_json_has_schema_version_and_status` exercise the extension.
- **Slice 002-01 AC #4 ("Stdout/stderr are pass-through") is intentionally superseded** (reviewer-noted) by slice 002-02 AC #3 (`--verbose`). The previous default behavior of inherit-streams is replaced by capture-then-emit-summary. Without `--verbose`, the oracle's free-form output is suppressed; with `--verbose`, the raw streams are re-emitted beneath the gate's summary (text mode) or under the `raw` JSON key (JSON mode). The 002-01 `PassthroughStreamsTests` class was retired; the new `VerboseTests` class covers the re-emission contract. This is a scope expansion, not a regression: the contract evolved from "raw passthrough" to "structured summary + optional raw passthrough".
- **Test name aligned with ADR-0002.** Reviewer caveat: ADR-0002's Verification section cites `JsonOutputTests.test_schema_version_present_and_equals_one`. The first draft of `test_gate.py` had this named `test_schema_version_field_pinned`. Renamed to match the ADR (the ADR is the contract source). The loop also gained a fifth oracle input (the unparseable-output branch), so every documented JSON-emitting path now has `schema_version=1` verified.
- **Default text format normalizes floats.** Oracle emits `composite=0.9000` (4 decimal places); gate emits `composite=0.9` (`{value:g}` formatting drops trailing zeros). Consumers should treat values as floats, not strings. JSON mode emits the raw float (no string formatting). Documented in `_format_float` docstring.
- **Refusal `reason` taxonomy is a closed set.** The implementation uses these reason strings: `target_missing`, `target_not_directory`, `oracle_missing`, `oracle_not_executable`, `invocation_failed`, `unexpected_exit`, `unparseable_oracle_output`. Plus the absence of `reason` on the natural pass / below-threshold / oracle-env-error paths. This is the closed set callers can branch on; documented here as a soft contract until either ADR-0002 evolves to enumerate it or a future caller proves the list incomplete.
- **`--verbose` re-emits oracle output on the same streams as the original** (no `>&1` redirect). Oracle stdout → gate stdout, oracle stderr → gate stderr. Matches user expectations from `2>&1` shell semantics.

**Reviewer caveats not addressed in-flight** (logged here for traceability):
- Pre-existing 002-01 entries in `docs/refinement-todo.md` still apply — signal-killed test loose substring match; missing `is_file()` guard for non-regular `oracle.sh`. Neither was reintroduced or worsened by this slice.

**Reviewer verdict:** PASS (independent review, `jig:reviewer` subagent, 2026-05-18). All 5 ACs met with observable subprocess-driven tests; deviation log captures both scope-expansion choices the reviewer flagged. No regressions in `test_scaffold.py` (40/40). Helper still stdlib-only.

---

