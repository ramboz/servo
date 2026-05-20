# Refinement TODO

Decisions deferred during servo's own development (not the target-project refinement-todo that 001-04 will scaffold — that one lives in `<target>/.servo/refinement-todo.md`).

Each entry: heading, Deferred reason, Resolution trigger.

---

## ~~Shellcheck verification falls back to skip on dev machines~~ — RESOLVED 2026-05-15

**Resolution:** `scripts/shellcheck.sh` wraps both the local binary (preferred) and the `koalaman/shellcheck:stable` Docker image (fallback), exiting 127 only when neither is available. `ShellcheckTests.test_rendered_oracle_shellcheck_clean` now invokes the wrapper and skips only on exit 127, so on any dev box with Docker the assertion actually runs. Verified: 34/34 tests green with zero skips on this branch even though the local `shellcheck` binary is absent.

---

## ~~Jig-fallback failures are silent~~ — RESOLVED 2026-05-15

**Resolution:** `_jig_tdd_detect` now returns `(framework, status)` where status ∈ `{absent, success, failed, unknown}`. The four non-absent failure modes (timeout, OSError, non-zero exit, JSON decode, missing framework key, out-of-vocab framework) each emit a distinct stderr breadcrumb naming the failure cause. `detect_signals` consumes the status to set the manifest `detector` field to the detector actually *used* (jig only on `success`), not merely "jig present on disk". A silent jig regression is now impossible.

---

## No automated test for the jig-present detector path

**Deferred:** `JigFallbackTests` covers the no-jig branch for all five test frameworks; the jig-present branch is "exercised by manual smoke" per ADR-0001 and not gated. The normalization map (`framework` / `runner` / `name`) and the vocabulary check (`framework in TEST_COMPONENTS`) are untested.

**Resolution trigger:** First time `_jig_tdd_detect` regresses (or when servo gets a CI pipeline that can stand up a fake-jig fixture). Easy fix: write a `tmp/jig/skills/tdd-loop/tdd.py` shim in the test that prints a chosen JSON shape, point CLAUDE_PLUGIN_ROOT at that tmp, assert servo picks up the shim's framework name. Three test cases (one per accepted key, one for the out-of-vocab fall-through) close the gap.

**Surfaced by:** slice 001-03 reviewer pass; ADR-0001 acknowledges this gap explicitly.

---

## ~~Threshold default of 0.5 is arbitrary~~ — RESOLVED 2026-05-15 by slice 001-04

