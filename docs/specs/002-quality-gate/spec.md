---
status: DONE
dependencies: [001]
last_verified: 2026-05-18
---

> **DONE 2026-05-18.** All five slices (002-01 through 002-05) implemented, reviewed (each by `jig:reviewer` subagent), and reconciled. Spec-level DoD passed including the three-scenario dogfood (pass-path JSON with `schema_version=1`, `--timeout 1` against a 5s sleep returning rc=2 with `reason=timeout`, manifest-missing refusal). 146 tests green across four files.

# Spec 002 — quality-gate

> Runtime invocation of the scaffolded `oracle.sh`. Locates the target's oracle, runs it under a bounded timeout, normalizes exit codes (0 = ≥threshold / 1 = <threshold / 2 = env error), and emits structured score data callers can act on. The truth-source every other servo runtime skill (003 agent-loop, 004 oracle-hook, 005 variant-race) depends on.

## Why this spec

Spec 001 dropped `oracle.sh` and `.servo/install.json` into the target. Without spec 002, every downstream skill would have to re-invent oracle invocation: locate the file, exec it, parse stdout, handle missing-tool failures, bound the runtime, and decide whether the exit code means "below threshold" or "environment broken". Doing that once — here — eliminates four near-duplicate copies of the same brittle subprocess-and-regex logic across specs 003 / 004 / 005.

It is also the **truth-source** framing servo's design philosophy hinges on: a single uniform call shape (`gate.py <target>`), a single output schema, a single set of exit codes. Once 002 lands, the rest of servo's runtime skills can treat the oracle as a black-box function `(target) -> {exit, score, threshold, missing}` and never touch `oracle.sh` directly.

## Out of scope (deferred to later specs)

- Per-iteration run logging at `<target>/.servo/runs/<run-id>/` (→ 003 agent-loop). The gate is intentionally stateless: callers own persistence.
- Hook-driven `Stop`-event scoring (→ 004 oracle-hook). The gate is a one-shot subprocess; hook integration is its own surface.
- Per-variant scoring across worktrees (→ 005 variant-race). The race driver loops the gate; the gate doesn't know about variants.
- Re-running the gate after edits (a loop concern, not a gate concern).
- Watching files / scheduling / cron-style invocation. Out of scope forever — servo composes with Unix tools that already do this.

## SPIDR decomposition

Mirrors the spec 001 cadence (spike-shaped first slice → core content → contract refinement → safety → wizard) because the problem shape is the same: ship a tool the LLM and the runtime skills both invoke, in vertical slices that each deliver end-to-end value.

### Slice index

| Slice | Title | Goal |
|---|---|---|
| 002-01 | invoke-passthrough | `gate.py <target>` locates `<target>/oracle.sh`, runs it via subprocess, passes through the 0/1/2 exit code. Refuses with rc=2 on missing oracle. |
| 002-02 | structured-output | Parse the oracle's `composite=X threshold=Y` summary; emit normalized text + `--json` mode with `{exit_code, composite, threshold, status, missing}`. |
| 002-03 | manifest-aware | Read `<target>/.servo/install.json` to confirm this is a servo-scaffolded install; refuse on missing manifest. `gate.py audit <target>` prints manifest + components. |
| 002-04 | timeout-safety | Bound oracle runtime (default 5 min, `--timeout` override); kill-on-timeout returns rc=2 with a stderr breadcrumb. Required for unattended callers. |
| 002-05 | qa-wizard | `SKILL.md` exposes the helper to the LLM with trigger phrases ("score this code", "run the oracle"), anti-greediness tests, and refusal-handling guidance. |

Five slices, sized to match spec 001's cadence.

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

## Slice 002-03 — manifest-aware

**Goal:** Refuse to run against a target that lacks `.servo/install.json` (the manifest spec 001 writes). Add a `gate.py audit <target>` subcommand that prints the manifest's `installed_tier`, `signals`, and `components` so callers can introspect the install without running the oracle. End-to-end value: 002-03 closes the contract that "if the gate runs, this is a servo install, not a hand-rolled `oracle.sh`."

