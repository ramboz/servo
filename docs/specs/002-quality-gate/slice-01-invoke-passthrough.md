---
status: DONE
dependencies: []
last_verified:
---

## Slice 002-01 — invoke-passthrough

**Goal:** A `gate.py` helper that, invoked against a target directory containing `oracle.sh`, runs the oracle via `subprocess.run` and exits with the oracle's own return code (passthrough). End-to-end value: any caller (human, agent, or future skill) can run `python3 gate.py <target>` and trust that `$?` reflects the oracle's verdict using servo's contracted 0/1/2 codes.

**DoR:**
- ✅ Spec 001 DONE (scaffolded `oracle.sh` exists in the target with the documented exit-code contract)
- ✅ Decision: helper is a Python script, same shape as `scaffold.py` (no shell wrapper)
- ✅ Decision: gate is stateless (no on-disk artifacts from this slice)

**Acceptance Criteria:**

1. **Passthrough exit codes.** Against a target with a scaffolded `oracle.sh` that exits 0/1/2 under varied inputs, `gate.py <target>` exits with the same code. Verified for all three branches with deterministic component stubs.
2. **Refusal on missing oracle.** Against a target where `<target>/oracle.sh` does not exist, `gate.py <target>` exits **2** and prints a stderr message naming the absent path; nothing on disk changes.
3. **Refusal on bad target.** Against a nonexistent path, or a path that is not a directory, `gate.py <target>` exits **2** with a clear error.
4. **Stdout/stderr are pass-through.** The oracle's stdout (e.g., `oracle: composite=... threshold=...`) and stderr (e.g., `missing components: ...`) reach the caller's streams verbatim. This slice does **not** parse or rewrite oracle output.
5. **Helper is dependency-free.** `gate.py` runs on system Python 3.10+ with no `pip install` step (matches the `scaffold.py` rule).
6. **Unexpected oracle exits remap to rc=2.** Per [ADR-0002](../../decisions/adr-0002-gate-caller-contract.md), if the oracle exits with any code outside `{0, 1, 2}` (signal kill, bash errors 126/127, application bugs returning 99, etc.), `gate.py` exits **2** and writes a stderr line of the form `gate: oracle exited with unexpected code <N> (expected 0/1/2)`. The original oracle stdout/stderr still pass through. Refusal on non-executable `oracle.sh` follows the same shape with a stderr line naming `chmod +x` (clarify Q4).

**DoD:**
- [x] All ACs pass; full test suite green (no regressions in `test_scaffold.py` either). _20/20 in `test_gate.py`; 40/40 in `test_scaffold.py` regression check._
- [x] Helper test coverage: at least one fixture per AC under `skills/quality-gate/test_gate.py` (AC6 → `UnexpectedExitTests` + `NonExecutableOracleTests`). _AC1→`PassthroughTests`, AC2→`MissingOracleTests`, AC3→`BadTargetTests`, AC4→`PassthroughStreamsTests`, AC5→`DependencyFreeTests`, AC6→`UnexpectedExitTests` + `NonExecutableOracleTests`._
- [x] Reviewed by `reviewer` subagent (`jig:reviewer`). _2026-05-18, PASS verdict (clean, no PASS-WITH-CAVEATS qualifier). All 6 ACs met by observable subprocess-driven tests; deviation log honest; no hidden deviations; no regressions._
- [x] Implementation review passed.
- [x] Deviation log produced under this slice heading.
- [x] Reconciliation review passed. _Same reviewer pass evaluated the initial deviation log; two non-blocking polish caveats added to `docs/refinement-todo.md`._
- [x] `docs/refinement-todo.md` updated if any decisions were deferred during implementation. _Two new entries: signal-killed test assertion looseness; missing `is_file()` guard for non-regular `oracle.sh`. Both surfaced by reviewer; both non-blocking._

### Close-out (post-DONE)

- [x] `docs/specs/README.md` status board: spec 002 → `IN_PROGRESS (slice 002-01)`.
- [x] `README.md` skills table row for `quality-gate` flipped from DRAFT to IN PROGRESS.

**Anti-horizontal-phasing check:** After this slice, an unattended caller can already use `gate.py <target>` to score a project and trust the exit code. That is end-to-end value — the next four slices refine the surface but none is a prerequisite for "the gate works".