**Resolution:** Slice 001-04 emits a `Threshold` decision into every scaffolded `<target>/.servo/refinement-todo.md`, pinning `DEFAULT_THRESHOLD = 0.5` as a constant in `scaffold.py` (kept in sync with the template's static `0.5`) and quoting it back to the user along with a resolution trigger ("first time the oracle gate misfires"). The arbitrariness is now surfaced explicitly at the install site, not buried in servo's own dev notes.

---

## `DEFAULT_THRESHOLD` is duplicated between `scaffold.py` and the oracle template

**Deferred:** `scaffold.py:DEFAULT_THRESHOLD = 0.5` and `templates/oracle.sh.template:THRESHOLD="${THRESHOLD:-0.5}"` are two sources of truth. The refinement-todo quotes back the Python constant; the runtime oracle uses the bash literal. If either is ever changed without the other, the scaffolded install will quote a value back to the user that disagrees with what the script actually defaults to.

**Resolution trigger:** First proposal to change the default threshold, OR the next template refactor that touches the substitution markers. Introduce a `{{THRESHOLD_DEFAULT}}` placeholder in the template and have `_render_oracle` substitute `str(DEFAULT_THRESHOLD)` at scaffold time. Add a test that asserts the rendered oracle's literal default matches the constant.

**Surfaced by:** slice 001-04 reviewer pass.

---

## "Custom signals" deferral category not emitted

**Deferred:** Slice 001-04's goal text named four deferred-decision categories (weights, threshold, ambiguous, **custom signals**), but no AC required the fourth and the implementation only emits the first three. The user's path to "add your own signal" today is the `# SEED:` block convention surfaced in the template's comment header and `README.md` — not the refinement-todo.

**Resolution trigger:** First user feedback that `refinement-todo.md` should explicitly invite custom signals (especially in the no-signals case, where the current refinement-todo has only Threshold). When that lands, add a `## Custom signals` block citing the `# SEED:` convention and `README.md#adding-a-component`. Emit unconditionally, or gate on `len(components) == 0`.

**Surfaced by:** slice 001-04 reviewer pass.

---

## Env-error test bypasses production code path

**Deferred:** Slice 001-02 AC #3 ("env error distinguishable from below-threshold") is tested by `EnvErrorDistinguishableTests`, which **patches the scaffolded `oracle.sh`** to inject a component returning `rc=2`. That's a fair structural test of the driver's exit-2 propagation, but the *shipped* `placeholder` component never returns 2 — so no naturally-scaffolded output exercises the env-error path today. Acceptable here because no real components exist yet (signal detection is 001-03), but the gap should close when real components land.

**Partial resolution (2026-05-15, slice 001-03):** Real shipped components now exist (pytest, vitest, jest, cargo, go, eslint, ruff) and each documents a `return 2` path on missing tool. `JigFallbackTests` exercises the natural detection path but does not execute the scoring functions, so the env-error exit-2 contract is still verified only by the patched-template test in `EnvErrorDistinguishableTests`. Leaving the entry open: closure requires an integration test that scaffolds a target with (say) pytest detected, runs the oracle with `PATH` stripped, and asserts exit 2 + a stderr mention of the component name.

**Resolution trigger:** Next time the env-error path regresses, OR opportunistically when servo gets a CI pipeline that can cheaply isolate `PATH`. The patched-template test stays as a driver-mechanics check; the new test would close the production-code-path gap.

**Surfaced by:** slice 001-02 reviewer pass.

---

## SKILL.md anti-greediness tests have soft negative-trigger checks

**Deferred:** `DescriptionBoundsTests.test_negative_triggers_in_description` only asserts that the strings "oracle" and "score this code" *appear somewhere* in the description and that some exclusion word ("do not" / "don't" / "skip") is present. A future broadening that added "review my code" or "score tests" as a *positive* trigger would still pass — the test never enforces that those phrases live inside a do-not block specifically.

**Resolution trigger:** Next time SKILL.md gets edited, OR when servo grows a second skill with its own surface tests. Tighten the assertion to: split the description into "fire" and "do not fire" sections by marker, assert positive phrases appear in the fire section only, assert negative phrases appear in the do-not section only.

**Surfaced by:** slice 001-05 reviewer pass.

---

## SKILL.md body tests check substrings globally, not by section

**Deferred:** `QAQuestionsTests`, `SkippabilityTests`, and `RefusalSurfacingTests` lowercase the entire SKILL.md and check for substring presence anywhere — so a SKILL.md with the right keywords in the wrong sections (Q&A options dumped in a comment, trigger phrases in the body instead of the description) could still pass. Only `DescriptionBoundsTests` correctly isolates the YAML frontmatter via regex.

**Resolution trigger:** Same as above. Extract a `_section(text, heading)` helper that scopes substring checks to the named section, then refactor the three body tests to use it.

**Surfaced by:** slice 001-05 reviewer pass.

---

## `test_signal_killed_remapped_to_two` assertion is platform-loose

**Deferred:** `UnexpectedExitTests.test_signal_killed_remapped_to_two` asserts `"unexpected code"` in stderr but doesn't pin the exact code (143 on Linux/macOS via `128 + signo`, but could be negative on platforms where Python reports `-signo` for signal-killed children). The reliance on the substring match is defensible — the gate's contract is "rc=2 with some unexpected-code message" — but two parallel assertions (one for positive `128 + signo`, one tolerating negative returncode) would be a stricter cross-platform guarantee.

**Resolution trigger:** First CI run on a platform where Python reports a negative returncode for signal-killed children, OR the next time the test is touched for any reason.

**Surfaced by:** slice 002-01 reviewer pass (`jig:reviewer`, PASS verdict).

---

## `gate.py` does not guard against non-regular-file `oracle.sh`

**Deferred:** `gate.py` checks `oracle.exists()` and `os.access(oracle, os.X_OK)` but does not verify the path is a regular file. A target with `oracle.sh` as a directory, FIFO, device file, or dangling symlink would pass the existence check, fail at subprocess.run, and surface an OSError message (caught by the generic `_refuse` handler — so rc=2 with `"failed to invoke oracle.sh: ..."`).

End-state behavior is still rc=2, which is the contract — but the error message is less actionable than the dedicated chmod-hint refusal. Adding `oracle.is_file()` would surface a clearer "oracle.sh is not a regular file" message.

**Resolution trigger:** First report of a confused user staring at "failed to invoke oracle.sh: ..." stderr because their `oracle.sh` is somehow a directory. Cheap fix when it lands.

**Surfaced by:** slice 002-01 reviewer pass (`jig:reviewer`, PASS verdict).

---

## Quality-gate surface tests inherit loose-substring pattern from scaffold-init

**Deferred:** `skills/quality-gate/test_skill_surface.py` uses the same loose-substring assertions as `skills/scaffold-init/test_skill_surface.py` (`test_recovery_pointers_present` asserts `"longer"` for the timeout recovery hint; positive triggers checked as substrings; etc.). A future docs reword could break the test without changing behavior. Also: surface tests only assert 6 of the 11 `reason` codes (`manifest_missing`, `oracle_missing`, `oracle_not_executable`, `timeout`, `unparseable_oracle_output`, `unexpected_exit`) — the remaining 5 (`target_missing`, `target_not_directory`, `manifest_malformed`, `manifest_invalid_key`, `invocation_failed`) are documented in SKILL.md but not test-asserted.

**Resolution trigger:** Same family as the pre-existing 001-05 entries above ("SKILL.md anti-greediness tests have soft negative-trigger checks" + "SKILL.md body tests check substrings globally"). Bundle the fix: extract a `_section(text, heading)` helper and a tighter trigger-assertion pattern, then update both `scaffold-init/test_skill_surface.py` and `quality-gate/test_skill_surface.py` together. Broader reason-code coverage is a separate one-line addition to `test_reason_field_documented`'s tuple.

**Surfaced by:** slice 002-05 reviewer pass (`jig:reviewer`, PASS verdict).

---

## Spec 003 spike open questions (Q1, Q2, Q5, Q6) await live-claude verification

**Deferred:** The pre-spec research [spike](specs/003-agent-loop/spike.md) flagged six open questions; Q3 and Q4 were resolved in the spec body. Q1, Q2, Q5, Q6 were tagged "await empirical verification at their respective slices" — but every slice 003-01..05 test uses a mock-claude harness via PATH injection (the AC8 contract), so no slice has actually exercised a live `claude -p` invocation against the spike's predictions.

The four still-open questions:

- **Q1: `terminal_reason` taxonomy from `claude -p` JSON output.** Spike captured `terminal_reason="completed"`. Other plausible values: `budget_exceeded`, `error`, `interrupted`, `timeout`. Slice 003-02's cost-ceiling logic assumes the mock harness's `"completed"`; an unexpected real-world value falls into the loop's "claude-terminal-reason-pass-through" branch (per-iter JSON emits whatever claude says) but doesn't drive halt logic — the cumulative tracking is the brake.
- **Q2: `stop_reason` taxonomy.** Spike captured `stop_reason="end_turn"`. Other Anthropic-API-named values: `max_tokens`, `tool_use`, `stop_sequence`, `pause_turn`. Less load-bearing than Q1; the loop doesn't branch on `stop_reason` today.
- **Q5: `--max-budget-usd` halt granularity.** Does `claude -p --max-budget-usd X` clean-halt before the next API call would exceed budget, or partway through with a partial response? Slice 003-02's cumulative tracking handles either case (the per-iter cost is summed regardless), but the per-iter `--max-budget-usd` defense-in-depth floor (`MIN_BUDGET_FLOOR_USD=0.01`) was picked conservatively without empirical data.
- **Q6: `--agent <name>` + permissions inheritance.** When `loop.py` invokes `claude --agent runner -p "..."`, does the agent's own `tools:` frontmatter authoritatively narrow the toolset, or does the parent invocation's `--allowedTools` / `--disallowedTools` (if any) intersect with the frontmatter? Slice 003-05's `runner.md` and `judge.md` declare their own `tools:` frontmatter and the loop does NOT pass parent-level `--allowedTools`; the assumption is "frontmatter authoritative." Untested against live `claude -p`.

**Resolution trigger:** First live `claude -p` invocation against a real servo target — either (a) a user runs `/servo:agent-loop` and reports an unexpected behavior, or (b) dogfooding for spec 004 / 005 surfaces a difference. When triggered, update the relevant slice's deviation log and either keep the spike's assumption documented or amend `loop.py` to match observed reality. **A note:** the spec text at `docs/specs/003-agent-loop/spec.md` mentions "all five open questions from spike.md 'Open questions' are either resolved..." — the count is six (Q1–Q6); Q3 / Q4 resolved in spec; Q1, Q2, Q5, Q6 deferred here.

**Surfaced by:** Slice 003-05 reconciliation review (`jig:reviewer`, 2026-05-20). The reviewer flagged that no slice empirically verified the spike's spike-shape predictions, despite the spike's "verification at the slice" promise. Deferring rather than blocking close-out because the entire spec was built on the mock-harness assumption and the spike's central question ("loop driver subprocesses claude, parses JSON, decides") was validated in vitro across 5 slices.

---

## Scaffold-init does not write `<target>/.gitignore`

**Deferred:** Slice 003-04 (checkpoint-resume) ships per-run state at `<target>/.servo/runs/<run-id>/state.json`. The spec's close-out item asks: "`.gitignore` updated to ensure `<target>/.servo/runs/` is ignored on the target — confirm spec 001's scaffold already adds this; if not, file a refinement-todo." `skills/scaffold-init/scaffold.py` does not currently touch `<target>/.gitignore`, so a target that runs `/servo:scaffold-init` followed by `/servo:agent-loop` will start checking in `<target>/.servo/runs/*/state.json` (and any future race / hook artifacts) unless the user manually adds the line.

`docs/architecture.md` "Runtime artifacts" already states the paths "are reserved (in `.gitignore`)" — that statement is aspirational, not enforced by the scaffolder.

**Resolution trigger:** First user report that servo's runtime artifacts polluted their commits, OR opportunistically when the scaffolder grows another out-of-band artifact (e.g., spec 005's `.servo/races/`). The shape of the fix: extend `scaffold.py:_write_artifacts` to append a `.servo/runs/`, `.servo/races/`, `.servo/refinement-todo.md`, `.servo/install.json` block to `<target>/.gitignore` — idempotent (skip if the block already exists), no-op if `<target>/.gitignore` doesn't exist (target's choice not to track gitignore is the target's call). Add a test under `test_scaffold.py` that asserts the block lands.

