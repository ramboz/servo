---
status: DONE
dependencies: []
last_verified:
---

## Slice 002-04 — timeout-safety

**Goal:** Bound the oracle's runtime. Default to 5 minutes (matches the architecture's "cost-ceiling=$2 per architecture.md" framing — long enough for real test suites, short enough that a wedged subprocess gets killed). `--timeout <seconds>` overrides. On timeout, send `SIGTERM`, wait briefly, then `SIGKILL`, and return rc=2 with a clear stderr breadcrumb. End-to-end value: unattended callers (003 agent-loop, 005 variant-race) can rely on the gate not hanging the whole loop / race.

**DoR:**
- ✅ Slice 002-03 DONE
- ✅ Decision: 300 seconds (5 min) is the default; tunable via flag and `SERVO_GATE_TIMEOUT` env var (env var wins so callers can set it for whole sessions)
- ✅ Decision: signal sequence is SIGTERM → 5s grace → SIGKILL (process-group-scoped so the oracle's awk/python children get killed too)

**Acceptance Criteria:**

1. **Default timeout.** With no flag, an oracle that sleeps for 11 minutes is killed at ~5 min and `gate.py` exits 2 with `status=env_error reason=timeout duration=300s`. The actual measured kill time is within ±2s of the configured timeout.
2. **Flag override.** `gate.py <target> --timeout 1` against a 5-second-sleeping oracle kills at ~1s and exits 2.
3. **Env-var override.** `SERVO_GATE_TIMEOUT=1 gate.py <target>` behaves identically to `--timeout 1`. If both are set, the flag wins (env var is the floor / default).
4. **Process-group kill.** The oracle and any descendants (e.g., a `pytest` subprocess) are all signaled. Verified by spawning an oracle that backgrounds a sleep and asserting the sleep doesn't outlive the gate.
5. **No regression on fast-path oracles.** An oracle that finishes in 100ms is not delayed by timeout machinery (no minimum wait); exit code and structured output are unchanged from 002-02 behavior.

**DoD:** _(same shape)_
- [x] All ACs pass; full test suite green. _75/75 in `test_gate.py` (up from 62 at 002-03); 40/40 `test_scaffold.py` regression check; total 115 tests green._
- [x] Test coverage per AC: AC1→`TimeoutTests.test_default_timeout_constant_is_300` + `test_resolve_timeout_default_is_300_via_function_call` + `test_timeout_flag_kills_long_running_oracle`. AC2→`test_timeout_flag_kills_long_running_oracle` + `test_timeout_summary_carries_timeout_field` + `test_timeout_json_carries_timeout_seconds`. AC3→`test_env_var_timeout_override` + `test_flag_wins_over_env_var` + `test_malformed_env_var_falls_back_to_default`. AC4→`ProcessGroupKillTests.test_backgrounded_subprocess_killed_with_oracle`. AC5→`FastPathRegressionTests.test_fast_oracle_no_delay` + `test_no_timeout_field_on_fast_path`. Plus `test_timeout_zero_disables_timeout` (clarify Q2) + `test_timeout_stderr_breadcrumb`.
- [x] Reviewer subagent review. _2026-05-18, PASS-WITH-CAVEATS verdict. Six caveats: three fixed in-flight (field rename, stronger default-timeout test, stderr breadcrumb assertion); three documented below._
- [x] Implementation review passed.
- [x] Reconciliation review passed.
- [x] `docs/refinement-todo.md` updated. _No new entries — all reviewer caveats either fixed in-flight or rolled into the deviation log. Pre-existing 002-01..03 entries unaffected._

### Close-out (post-DONE)

- [ ] `docs/architecture.md` mentions the timeout default + env var in the runtime section (so spec 003's loop driver knows the gate is timeout-aware). _Pending — will land at spec-002 close-out together with the Quality-gate JSON contract section deferred from slice 002-02._

**Anti-horizontal-phasing check:** After this slice, the gate is safe in unattended contexts. Spec 003 can build the loop driver on top without re-doing timeout logic; spec 005's race driver can race N variants without one wedged variant freezing the race.

### Deviation log (after reconciliation)

**Slice 002-04 — implemented 2026-05-18.** 75 tests green in `test_gate.py` (up from 62 at 002-03 close-out); 40/40 scaffold regression intact; total 115 tests. End-to-end dogfood: oracle that sleeps 10s + `--timeout 1 --json` → killed at ~1.3s wall-clock (1.0s timeout + ~0.3s subprocess overhead), payload `{schema_version:1, exit_code:2, status:"env_error", reason:"timeout", timeout_seconds:1.0}`, stderr breadcrumb `gate: oracle timed out after 1.0s (killed via SIGTERM → SIGKILL)`.

Deviations from spec text:

- **Field renamed `duration` → `timeout`** (reviewer-noted, fixed in-flight). Spec AC #1 uses the wording `duration=300s` in the example output; first implementation matched verbatim with JSON key `duration_seconds` / text token `duration=Xs`. Reviewer flagged the field name as misleading: "duration" reads naturally as "elapsed wall-clock the oracle ran for", but the value is actually "the timeout budget that fired" (the two can diverge by up to `_KILL_GRACE_SECONDS = 5` when an oracle ignores SIGTERM). Renamed for clarity: JSON key is now `timeout_seconds` (matches the `--timeout` flag and `SERVO_GATE_TIMEOUT` env var); text token is `timeout=Xs`. Spec wording in AC #1 is preserved as-is for historical fidelity; this deviation log captures the rename so downstream callers know which key to read.
- **Default-timeout AC tested via two complementary proxies.** AC #1 requires a 5-minute default with kill within ±2s of the configured timeout. The slice can't wall-clock-test the 5-min default itself (would push CI runtime past acceptable bounds). Two proxies: (1) `test_default_timeout_constant_is_300` greps the source for the literal `DEFAULT_TIMEOUT_SECONDS = 300` — refactor-fragile but human-readable; (2) `test_resolve_timeout_default_is_300_via_function_call` imports gate.py as a module and calls `_resolve_timeout(None)` with no env var set, asserting the returned value is 300.0 — refactor-resilient. Both kept because they fail differently (one on rename of the constant, the other on a logic regression in the resolver).
- **`--timeout 0` semantics** (clarify Q2). Per the Q2 answer, `--timeout 0` disables the timeout entirely (no upper bound on oracle runtime). Implementation: `_resolve_timeout` returns `None` when the flag value is `0`; `_run_oracle_bounded` passes `None` to `Popen.communicate(timeout=...)` which means "wait indefinitely". `test_timeout_zero_disables_timeout` exercises this.
- **Process-group kill via `start_new_session=True` + `os.killpg`** (reviewer-confirmed mechanically correct). The oracle becomes its own process-group leader; `os.killpg(proc.pid, signal.SIGTERM)` then signals the whole group, catching any backgrounded subprocesses the oracle's components spawned (e.g., a `pytest &` from a custom SEED block). Verified by `ProcessGroupKillTests`'s sentinel file pattern.
- **`SIGTERM → 5s grace → SIGKILL` sequence is hardcoded.** Per DoR. `_KILL_GRACE_SECONDS = 5` is a module-level constant; not user-configurable. Future slices may want to surface it as a flag (e.g., `--kill-grace 10` for slow shutdown sequences); deferred.
- **Malformed `SERVO_GATE_TIMEOUT` env var falls back to default with a stderr breadcrumb** (defensive). Spec didn't pin behavior for malformed env values; the implementation chose "ignore + breadcrumb + use default" rather than refusing or crashing. Caller-friendly. Tested by `test_malformed_env_var_falls_back_to_default`.

**Reviewer caveats not addressed in-flight** (logged here for traceability):

- `_run_oracle_bounded` returns `proc.returncode if proc.returncode is not None else -1` on timeout, but the value is unused (the timeout branch in `run_gate` emits `EXIT_ENV_ERROR` unconditionally). Reviewer flagged as cosmetic / dead code path. Left intact with a comment explaining why the field is populated despite being unused (downstream consumers might one day want to log the original returncode for forensic purposes).
- `time.sleep(6)` in `ProcessGroupKillTests` is intentional (must outlast the 5s backgrounded sleep). Adds ~6s to CI runtime. Documented for budgeting; non-actionable.
- Pre-existing 002-01..03 entries in `docs/refinement-todo.md` still apply.

**Reviewer verdict:** PASS-WITH-CAVEATS (independent review, `jig:reviewer` subagent, 2026-05-18). All 5 ACs met with observable subprocess-driven tests; closed 0/1/2 contract preserved (timeout → rc=2, no leak); stdlib-only intact (new `signal` import is stdlib). The PASS-WITH-CAVEATS qualifier reflects the in-flight fixes (field rename, stronger test, stderr assertion) the reviewer surfaced — all addressed before this verdict was finalized.

---