**Spike-shape note:** Servo's oracle contract was proven by spec 001's dogfood (composite=1.0 threshold=0.5 → exit 0). 002-01 is *not* spike-shaped for the contract itself. It is mildly spike-shaped for the **subprocess + signal-propagation assumption** the rest of the spec rests on — if `subprocess.run` doesn't preserve exit codes faithfully (e.g., signal-killed oracles, weird `set -e` interactions), slices 002-02 through 002-04 need replanning around an alternative invocation shape.

### Deviation log (after reconciliation)

**Slice 002-01 — implemented 2026-05-18.** 20 tests green via `python3 skills/quality-gate/test_gate.py`; scaffold regression suite still 40/40. End-to-end dogfood: scaffold a tmp project → `gate.py <tmp>` propagates exit 2 (env error, pytest missing); custom pass-path oracle (exit 0) → `gate.py` exit 0 with oracle stdout passed through.

Deviations from spec text:

- **`target.resolve()` applied before validation.** The spec doesn't require absolute paths; resolving was an enhancement so refusal messages name the absolute path of the missing oracle. Test `MissingOracleTests.test_stderr_names_missing_oracle` exercises this. Tradeoff: a relative-path symlink dance becomes resolved (which can be confusing if the user expected the raw input echoed back); accepted as a usability improvement.
- **Consistent `gate: <message>` stderr prefix.** All refusal lines and the unexpected-exit line start with `gate:` to disambiguate gate output from oracle output (which uses `oracle:`). Not in the spec but matches the prefix convention oracle.sh already established. Downstream slices (002-02 onward) can keep the prefix for structured-summary lines too.
- **`os.access(..., os.X_OK)` for executability check.** Pre-check before subprocess.run so the chmod-hint refusal is deterministic. Alternative considered: invoke unconditionally and catch `PermissionError`/`OSError`; rejected because subprocess error messages are platform-dependent and the chmod hint becomes harder to deliver.
- **No special handling for negative `returncode`.** On signal-killed bash, the gate sees the standard `128 + signo` positive code (143 for SIGTERM in `test_signal_killed_remapped_to_two`). If a future Python or platform reports a negative returncode for a signal-killed child, the existing `if rc not in ALLOWED_ORACLE_EXIT_CODES` branch still triggers — the message just reports the negative code, which is acceptable.
- **Refusal messages name the `/servo:scaffold-init` recovery skill explicitly.** Test `MissingOracleTests.test_stderr_directs_user_to_scaffold` asserts this. Beyond spec text but a small UX win — the gate is the most-invoked entrypoint after install, and the missing-oracle case is the most common "first-time runner" failure mode.
- **Constants surfaced (`EXIT_PASS`, `EXIT_BELOW_THRESHOLD`, `EXIT_ENV_ERROR`, `ALLOWED_ORACLE_EXIT_CODES`).** Named constants instead of magic numbers — clarifies the ADR-0002 contract at the call site, costs nothing.

**Spike-shape check:** Subprocess + signal-propagation assumption holds. `subprocess.run` preserves bash's `128 + signo` convention on signal kills (verified by the `signal_killed` test); the closed 0/1/2 remap branch handles every non-contract code uniformly without per-platform special-casing. `set -e` inside the oracle does not break exit-code propagation when invoked via shebang-direct (no shell wrapper added). **Proceeding to 002-02 with no re-plan.**

**Reviewer caveats (non-blocking, recorded in `docs/refinement-todo.md`):**
- `test_signal_killed_remapped_to_two` uses a substring match on stderr rather than two parallel assertions (positive `128 + signo` / negative returncode). Defensible — the contract is "rc=2 + some unexpected-code message" — but a future cross-platform CI run may want stricter pinning.
- `gate.py` does not guard against `oracle.sh` being a non-regular file (directory, FIFO, dangling symlink). End-state is still rc=2 via the generic OSError handler, but the message is less actionable than the dedicated chmod-hint refusal.
- Reviewer also flagged a filename case mismatch (lowercase spec links vs. uppercase ADR file). Verified post-review: the file is `adr-0002-gate-caller-contract.md` (lowercase) and all references match — the caveat reflects stale state at the moment of the reviewer's read, not the committed shape.

**Reviewer verdict:** PASS (independent review, `jig:reviewer` subagent, 2026-05-18). All 6 ACs met with observable subprocess-driven tests; deviation log honest; no hidden deviations; no regressions in `test_scaffold.py`.

---