Target-side .gitignore is the target's concern, not servo's, but the scaffolder is the natural place to suggest the additions — same shape as jig's scaffold-init nudging `.claude/` paths.

**Surfaced by:** Slice 003-04 reconciliation review (`jig:reviewer`, 2026-05-20). The spec close-out item explicitly contemplated this path.

---

## `DEFAULT_CONTEXT_FILL_THRESHOLD = 0.75` is a guess

**Deferred:** `loop.py`'s context-fill refusal threshold defaults to 0.75 (75%) — picked as the midpoint of the spike's observed 60–75% range across mixed iteration loads, with no real-world tuning data. A loop running short, focused turns may reasonably tolerate fills above 0.75 before output degrades; a loop with heavy tool use that produces long agent responses may degrade well below 0.75. Without empirical data, 0.75 could be 20 percentage points too generous (false-negatives: garbage output sneaks through) or too tight (false-positives: legitimate iterations refused).

The `--context-fill-threshold` flag is the user's escape hatch (`0` disables; any value in [0.0, 1.0] tunes). But the default ships in the slice 003-03 contract and downstream slices/callers inherit it.

**Resolution trigger:** First real-world iteration data — either (a) a user reports that 0.75 produced degraded output on the iteration before the gate fired, or (b) servo's own dogfood (slice 003-05 + spec-level end-to-end) shows a different right-sized default. When triggered, either tune the default (and document in `docs/architecture.md` "Project vs servo-core split") OR add the threshold to the `<target>/.servo/refinement-todo.md` deferred-decision set so each scaffolded install gets a chance to override based on the target's workload shape.