**DoR:**
- ✅ Slice 002-02 DONE
- ✅ Manifest schema frozen by spec 001-03 (keys: `servo_version`, `timestamp`, `installed_tier`, `signals`, `components`)
- ✅ Decision: gate refuses on missing manifest; runs on present-but-stale manifest (staleness is a future concern, not a gate concern)

**Acceptance Criteria:**

1. **Refusal on missing manifest.** If `<target>/.servo/install.json` does not exist, `gate.py <target>` exits **2** with a stderr message naming the absent manifest. The user is told to run `/servo:scaffold-init` first.
2. **Refusal on malformed manifest.** If the manifest exists but is not valid JSON, or is missing required keys (`installed_tier`, `components`), `gate.py` exits 2 with a stderr message naming the offending key.
3. **Audit subcommand prints manifest.** `gate.py audit <target>` exits 0 and prints a human-readable summary of the manifest: `tier`, `installed at`, `signals` (one per line), `components` (one per line, with weight). No oracle invocation.
4. **Audit `--json` mode.** `gate.py audit <target> --json` emits the manifest contents verbatim as JSON on stdout.
5. **Audit refusal modes mirror invocation refusal.** Audit also refuses on missing manifest / bad target with rc=2 and the same stderr shape.

**DoD:** _(same shape)_
- [x] All ACs pass; full test suite green. _62/62 in `test_gate.py` (up from 39 at 002-02); 40/40 `test_scaffold.py` regression check; total 102 tests green._
- [x] Test coverage per AC: AC1→`MissingManifestTests` (5 tests), AC2→`MalformedManifestTests` (4 tests: bad JSON, non-object, missing `installed_tier`, missing `components`), AC3→`AuditTextOutputTests` (7 tests, including no-oracle-invocation sentinel verification), AC4→`AuditJsonOutputTests` (2 tests: verbatim manifest, no weight enrichment), AC5→`AuditRefusalTests` (5 tests, covers all four refusal reasons + schema_version).
- [x] Reviewer subagent review. _2026-05-18, PASS verdict. Six caveats: two fixed in-flight (one-line audit JSON, lowercase booleans); one logged to `refinement-todo.md` (manifest weights coupling); three documented below._
- [x] Implementation review passed.
- [x] Reconciliation review passed.
- [x] `docs/refinement-todo.md` updated. _New entry: "`gate.py audit` parses component weights from `oracle.sh` (soft template coupling)" — the manifest carries names only; weights live in oracle.sh until a future spec/ADR extends the manifest schema._

### Close-out (post-DONE)

- [ ] If the manifest schema needs a new key for gate's benefit (e.g., `oracle_path` override), record an ADR-candidate in `docs/architecture.md` rather than silently extending it. _Logged in refinement-todo (weights-in-manifest); revisit when spec 003 or a future template-shape change forces the question._

**Anti-horizontal-phasing check:** After this slice, the gate is the front door to *any* servo install introspection. A user with no oracle invocation in mind can still run `gate.py audit <target>` and see what's there. That makes 002 useful even when the project is paused mid-loop.

### Deviation log (after reconciliation)

**Slice 002-03 — implemented 2026-05-18.** 62 tests green in `test_gate.py` (up from 39 at 002-02 close-out); 40/40 scaffold regression intact. End-to-end dogfood: scaffold a tmp project with pytest → `gate.py audit <tmp>` prints `tier-0`, `installed: <ts>`, `signals: tests=true language=python`, `components: pytest (weight 1)`. `gate.py audit <tmp> --json` emits the manifest verbatim. `rm <tmp>/.servo/install.json` then `gate.py <tmp> --json` → `{schema_version: 1, exit_code: 2, status: env_error, reason: manifest_missing}`.

Deviations from spec text:

- **Component weights are parsed from `oracle.sh`'s `COMPONENTS=( "name:weight" )` array** (reviewer-noted, refinement-todo logged). The manifest stops at component names; AC #3 requires "components (one per line, with weight)". `_parse_component_weights` reads oracle.sh as a best-effort enrichment for text mode. Returns `{}` silently on any parse failure — audit then prints the component name with no weight, which is still useful. The clean long-term fix is to extend the manifest schema, but that touches the frozen 001-03 contract and warrants its own ADR. Tracked in `docs/refinement-todo.md` as "audit parses weights from oracle.sh (soft template coupling)".
- **Audit `--json` mode is one-line (not pretty-printed)** (reviewer-noted, fixed in-flight). First implementation used `json.dumps(manifest, indent=2)` — multi-line. Reviewer flagged the shape divergence from invocation `--json` (one-line per 002-02 AC #2) and from audit refusal-mode JSON (one-line via `_emit_summary`). Changed to `json.dumps(manifest)` (one-line) so the contract is uniform: every `--json` payload from the gate is one parseable line.
- **Signal booleans render lowercase in text mode** (reviewer-noted, fixed in-flight). First implementation interpolated booleans via f-string, yielding Python repr `True`/`False`. Reviewer noted the divergence from JSON's `true`/`false`. Fixed: text mode now emits `tests=true lint=false` etc. The dedicated f-string formatter (`'true' if v is True else 'false' if v is False else v`) only normalizes booleans; other types stringify unchanged.
- **Hand-rolled subcommand dispatch** (reviewer-confirmed clean). `main()` checks `argv[0] == "audit"` and dispatches to a separate argparse parser; otherwise the default gate parser handles bare `gate.py <target>`. Mirrors `scaffold.py`'s `detect` shape. The bare-positional form remains valid because argparse subparsers aren't introduced.
- **Manifest precondition fires between target validation and oracle existence check** (reviewer-confirmed). Order: target exists → is_dir → manifest exists → manifest parseable → oracle exists → oracle executable → invoke. A target with no manifest is rejected before the oracle is even consulted, which matches the AC #1 "this is a servo install, not a hand-rolled oracle.sh" framing.
- **Test setUps pre-seed a manifest** (reviewer-confirmed clean). The 002-01/02 test classes that exercise oracle invocation (`PassthroughTests`, `MissingOracleTests`, `UnexpectedExitTests`, `NonExecutableOracleTests`, `SummaryLineTests`, `JsonOutputTests`, `VerboseTests`, `UnparseableOracleTests`) all added `_make_manifest(self.target)` in setUp. This isolates each test class to its target failure mode (`MissingOracleTests` now tests oracle-missing with a valid manifest, not missing-everything).
- **Three new refusal reasons** (`manifest_missing`, `manifest_malformed`, `manifest_invalid_key`) round out the closed `reason` taxonomy first sketched in slice 002-02's deviation log. Both text and JSON modes carry these consistently.

**Reviewer caveats not addressed in-flight** (logged here for traceability):
- `test_stderr_directs_user_to_scaffold` (and equivalents) assert `scaffold-init` (no slash) rather than the full `/servo:scaffold-init`. Same loose-substring pattern flagged by 002-01 reviewer (already in `refinement-todo.md`). Not regressed by this slice; not blocking.
- `AuditTextOutputTests.test_components_show_weight_when_oracle_present` asserts `"1.5"` substring. Python's `{:g}` formatter would render `1.0` as `1` (no decimal). If a test ever lands a weight of exactly `1.0`, the substring assertion may pick up incidental matches. Defensible — production weights are tunable floats — but worth tightening if it bites.
- Pre-existing 002-01 / 002-02 entries in `docs/refinement-todo.md` still apply.

**Reviewer verdict:** PASS (independent review, `jig:reviewer` subagent, 2026-05-18). All 5 ACs met with observable subprocess-driven tests; manifest schema producer/consumer agree; no regressions in `test_scaffold.py`; deviation log captures both the soft coupling and the two in-flight fixes.

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

## Slice 002-05 — qa-wizard

**Goal:** `skills/quality-gate/SKILL.md` exposes the helper to the LLM. Mirrors the `scaffold-init` SKILL.md shape: trigger phrases the skill fires on, explicit negative triggers, refusal-handling guidance, examples. No Q&A flow needed — the gate has few user-facing knobs — but a short "options" section covers `--json`, `--timeout`, and the `audit` subcommand. End-to-end value: typing "score this project" or "run the oracle" surfaces the gate naturally.

**DoR:**
- ✅ Slice 002-04 DONE
- ✅ Anti-greediness tests pattern reused from `skills/scaffold-init/test_skill_surface.py` (`DescriptionBoundsTests`)
- ✅ Trigger phrase set agreed (positive: "score", "run the oracle", "run quality gate", "check the oracle"; negative: "set up", "install", "scaffold", "fix the test")

**Acceptance Criteria:**

1. **SKILL.md trigger phrases.** SKILL.md description fires on "score this code", "run the oracle", "run quality gate", "what's the oracle score?", and similar; does *not* fire on "set up servo" / "scaffold oracle" (those are spec 001's territory) nor on "fix the failing test" / "make tests pass" (out of scope).
2. **Options section documented.** The body lists `--json`, `--verbose`, `--timeout <seconds>`, and the `audit` subcommand with one-line descriptions and an example invocation each.
3. **Refusal handling.** SKILL.md tells the LLM how to react to rc=2 — distinguish missing-oracle (suggest `/servo:scaffold-init`) from missing-manifest (same) from timeout (offer to re-run with a longer `--timeout`) from unparseable output (surface raw stderr). Do NOT silently retry.
4. **Audit example.** At least one example shows a user asking "what does this servo install include" → the LLM runs `gate.py audit <target>` and surfaces the output.
5. **No SKILL.md regressions for scaffold-init.** `skills/scaffold-init/test_skill_surface.py` still passes; the new `skills/quality-gate/test_skill_surface.py` passes too.

**DoD:** _(same shape)_
- [x] All ACs pass; both surface test files green. _18/18 in `quality-gate/test_skill_surface.py`; 13/13 in `scaffold-init/test_skill_surface.py` regression; 75/75 in `test_gate.py`; 40/40 in `test_scaffold.py`. Total 146 tests across four files._
- [x] Test coverage per AC: AC1→`DescriptionBoundsTests` (4 tests, including positive + negative + audit trigger + sibling-pointer assertions). AC2→`OptionsSectionTests` (5 tests, `--json` + `--verbose` + `--timeout` + audit + examples). AC3→`RefusalHandlingTests` (4 tests, refusal section + reason taxonomy + no-silent-retry + recovery pointers). AC4→`AuditExampleTests` (3 tests, presence + install contents + no-oracle assertion). AC5→cross-skill regression by running both surface test files (passes confirmed).
- [x] Reviewer subagent review. _2026-05-18, PASS verdict (clean). Four non-blocking caveats around surface-test substring looseness — same family as the pre-existing 001-05 entries in `docs/refinement-todo.md`._
- [x] Implementation review passed.
- [x] Reconciliation review passed.
- [x] `docs/refinement-todo.md` updated. _One new entry: surface tests for quality-gate inherit the loose-substring pattern from scaffold-init (sibling refinement-todo entries share a fix path). Reasons not enumerated in surface tests (`manifest_malformed`, `manifest_invalid_key`, `target_*`, `invocation_failed`) covered by `test_reason_field_documented`'s common-six subset; broader coverage deferred._

### Close-out (post-DONE)

- [x] SKILL.md anti-greediness tests pass (`python3 skills/quality-gate/test_skill_surface.py`). _18/18 green; pytest auto-discovery works because the file uses `unittest.TestCase` with no pytest-specific syntax (matches the 001-05 pattern)._
- [x] `README.md` skills table row for `quality-gate` flipped to DONE.
- [x] `docs/specs/README.md` status board: spec 002 → DONE.

**Anti-horizontal-phasing check:** After this slice, the user-facing surface is complete — typing a trigger phrase produces a real gate invocation with structured output and timeout safety. This is the slice that closes the spec.

### Deviation log (after reconciliation)

**Slice 002-05 — implemented 2026-05-18.** 18 surface tests green in `skills/quality-gate/test_skill_surface.py`; 13 surface tests in `scaffold-init/test_skill_surface.py` still green (no sibling regression). End-to-end check: SKILL.md frontmatter declares the skill, lists positive + negative triggers, points at the sibling `/servo:scaffold-init` for scaffolding requests; body documents the three options (`--json`, `--verbose`, `--timeout`) + audit subcommand + the 11-reason refusal taxonomy + recovery pointers + concrete examples.

Deviations from spec text:

- **Refusal table enumerates 11 `reason` codes**, not just the 4-5 named in AC #3 (missing-oracle, missing-manifest, timeout, unparseable output). The taxonomy locked in slices 002-01..04 is: `target_missing`, `target_not_directory`, `manifest_missing`, `manifest_malformed`, `manifest_invalid_key`, `oracle_missing`, `oracle_not_executable`, `invocation_failed`, `timeout`, `unexpected_exit`, `unparseable_oracle_output`. SKILL.md documents all 11 with recovery hints; surface tests only assert the 6 most common (`test_reason_field_documented`). Broader enumeration in tests deferred.
- **Trigger-phrase substring assertions remain loose**, inheriting the pattern from `scaffold-init/test_skill_surface.py`. Same caveat as the pre-existing 001-05 refinement-todo entries. Not regressed by this slice.
- **`SERVO_GATE_TIMEOUT` env var documented inline with `--timeout`** in the Options table. Spec didn't require it be discoverable from SKILL.md (env vars are usually invisible to the LLM), but surfacing it here makes the timeout knob fully visible in one place.
- **Audit example walks through the user-facing UX**, not just the helper invocation. Spec AC #4 said "at least one example shows a user asking...". SKILL.md has the audit example formatted as a user/assistant exchange + the expected stdout structure, so the LLM has a template to follow.

**Reviewer caveats not addressed in-flight** (logged here for traceability):

- Surface tests' loose-substring pattern (e.g., `"longer"` in `test_recovery_pointers_present`) inherits the 001-05 entries already in `docs/refinement-todo.md`. New refinement-todo entry added for quality-gate's variant.
- Pre-existing 002-01..04 entries in `docs/refinement-todo.md` still apply.

**Reviewer verdict:** PASS (independent review, `jig:reviewer` subagent, 2026-05-18). All 5 ACs met by observable surface tests; refusal table enumerates the closed `reason` taxonomy with recovery hints; sibling skill (`/servo:scaffold-init`) explicitly pointed-at for out-of-scope triggers; cross-spec regression on `scaffold-init/test_skill_surface.py` confirmed green. **Spec-level verdict from the reviewer:** spec 002 is ready to mark DONE after dogfood + close-out actions land.

---

## Spec-level Definition of Done

- [x] All five slices DONE (002-01 invoke-passthrough, 002-02 structured-output, 002-03 manifest-aware, 002-04 timeout-safety, 002-05 qa-wizard) — each reviewed by `jig:reviewer` subagent. Verdicts: 002-01 PASS, 002-02 PASS, 002-03 PASS, 002-04 PASS-WITH-CAVEATS (all caveats addressed in-flight), 002-05 PASS. 146 tests across four files: `test_gate.py` (75), `test_skill_surface.py` (18), `test_scaffold.py` (40 regression), `scaffold-init/test_skill_surface.py` (13 regression).
- [x] End-to-end dogfood: three scenarios run 2026-05-18, all PASS:
  1. **Pass-path JSON.** Scaffold a tmp project + pass-path oracle → `gate.py --json` emits `{schema_version: 1, status: "pass", composite: 0.95, ...}`, exit 0. ✓
  2. **Timeout path.** Replace oracle with `sleep 5` body → `gate.py --timeout 1 --json` exits 2, `reason=timeout`, `timeout_seconds=1.0`. ✓
  3. **Manifest-missing refusal.** `mv .servo/install.json .bak` → `gate.py --json` exits 2, `reason=manifest_missing`. ✓
- [x] [README.md](../../../README.md) skills table: `quality-gate` row reads `DONE`.
- [x] `docs/architecture.md` "Runtime artifacts" section unchanged (gate is stateless, no new disk artifacts at `<target>/.servo/`). New "Quality-gate JSON contract" section added below it documenting the closed exit codes, JSON schema, full 11-code `reason` taxonomy, audit JSON shape, and timeout machinery.
- [x] One ADR recorded. _[ADR-0002](../../decisions/adr-0002-gate-caller-contract.md) Accepted 2026-05-18 — closed 0/1/2 exit codes + versioned `--json` schema. Both clauses verified in tests (`UnexpectedExitTests` for the closed-exit clause; `JsonOutputTests.test_schema_version_present_and_equals_one` for the schema-version clause across all five JSON-emitting paths)._
- [x] [docs/specs/README.md](../README.md) status board reflects DONE.

## Critical files (when implementation starts)

In jig (reference patterns):
- `skills/tdd-loop/tdd.py` — subprocess invocation + exit-code passthrough pattern (mirror for 002-01)
- `skills/pr-review/test_skill_surface.py` — anti-greediness test pattern (mirror for 002-05)

In servo (already shipped by spec 001):
- `skills/scaffold-init/scaffold.py` — manifest schema source; gate.py mirrors its CLI shape
- `templates/oracle.sh.template` — the contract source (exit codes, summary line format)
- `skills/scaffold-init/SKILL.md` — Q&A surface pattern for 002-05

In this spec (to be created):
- `skills/quality-gate/gate.py` — new in 002-01, extended each slice
- `skills/quality-gate/test_gate.py` — new in 002-01, extended each slice
- `skills/quality-gate/SKILL.md` — new in 002-05
- `skills/quality-gate/test_skill_surface.py` — new in 002-05

## Clarifications

Recorded 2026-05-18 via `/jig:clarify` before READY_FOR_REVIEW. Q1 and Q3 jointly captured as [ADR-0002](../../decisions/adr-0002-gate-caller-contract.md) because they define the gate's outward caller contract.

### Q1: What should `gate.py` do if `oracle.sh` exits with a code outside the 0/1/2 contract (e.g., signal-killed = 137, buggy = 99)?
_(category: Edge Cases & Failure Modes)_

**Remap to rc=2.** Treat any non-contract exit as `status=env_error reason=unexpected_exit code=<N>`. Keeps the gate's 0/1/2 contract strictly closed; callers never see surprise codes. Captured in [ADR-0002](../../decisions/adr-0002-gate-caller-contract.md).

### Q2: What should `--timeout 0` mean?
_(category: Edge Cases & Failure Modes)_

**Disable timeout.** Treat 0 as 'no bound'. Useful for human runs where you want unbounded wait; unattended callers can still pass a positive value.

### Q3: Should the `--json` output schema (slice 002-02) carry a `schema_version` field from day one?
_(category: Non-functional Requirements)_

**Yes, schema_version=1.** Add the field upfront so 003/004/005 can detect future schema changes. Cheap insurance for a contract three runtime skills depend on. Captured in [ADR-0002](../../decisions/adr-0002-gate-caller-contract.md).

### Q4: What should `gate.py` do if `<target>/oracle.sh` exists but is not executable (e.g., chmod was lost by a git operation)?
_(category: Edge Cases & Failure Modes)_

**Refuse with chmod hint.** Exit 2 with stderr naming `chmod +x oracle.sh` so the user recovers explicitly. Never silently mutate the target's filesystem.

### Coverage summary

| Category | Status |
|---|---|
| Scope & Boundaries | Clear |
| Acceptance Criteria Testability | Clear |
| Dependencies & Blockers | Clear |
| Non-functional Requirements | Resolved |
| Edge Cases & Failure Modes | Resolved |
| Terminology Consistency | Clear |
