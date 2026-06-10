---
status: DONE
dependencies: []
last_verified: 2026-06-10
---

## Slice 006-02 — check-library

**Goal:** Implement the deterministic check primitives and compile
planned checks into a runnable stdlib-only `checks.py` that emits one
JSON line per AC plus a summary score.

**DoR:**
- ✅ Slice 006-01 DONE.
- ✅ `checks.json` schema from 006-01 is stable enough for first
  implementation.
- ✅ Check primitives do not require network access.

**Acceptance Criteria:**

1. **Primitive coverage.** `checks.py` supports command, file presence,
   text invariant, JSON contract, archive inventory, Markdown local-link,
   generated-artifact command, and runtime-reference scan checks.
2. **Structured output.** A run emits JSONL evidence with
   `schema_version`, `check_id`, `ac_id`, `status`
   (`pass`/`fail`/`env_error`/`not_applicable`), and an actionable
   `message`.
3. **Composite score.** The final summary reports
   `passed_checks`, `failed_checks`, `env_errors`, `not_applicable`,
   and `score` in `[0.0, 1.0]`.
4. **Fixture-proven failures.** Each primitive has at least one passing
   and one failing fixture test, and failing diagnostics name the
   offending path/command/key.
5. **Dependency-free.** The generated runner uses only Python stdlib.

**DoD:**
- [x] All ACs pass; full test suite green.
- [x] Test coverage per primitive, including failure diagnostics.
- [x] Reviewed by `reviewer` subagent.
- [x] Implementation review passed.
- [x] Deviation log produced under this slice heading.
- [x] Reconciliation review passed.

### Close-out (post-DONE)

- [x] `docs/specs/README.md` status board updated.

**Anti-horizontal-phasing check:** After this slice, a generated plan can
be executed manually and produce AC-level evidence, even before it is
wired into `oracle.sh`.

### Deviation log (after reconciliation)

Original ACs above are preserved; this records what changed during
implementation. Implemented 2026-06-10; 90 tests in
`skills/spec-oracle/test_checks.py`; full suite 560 passed, 1 skipped (the
skip is the pre-existing shellcheck/Docker-daemon skip, unrelated to 006-02).

- **Engine, not per-spec codegen (scope clarification).** The spec's evidence-
  contract file tree lists `checks.py` under `.servo/spec-oracles/<id>/`, which
  reads as a *generated* per-spec artifact. This slice instead ships one
  reusable engine at `skills/spec-oracle/checks.py` that *consumes* a
  `checks.json` plan and is runnable standalone
  (`python3 checks.py <checks.json>`). The anti-horizontal-phasing check ("a
  generated plan can be executed manually and produce AC-level evidence") is
  about *running a plan*, which the engine satisfies. Emitting/installing a
  per-spec runner + `oracle.sh.fragment` is explicitly slice 006-03's goal;
  building the engine first keeps the families testable in isolation and avoids
  duplicating primitive code into every generated tree.
- **Executable check schema defined here.** 006-01 emits planning-level entries
  (`family` + `statement` + `status:"planned"`, no executable fields). This
  slice defines the per-family executable fields the runner reads — `command` /
  `expected` / `working_directory` / `timeout`; `path` / `exists` /
  `executable`; `contains` / `not_contains` / `regex` / `not_regex`;
  `required_keys` / `equals`; `contains` / `excludes`; `path` / `root`;
  `source` / `build_command` / `working_subdir`; `needle` / `regex` / `roots` /
  `exclude`. Elaborating a planned check into an executable one is manual (or a
  future planner pass); an **unelaborated** check (family but no exec fields)
  resolves to `env_error`, so the runner never silently passes a check it
  cannot actually evaluate.
- **Status rule (made explicit).** `fail` = target exists/ran and the assertion
  was violated (message names the offending path/command/key, AC4); `env_error`
  = the check could not be evaluated (missing/unreadable target, malformed spec,
  command not found, timeout). Existence is asserted *only* by `file_presence`;
  every other primitive `env_error`s on a missing target rather than guessing.
  The one nuance: `json_contract` treats an existing-but-unparseable file as
  `fail` ("is valid JSON" is itself the contract) but a missing file as
  `env_error`.
- **Score policy (one open question deferred).** `score = passed / (passed +
  failed)`; `env_error` and `not_applicable` are excluded from the denominator
  (env errors are surfaced separately and as exit 2; judgment ACs must not
  dilute the deterministic score). With no pass/fail records, `score` is `0.0`
  if anything env-errored and `1.0` if the only records were `not_applicable`.
  Whether *unresolved residual judgment* should **block** a perfect overlay
  score is the spec's open question and is explicitly deferred to slice 006-04
  (freeze-and-controls).
- **Exit-code contract + `--ledger` are forward seams (used in 006-03).** The
  CLI exits 2 on any env error, 1 on any failure, else 0 (servo's existing
  convention), and can append evidence JSONL to a `--ledger` file. Wiring the
  engine into `oracle.sh` and the per-spec ledger is slice 006-03; this slice
  only provides the writer and the score/exit semantics it will reuse.
- **Evidence/summary schema additions beyond AC2's named keys.** Each record
  also carries `kind` (`evidence`/`summary`) and `family` plus family-specific
  diagnostics (`command`, `exit_code`, `path`, `line`); the summary adds
  `total` alongside the five AC3 counts. Additive, mirroring 006-01's pattern
  and the spec's "schema can evolve before implementation" license.
- **Bounded command execution.** `command` and `generated_artifact_command` run
  argv lists (never `shell=True`; string commands are `shlex.split`) in their
  own process group under a per-check `timeout` (env default `SERVO_CHECK_TIMEOUT`,
  120s, `0` disables), with SIGTERM → grace → SIGKILL — mirroring `gate.py`
  (slice 002-04).
- **Known limitation (logged to refinement-todo).** `markdown_links` parses only
  inline `[text](target)` links; reference-style `[text][ref]` links are not yet
  resolved. No fixture or current servo doc uses reference-style links.
- **Review-driven hardening.** Independent review (PASS) prompted three
  follow-ups, all applied: a defensive `_expected_exit_code` (accepts
  `{"exit_code": N}` or a bare int, never raises on a malformed value); a test
  asserting the `generated_artifact_command` failure diagnostic names the
  command (AC4 completeness); and added coverage for the `working_subdir` and
  markdown-`root` branches.

**Reconciliation review (inline):** deviation log checked against the diff
(faithful — no source-spec ACs or DoD were rewritten); the two new files live
only under `skills/spec-oracle/`; scope boundaries to 006-03 (overlay install +
ledger wiring) and 006-04 (approval/freeze/negative-controls + residual-blocking
policy) are respected; the only doc edits are this slice's DoD/close-out ticks,
the deviation log, the regenerated status board, and a refinement-todo entry for
reference-style Markdown links.

---