**Surfaced by:** Slice 003-03 implementation (`/jig:spec-workflow`, 2026-05-19). DoR's "Decision: threshold default 0.75. **Flagged in `docs/refinement-todo.md` for tuning** once real-world iteration data accumulates." pre-committed to landing this entry alongside the slice.

---

## `DEFAULT_PER_ITER_BUDGET_USD = 1.00` is a guess

**Deferred:** `loop.py`'s per-invocation `--max-budget-usd` fallback when `--cost-ceiling 0` disables cumulative tracking defaults to $1.00. The value is a "sane upper bound for one agentic turn" picked without real-world data — analogous to the `DEFAULT_CLAUDE_TIMEOUT_SECONDS = 1800` guess below. A simple iteration may burn $0.05; a complex one with heavy tool use may approach $1.00 or beyond. Without empirical data, $1.00 could be 10x too generous (one runaway turn still burns $1) or 2x too tight (false-positive `budget_exceeded` on legitimate heavy iterations).

The flag is the user's escape hatch (`--cost-ceiling N` with N > 0 then sets the per-iter cap to remaining budget). But the `--cost-ceiling 0` mode is where the fallback ships and downstream slices/callers will inherit it.

**Resolution trigger:** First real-world iteration cost data — either (a) a user reports that $1/iter isn't enough for their workflow, or (b) servo's own dogfood (slice 003-05 + spec-level end-to-end) shows a different right-sized default. When triggered, either tune the default (and document in `docs/architecture.md` "Project vs servo-core split") OR introduce a `--per-iter-budget` CLI flag if a single fixed default proves insufficient.

**Surfaced by:** Independent reviewer pass on slice 003-02 (`jig:reviewer` subagent, 2026-05-19). The reviewer flagged it as a non-blocking caveat alongside the existing `DEFAULT_CLAUDE_TIMEOUT_SECONDS` entry — both are "best guess" defaults waiting on tuning data.

---

## `DEFAULT_CLAUDE_TIMEOUT_SECONDS = 1800` is a guess

**Deferred:** `loop.py`'s per-invocation `claude -p` timeout defaults to 1800s (30 min). The value was picked without real-world iteration data — it's a generous upper bound chosen to be "long enough for substantial agentic turns with tool use, short enough that an unattended loop won't hang for days if claude wedges." A real-world loop running on a complex target may regularly take 5–20 minutes per iteration (compile cycles, test runs, large code edits); a simple target may finish in seconds. Without data, 1800s could be 10x too generous (wasteful when claude wedges in CI) or 5x too tight (false-positive timeouts on heavy iterations).

The `SERVO_CLAUDE_TIMEOUT` env var is the user's escape hatch today; `0` disables the bound entirely. But the default ships in the slice 003-01 contract and downstream slices (003-02 cost ceiling, 003-04 state file) inherit it.

**Resolution trigger:** First real-world iteration data — either (a) a user reports that 1800s isn't enough for their workflow, or (b) servo's own dogfood (slice 003-05 + spec-level end-to-end) shows a different right-sized default. When triggered, either lower the default to a tighter value (and document the tradeoff in `docs/architecture.md` "Project vs servo-core split") OR introduce a `--claude-timeout` CLI flag if env-var-only proves insufficient.

**Surfaced by:** PR-review pass on slice 003-01 (multi-perspective `pr-review` skill, 2026-05-19). The reviewer flagged "no timeout on `claude -p` subprocess" as a Should-Fix reliability gap; slice 003-01 closed the gap by landing the timeout, but the picked default needs tuning data.

---

## ~~`SERVO_VERSION` constant is dead code in `gate.py`~~ — RESOLVED 2026-05-19

**Resolution:** Removed in the pre-003-03 cleanup pass. `skills/quality-gate/gate.py` no longer declares `SERVO_VERSION`; the constant lives only in `skills/scaffold-init/scaffold.py` where it's actually used (manifest write). 75/75 `test_gate.py` still green post-removal.

---

## ~~ADR-0004 run-id precision: prose says "millisecond" but example uses seconds~~ — RESOLVED 2026-05-19

**Resolution:** Picked path (a) from the original entry — keep seconds-precision in the implementation (matches the example and the test regex) and amend ADR-0004's prose to match. Three spots in `docs/decisions/adr-0004-session-state-file-format.md` were updated: the "Run-id format" sentence, the collision-policy paragraph, and the Neutral consequence bullet. A new sentence at the end of the collision-policy paragraph names millisecond precision as the documented escape hatch if spec 005's parallel-variant fan-out ever surfaces a real collision rate the seconds window can't absorb — so future bumps don't need a new ADR. Slice 003-04 inherits the frozen seconds-precision format with no further reconciliation work.

---

## `gate.py audit` parses component weights from `oracle.sh` (soft template coupling)

**Deferred:** The manifest written by `scaffold.py` carries component names but not weights (the per-component weight lives only in the scaffolded `oracle.sh`'s `COMPONENTS=( "name:weight" )` array). `gate.py audit` enriches the text-mode component listing with weights by parsing oracle.sh via `_ORACLE_COMPONENT_ENTRY_RE`. This is a best-effort coupling — if `templates/oracle.sh.template` ever changes its COMPONENTS array shape, audit will silently fall back to no-weight rendering (the function returns `{}` on any parse failure).

The clean fix is to extend the manifest schema to carry weights directly (`{"components": [{"name": "pytest", "weight": 1.0}, ...]}`). That requires touching spec 001 (the manifest contract was frozen at 001-03) and probably warrants an ADR ("Quality-gate extends manifest schema to include component weights"). Deferred until the coupling actually breaks or a future spec wants weights for another reason (e.g., spec 003 agent-loop wanting to log per-component scores per iteration).

**Resolution trigger:** Either (a) a future template-shape change exposes the coupling, or (b) spec 003+ requires manifest-readable weights. When triggered, write the ADR and amend `_install_manifest()` in `scaffold.py` to emit the richer shape; the gate's `_parse_component_weights` becomes dead code and can be deleted.

**Surfaced by:** slice 002-03 reviewer pass (`jig:reviewer`, PASS verdict). Implementer also flagged the coupling in `_parse_component_weights` docstring.
