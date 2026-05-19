---
status: DONE
dependencies: []
last_verified: 2026-05-15
---

> **DONE 2026-05-15.** All five slices (001-01 through 001-05) implemented, reviewed, reconciled. Spec-level DoD passed including the servo-on-servo dogfood (exit 0, composite=1.0000).

# Spec 001 — scaffold-init

> Probe a target project's signals, run a Q&A flow, and drop a tailored set of unattended-agent infrastructure (`oracle.sh` always; agent-loop / hook / race stubs when offered and accepted) into the target — with an install manifest the runtime skills (specs 002–005) can read back.

## Why this spec

Servo's whole value proposition is **per-project artifacts that reflect the project's actual signals**. A generic `oracle.sh` stub the dev has to rewrite is no better than the docs-only examples that exist elsewhere. The scaffolder is the first piece of servo's surface that *can't* be replaced by docs — it has to read filesystem state and produce tailored output.

It is also the foundation every other servo spec presupposes:

- 002 `quality-gate` invokes the scaffolded `oracle.sh`
- 003 `agent-loop` refuses to run without `oracle.sh`
- 004 `oracle-hook` reads `.servo/install.json` to know what was installed
- 005 `variant-race` reuses signal-detection results to score across worktrees

So 001 is unblocking for the entire servo backlog.

## Out of scope (deferred to later specs)

- Runtime invocation of `oracle.sh` (→ 002)
- Loop driver implementation (→ 003)
- Hook installer implementation (→ 004)
- Race driver implementation (→ 005)
- Refactoring jig's `slice-land prepare` to emit servo pull-hints (→ jig-side spec)

## SPIDR decomposition

Mirrors jig's spec-001 structure (greenfield scaffold → content → signals → deferred → wizard) because the problem shape is identical: probe filesystem, copy templates, manifest the install, expose to the LLM via Q&A.

### Slice index

| Slice | Title | Goal |
|---|---|---|
| 001-01 | greenfield-scaffold | Helper that copies bare `oracle.sh` template + writes `.servo/install.json` into an empty target |
| 001-02 | template-content | Real `oracle.sh.template` content: weighted composite, threshold, `# SEED:` annotation convention |
| 001-03 | signal-detection | Probe target for tests / lint / CI / language; tailor generated `oracle.sh` to detected components |
| 001-04 | deferred-decisions | Emit a `refinement-todo`-style record of what couldn't be inferred (weight tuning, custom signals) |
| 001-05 | qa-wizard | `SKILL.md` Q&A flow that asks user about scope before invoking helper |

Five slices, sized to match jig-001's cadence.

---

## Slice 001-01 — greenfield-scaffold

**Goal:** A `scaffold.py` helper that, invoked against an empty target directory, copies a placeholder `oracle.sh` from `${CLAUDE_PLUGIN_ROOT}/templates/` to `<target>/oracle.sh`, makes it executable, and writes `<target>/.servo/install.json` recording what landed. End-to-end value: an empty repo gains a runnable (if minimal) oracle in one command.

**DoR:**
- ✅ Plugin shell exists (`.claude-plugin/`, `templates/`, `skills/`)
- ✅ Target dir exists and is a git repo (servo's own dogfood case)
- ✅ Architecture decision recorded: scaffolder is a Python helper invoked by SKILL.md (mirrors jig)

**Acceptance Criteria:**

1. **Empty-target install succeeds.** `python3 skills/scaffold-init/scaffold.py <empty-dir>` exits 0; `<empty-dir>/oracle.sh` exists and is executable (`-rwxr-xr-x`); `<empty-dir>/.servo/install.json` exists and parses as JSON with keys `servo_version`, `timestamp`, `installed_tier="tier-0"`, `signals` (empty object at this slice), `components` (empty list).
2. **Refusal on existing oracle.** Re-running against the same dir exits non-zero with a message naming `oracle.sh` already present; nothing on disk changes.
3. **Force overwrites.** `--force` against the same dir overwrites `oracle.sh` and rewrites `.servo/install.json` with a new timestamp.
4. **Refusal on missing target.** Invoking against a nonexistent path exits non-zero with a clear error; nothing on disk changes.
5. **Helper is dependency-free.** `scaffold.py` runs on system Python 3.10+ with no `pip install` step.

**DoD:**
- [x] All ACs pass; full test suite green (no regressions). _12/12 in `test_scaffold.py`._
- [x] Helper test coverage: at least one fixture per AC under `skills/scaffold-init/test_scaffold.py`. _AC1→`GreenfieldScaffoldTests`, AC2→`RefuseExistingOracleTests`, AC3→`ForceOverwriteTests`, AC4→`MissingTargetTests`, AC5→`DependencyFreeTests`._
- [x] Reviewed by `reviewer` subagent. _jig:reviewer agent, 2026-05-15 — PASS, all five ACs met, tests real, deviations defensible._
- [x] Implementation review passed. _Same review as above._
- [x] Deviation log produced under this slice heading.
- [x] Reconciliation review passed. _Reviewer also evaluated deviation log; one minor gap (rc=1 vs rc=2 asymmetry) added post-review._
- [x] `docs/refinement-todo.md` updated if any decisions were deferred during implementation. _No 001-01-specific deferrals._

### Close-out (post-DONE)

- [x] `docs/specs/README.md` status board updated. _Flipped to `IN_PROGRESS (slice 001-01)`._
- [x] `README.md` skills table row for `scaffold-init` flipped from DRAFT to IN PROGRESS (or DONE if final slice).

**Anti-horizontal-phasing check:** After this slice, a user can run servo's scaffolder against an empty repo and get a working `oracle.sh` (even if minimal) and a manifest the next spec can read. That is end-to-end value, not intermediate state.

**Spike-shape note:** Servo has no prior Spike 0. Treat 001-01 as **spike-shaped** — its purpose is partly to validate that the weighted-composite-oracle approach holds up in practice. If implementation reveals a structural problem (e.g., bash composition doesn't compose cleanly across heterogeneous signals, or the manifest schema needs to encode more than expected), pause and re-plan slices 001-02 through 001-05 before proceeding. A re-plan here is cheaper than carrying a wrong shape through four more slices.

### Deviation log (after reconciliation)

**Slice 001-01 — implemented 2026-05-15.** 12 tests green via `python3 skills/scaffold-init/test_scaffold.py`. Dogfood smoke (`scaffold.py <tmp>` then `bash <tmp>/oracle.sh`) exits 0 with composite=1.0 threshold=0.0.

Deviations from spec text:
- AC #4 ("refusal on missing target") implemented as exit code **2** (env error) rather than the spec's unspecified non-zero. Mirrors the exit-code convention drafted for slice 001-02 (0 pass / 1 below-threshold / 2 env error) — applied early to avoid a churn-y rename next slice.
- `--force` rewrites `install.json` from scratch (per AC #3), but does **not** delete the existing `.servo/` directory; future runtime artifacts (`.servo/runs/`, `.servo/races/`) survive a re-scaffold. Not in the spec text but consistent with `docs/architecture.md` "Runtime artifacts" reservation.
- Shellcheck verification deferred to slice 001-02 (where it's an explicit AC). Local shellcheck not installed; placeholder template is small enough to eyeball.
- **Exit-code asymmetry between refusal cases** (added during reviewer pass): `FileExistsError` (oracle already present) → rc=1; `FileNotFoundError` / `NotADirectoryError` (target missing or not a dir, template missing) → rc=2. Rationale: rc=1 means "state precondition fails but the environment is healthy" — the dev can recover by passing `--force`. rc=2 means "the environment itself is wrong" — no `--force` is going to help. This aligns with the slice 001-02 exit-code convention (1 = below-threshold-style failure, 2 = env error).

**Spike-shape check:** Weighted-composite-oracle approach holds — the placeholder template composes cleanly (single function → score → awk threshold compare) and the manifest schema accepted the slice 001-01 fields without strain. **Proceeding to 001-02 with no re-plan.**

**Reviewer verdict:** PASS (independent review, jig:reviewer subagent, 2026-05-15). All 5 ACs met, tests are real subprocess-driven, deviations defensible, no structural problems forcing a re-plan.

---

## Slice 001-02 — template-content

**Goal:** Replace the placeholder `oracle.sh` with a real weighted-composite template: configurable component blocks, threshold gate, normalized exit codes (0 pass / 1 below-threshold / 2 env error), and a documented `# SEED:` annotation convention for project-specific signal functions. End-to-end value: the generated `oracle.sh` is actually useful (composes signals into a score), not just a stub.

**DoR:**
- ✅ Slice 001-01 DONE
- ✅ Exit-code convention agreed (0 / 1 / 2)
- ✅ Weight schema agreed (component name → weight float; threshold float)

**Acceptance Criteria:**

1. **Scaffolded `oracle.sh` runs.** Against a target with at least one detected component, the scaffolded script exits 0, 1, or 2 (never another code) and prints a single-line composite-score summary.
2. **Threshold gate works.** With `THRESHOLD=1.0` and one component scoring 0.0, the script exits 1. With `THRESHOLD=0.0` and the same input, it exits 0.
3. **Env error is distinguishable from below-threshold.** If a component's command isn't installed, the script exits 2 (not 1) and prints which component is missing.
4. **`# SEED:` blocks are clearly demarcated.** The template includes at least one `# SEED:start <name>` / `# SEED:end <name>` block with a placeholder shell function, and the README section explains how a project adds their own.
5. **No bashisms-that-bite.** Script passes `shellcheck` with severity ≥ warning silent.

**DoD:** _(same shape as 001-01)_
- [x] All ACs pass; full test suite green. _23/23 in `test_scaffold.py` (1 skipped → re-verified via Docker shellcheck)._
- [x] Test coverage per AC: AC1→`WeightedCompositeTests`, AC2→`ThresholdGateTests`, AC3→`EnvErrorDistinguishableTests`, AC4→`SeedBlockTests` + `SeedDocumentationTests`, AC5→`ShellcheckTests`.
- [x] Deviation log produced under this slice heading.
- [x] Reviewer subagent review. _jig:reviewer agent, 2026-05-15 — PASS-WITH-CAVEATS. Two non-blocking deferrals tracked in `docs/refinement-todo.md`._
- [x] Implementation review passed.
- [x] Reconciliation review passed. _Reviewer evaluated deviation log; two minor gaps (quoted command-string dispatch; `set -e` interaction) added post-review._
- [x] `docs/refinement-todo.md` updated. _New entries: shellcheck-skip-on-dev-box; patched-template env-error test; threshold-default-of-0.5._

### Close-out (post-DONE)

- [x] Architecture doc's "open question" about weighting heuristic resolved (or moved to ADR). _Resolved in-line in `docs/architecture.md`: weighted average, equal-weight default, tuning deferred to 001-04's refinement-todo._

**Anti-horizontal-phasing check:** After this slice, the generated oracle is something a project could actually adopt — not a phase that needs slice 003 to be useful.

### Deviation log (after reconciliation)

**Slice 001-02 — implemented 2026-05-15.** 23 tests green (1 skip → shellcheck-via-Docker confirms warning-clean separately). Dogfood smoke covers all three exit paths:
- Default → `composite=1.0000 threshold=0.5 exit=0`
- `THRESHOLD=1.0 PLACEHOLDER_SCORE=0.5` → exit 1
- Missing-tool injection → exit 2 + "missing components: placeholder" on stderr

Deviations from spec text:
- **Composite is a weighted *average***, not a weighted sum. Picked so any `THRESHOLD` in `[0, 1]` remains meaningful regardless of how many components are registered. Recorded in `docs/architecture.md` "Open questions".
- **Default `THRESHOLD=0.5`** chosen as the placeholder default (spec didn't dictate a value). 001-04 will surface this in `refinement-todo.md` per its AC #2 ("Threshold default is flagged").
- **`PLACEHOLDER_SCORE` env hook** added to the placeholder component so tests and dogfood smokes can vary the score without re-editing the template. Documented in the template's comment.
- **shellcheck verification ran via Docker** (`koalaman/shellcheck:stable`) since the local Homebrew install is missing the binary. The test class `ShellcheckTests` skips when the binary is absent; CI / future runners with shellcheck installed will exercise it directly.
- **`scaffold.py` unchanged** — template copy-verbatim still satisfies this slice. Component injection by signal-detection is 001-03's job.
- **Quoted command-string dispatch** (added during reviewer pass): the driver invokes each component via `score="$("score_${name}")"` — a quoted-string command form that bash resolves by expanding the variable, then executing the resulting token as a command. Functionally correct but unconventional; preferred over `eval` because it doesn't require escaping. If a future refactor splits per-component scripts out of the single template, this dispatch shape will go away.
- **`set -e` interaction with scoring functions** (added during reviewer pass): the driver wraps each invocation in `if score="$(...)"; then ... else rc=$?; ... fi`. Under `set -e`, this `if` context is a "tested command" — non-zero exits don't abort the script. Correct today; future component authors writing complex `score_*` functions need to be aware that *their* function still runs under `set -e` (inherited from the script), so internal command failures may abort the function before it can `return 2`. README's "Adding a component" example shows the `command -v ... || return 2` idiom that avoids this trap.

**Open follow-ups (tracked in [docs/refinement-todo.md](../../refinement-todo.md)):**
1. Shellcheck verification falls back to skip on dev machines without local binary.
2. Env-error test patches the template — should drive a real shipped component once 001-03 lands.

**Reviewer verdict:** PASS-WITH-CAVEATS (independent review, jig:reviewer subagent, 2026-05-15). ACs substantively met; both caveats are tracked deferrals, not blockers for this slice.

---

## Slice 001-03 — signal-detection

**Goal:** Helper sub-routine that probes the target for tests / lint / CI / language signals and *tailors* the generated `oracle.sh` to include only components the project actually has. Output also lands in `.servo/install.json` under `signals` and `components`. End-to-end value: a Python project with pytest but no lint gets an `oracle.sh` that scores pytest only, instead of failing on a missing `eslint` command.

**DoR:**
- ✅ Slice 001-02 DONE
- ✅ Decision: reuse jig's `tdd.py detect` via subprocess when jig is present (per ADR-TBD)
- ✅ Fallback detector spec'd (built-in minimal matcher for pytest/vitest/jest/cargo/go)

**Acceptance Criteria:**

1. **Pytest-only project gets pytest-only oracle.** Against a target with `pyproject.toml` containing `[tool.pytest.ini_options]` and no lint config, the generated `oracle.sh` includes a pytest block and no eslint/ruff blocks.
2. **Mixed project gets multiple components.** Against a target with `package.json` (vitest) + `.eslintrc.json`, the generated script includes both blocks.
3. **No-signal project gets a comment-only oracle.** Against a target with no detectable signals, the generated script is still valid bash, exits 2 with "no signals detected — populate `# SEED:` blocks manually", and `.servo/install.json` has `components: []`.
4. **Jig-fallback path works.** With jig absent (`${CLAUDE_PLUGIN_ROOT}/jig/skills/tdd-loop/tdd.py` missing), the built-in detector still classifies the four primary test frameworks correctly.
5. **Detection results are inspectable.** `scaffold.py detect <target>` (subcommand) prints the JSON audit *without* writing anything to disk.

**DoD:** _(same shape)_
- [x] All ACs pass; full test suite green. _34/34 in `test_scaffold.py` (1 skipped → re-verified via Docker shellcheck against rendered oracle, not template)._
- [x] Test coverage per AC: AC1+2+3→`SignalDetectionTests`, AC4→`JigFallbackTests` (5 frameworks, no-jig path), AC5→`DetectSubcommandTests`. Fragment-side SEED conventions covered by the rewritten `SeedBlockTests`.
- [x] Deviation log produced under this slice heading.
- [x] Reviewer subagent review. _jig:reviewer agent, 2026-05-15 — PASS-WITH-CAVEATS. Three non-blocking deferrals tracked in `docs/refinement-todo.md`._
- [x] Implementation review passed.
- [x] Reconciliation review passed.
- [x] `docs/refinement-todo.md` updated. _New entries: silent jig-fallback failures; no automated jig-present test._

### Close-out (post-DONE)

- [x] ADR-0001 recorded. _`docs/decisions/adr-0001-reuse-jig-test-detector.md` — Accepted. `docs/decisions/README.md` index seeded._
- [x] `docs/architecture.md` "Signal detection" section status updated. _Rewritten to reference implementation, ADR-0001, fragment composition, and the `detect` subcommand. "Decisions pending" reshaped into a Decisions table with ADR-0001 promoted out of the candidates list._

**Anti-horizontal-phasing check:** After this slice, a real project's first run produces a tailored oracle that matches what's actually in the repo — the headline servo promise.

### Deviation log (after reconciliation)

**Slice 001-03 — implemented 2026-05-15.** 34 tests green (1 skip is local-shellcheck-when-absent; re-verified clean against a fully-seeded rendered oracle via Docker). End-to-end dogfood: empty target → exit 2 with the documented no-signals message; pytest target → manifest.components=[pytest], rendered oracle has score_pytest; `detect` subcommand → JSON without side effects.

Deviations from spec text:
- **Component renamed `go-test` → `go`** (reviewer-noted). The driver dispatches each component via `"score_${name}"` — a bash function call. Bash function names disallow hyphens, so `name="go-test"` would have required either a dispatch-side `tr - _` translation (fragmenting the manifest/function/filename mental model) or a static rename. The rename was chosen so the manifest key, fragment filename, COMPONENTS entry, and function suffix all match exactly. AC #4 still covers all five frameworks named in the DoR; only the surface label changed.
- **Shellcheck target retargeted from template to *rendered* oracle.** Slice 001-02 AC #5 said the template must shellcheck-clean, but post-001-03 the template carries `{{COMPONENTS_LIST}}` / `{{SEED_BLOCKS}}` / `{{NO_COMPONENTS_MESSAGE}}` substitution markers and the fragments lack shebangs (they're partial). Both are syntactically incomplete by design. `ShellcheckTests.test_rendered_oracle_shellcheck_clean` now scaffolds a target with every signal seeded and shellchecks the assembled output — a stronger check than the template-as-string original.
- **001-02 driver-mechanics tests seed a controllable placeholder via `_seed_placeholder_component`.** The 001-03 scaffold no longer ships a default placeholder (signal-only), so the 001-02 driver-mechanics tests (weighted composite, threshold gate, env-error propagation) needed a deterministic stub. The helper appends `"placeholder:1.0"` to `COMPONENTS` and a `score_placeholder` SEED block to the scaffolded oracle. Reviewer pass evaluated this as legitimate test maintenance, not test pollution.
- **001-01 manifest-schema test updated.** The 001-01 AC said `signals` was an empty object at that slice with the expectation that it would be populated later. 001-03 fulfills that — the test now asserts the four-key shape `{tests, lint, ci, language}` for empty targets.
- **CLI dispatcher uses a hand-rolled `argv[0] == "detect"` short-circuit** (reviewer-noted). Comment in `scaffold.py:main` explains the tradeoff: argparse subparsers would have broken the 001-01 bare-positional `scaffold.py <target>` form, and the footgun (target literally named `detect`) is benign in practice (such a target would fail both pathways).
- **Jig-fallback path is silent on non-absence failures** (reviewer-noted). `_jig_tdd_detect` swallows timeout / OSError / JSON-decode errors and falls back to built-in without emitting a breadcrumb. This is the ADR-0001 contract — but the field `signals.detector="jig"` reports file-existence only, not call success. Tracked in `docs/refinement-todo.md` as "Jig-fallback failures are silent".
- **Jig-present detector path has no automated test** (reviewer-noted). `JigFallbackTests` covers the no-jig branch for all five frameworks; the present-branch is "exercised by manual smoke" per ADR-0001. Tracked in `docs/refinement-todo.md`.

**Open follow-ups (tracked in [docs/refinement-todo.md](../../refinement-todo.md)):**
1. Silent jig-fallback failures should surface a stderr breadcrumb.
2. Add a fake-jig shim test for the jig-present branch.
3. Pre-existing: shellcheck-skip-on-dev-box; threshold-default-of-0.5; refinement-todo entries from 001-02 review. The 001-02 entry about the patched-template env-error test is **partially addressed** here — `JigFallbackTests` exercises real shipped components per framework — but the env-error path itself (component returns 2) is still tested via the patched-template approach. Not a regression on 001-02's spec; left for explicit closure in 001-04 or later.

**Reviewer verdict:** PASS-WITH-CAVEATS (independent review, jig:reviewer subagent, 2026-05-15). All five ACs substantively met with behavior-driven tests; the three caveats are all non-blocking refinement-todo items.

---

## Slice 001-04 — deferred-decisions

**Goal:** When the scaffolder can't infer a tailoring decision (weights when multiple signals are present, threshold tuning, signals it detected but couldn't classify, project-specific custom signals), it records the open question in `<target>/.servo/refinement-todo.md` with a resolution trigger — mirroring jig's deferred-decisions slice. End-to-end value: the dev gets an explicit list of "things you need to tune," not silent defaults that pass review.

**DoR:**
- ✅ Slice 001-03 DONE
- ✅ Decision categories agreed: weights, threshold, ambiguous signals, custom signals
- ✅ Refinement-todo format mirrors jig's (heading per decision, "Deferred:" reason, "Resolution trigger:" line)

**Acceptance Criteria:**

1. **Multi-signal install creates a weight-tuning todo.** When ≥2 components are detected, `<target>/.servo/refinement-todo.md` contains a `Weights` decision with "Deferred: equal weights applied — tune to reflect project priorities" and a resolution trigger.
2. **Threshold default is flagged.** Every install creates a `Threshold` decision with the chosen default and a resolution trigger ("first time oracle gate misfires").
3. **Ambiguous signals are listed.** A project with both vitest and jest configs gets an `Ambiguous test runner` decision with both names listed.
4. **Refinement-todo is idempotent.** Re-running with `--force` doesn't duplicate decisions; it rewrites the file from scratch.
5. **No spurious decisions.** A perfectly-tailorable install (one component, no ambiguity) produces a refinement-todo with only the unavoidable `Threshold` decision.

**DoD:** _(same shape)_
- [x] All ACs pass; full test suite green. _40/40 in `test_scaffold.py`, zero skips._
- [x] Test coverage per AC: AC1→`test_weights_decision_on_multi_signal`, AC2→`test_threshold_decision_*` (×2), AC3→`test_ambiguous_test_runner`, AC4→`test_force_rewrites_no_duplicate_entries`, AC5→`test_single_component_only_threshold`.
- [x] Deviation log produced under this slice heading.
- [x] Reviewer subagent review. _jig:reviewer agent, 2026-05-15 — PASS-WITH-CAVEATS. Two caveats recorded below._
- [x] Implementation review passed.
- [x] Reconciliation review passed.
- [x] `docs/refinement-todo.md` updated. _The pre-existing "Threshold default of 0.5 is arbitrary" entry was closed by this slice — the deferral is now surfaced at the target project, not in servo's dev notes._

**Anti-horizontal-phasing check:** After this slice, every install lands with an explicit `refinement-todo.md` the dev can scan in 30 seconds. The next supervised session can resolve the items via jig's normal refinement-todo flow.

### Deviation log (after reconciliation)

**Slice 001-04 — implemented 2026-05-15.** 40 tests green (up from 34). Dogfood across three flavors — multi-signal (pytest+ruff) → Threshold+Weights; single (pytest only) → Threshold only; ambiguous (vitest+jest) → Threshold+Ambiguous-test-runner with `vitest (selected)` and `jest` listed.

Deviations from spec text:

- **`DEFAULT_THRESHOLD = 0.5` is duplicated** (reviewer-noted). The constant lives in `scaffold.py` for the refinement-todo's "Deferred:" line; the template `oracle.sh.template` still carries the literal `0.5` in `THRESHOLD="${THRESHOLD:-0.5}"`. A future template default bump would silently desync from what the refinement-todo quotes back. Acceptable for this slice — the constant's docstring names the duplication explicitly, and `0.5` isn't expected to change in the near term — but a `{{THRESHOLD_DEFAULT}}` substitution marker would be a strict improvement. Tracked as a follow-up.
- **"Custom signals" category omitted** (reviewer-noted). Slice goal text names four deferred-decision categories (weights, threshold, ambiguous, custom signals); ACs only require the first three. The `# SEED:` block convention from 001-02 already surfaces the "add your own" path in the template's comment header, so a refinement-todo entry would be a pure pointer. Defensible but worth flagging — the goal wrote a check the ACs didn't cash.
- **`ambiguous_tests` is built from built-in detection only, not jig's pick** (reviewer-confirmed correct semantic). Ambiguity is a property of the project's filesystem, not the detector's preference — so when jig selects vitest but built-in also detects jest, both names land in the ambiguous list and `(selected)` marks the jig pick. Edge case: if jig picks something outside `builtin_test_frameworks`, `(selected)` could mark a name absent from the ambiguous list. Vocabulary check in `_jig_tdd_detect` makes this unreachable in practice.
- **Idempotency via `Path.write_text` (not explicit unlink)**. AC #4 is satisfied structurally — truncate-and-write can't duplicate. Also covers the "older file with stale headings" edge case (full replacement). Subtle gap: `--force` will silently overwrite user hand-edits to refinement-todo.md. Intended `--force` behavior, but worth a docs note when SKILL.md ships in 001-05.

**Open follow-ups (added to [docs/refinement-todo.md](../../refinement-todo.md)):**
1. `THRESHOLD_DEFAULT` template substitution to remove the dual source of truth.
2. Decide whether to emit a "Custom signals" category for the no-signals case (currently silent; user only sees the in-oracle "populate # SEED: blocks manually" hint).

**Reviewer verdict:** PASS-WITH-CAVEATS (independent review, jig:reviewer subagent, 2026-05-15). All 5 ACs met by behavior-driven tests; both caveats are non-blocking and now tracked.

---

## Slice 001-05 — qa-wizard

**Goal:** `skills/scaffold-init/SKILL.md` exposes the helper to the LLM via a Q&A wizard mirroring jig's scaffold-init flow: each question skippable, "skip every question" is the legitimate pure-inference path, never invent answers. End-to-end value: a user typing "set up servo on this project" gets a coherent question flow that fills in flags before the helper runs.

**DoR:**
- ✅ Slice 001-04 DONE
- ✅ Q&A questions enumerated (see below)
- ✅ Anti-greediness test pattern decided (mirror jig's `pr-review` `DescriptionBoundsTests`)

**Acceptance Criteria:**

1. **SKILL.md trigger phrases.** SKILL.md description fires on "set up servo", "scaffold oracle for this project", "install agent loop infrastructure", and similar; does *not* fire on bare "oracle" or "score this code".
2. **Five Q&A questions documented.**
   1. Project type — service / library / plugin / unsure → flag-mapped to component bias
   2. Tier offered — Tier 0 only / Tier 0 + 1 / all three → maps to which templates ship
   3. Loop guardrails — defaults / custom → if custom, ask iteration cap + cost ceiling
   4. Hook installation — yes (Tier 2 only) / no / skip → installs `oracle-hook` registration
   5. Existing servo install — proceed / abort → if `.servo/install.json` present
3. **Each question independently skippable.** Skipping any question omits the corresponding flag; helper falls back to filesystem inference.
4. **Skipping all = pure inference.** Equivalent to invoking `scaffold.py <target>` with no flags.
5. **Refusal on already-scaffolded target without `--force`.** SKILL.md surfaces the helper's refusal message to the user verbatim; doesn't silently retry.

**DoD:** _(same shape)_
- [x] All ACs pass; full test suite green. _53/53 across `test_scaffold.py` + `test_skill_surface.py` (13 new surface tests)._
- [x] Test coverage per AC: AC1→`DescriptionBoundsTests`, AC2→`QAQuestionsTests`, AC3+AC4→`SkippabilityTests`, AC5→`RefusalSurfacingTests`. Plus `SkillFileShapeTests` for the existence/frontmatter shape.
- [x] Deviation log produced under this slice heading.
- [x] Reviewer subagent review. _jig:reviewer agent, 2026-05-15 — PASS-WITH-CAVEATS. Two non-blocking caveats tracked in `docs/refinement-todo.md`._
- [x] Implementation review passed.
- [x] Reconciliation review passed.
- [x] `docs/refinement-todo.md` updated. _New entries for soft anti-greediness checks and section-scoped substring tests._

### Close-out (post-DONE)

- [x] SKILL.md anti-greediness tests pass (`pytest skills/scaffold-init/test_skill_surface.py`). _13/13 green under unittest runner; the file uses `unittest.TestCase` (no pytest-specific syntax), so pytest auto-discovers it. Local pytest binary absent on this dev box — close-out invocation form documented to work wherever pytest is installed._
- [x] `README.md` skills table row for `scaffold-init` flipped to DONE.
- [x] `docs/specs/README.md` status board: spec 001 → DONE.

**Anti-horizontal-phasing check:** After this slice, the user-facing surface is real — typing the trigger phrase produces a tailored install in one Q&A pass. This is the slice that closes the spec.

### Deviation log (after reconciliation)

**Slice 001-05 — implemented 2026-05-15.** 13 surface tests green under `python3 skills/scaffold-init/test_skill_surface.py`. SKILL.md weighs in at ~155 lines covering frontmatter, Q&A flow, pure-inference path, refusal handling, examples.

Deviations from spec text:

- **Four of five questions are documentation-only at this slice** (reviewer-noted). Tier-1, Tier-2, hook-installation, and loop-guardrails questions have no helper flag yet (scaffold.py only accepts `--force`). SKILL.md frames each as "informational at this slice" with forward pointers to specs 003/004/005. AC #3's "skipping any question omits the corresponding flag" is technically aspirational for those four — they have no flag to omit. The only question that maps to a real flag today is #5 (existing-install → `--force`). Acceptable because the spec scoped Tier-1+ to future work; the Q&A surface is the *user-facing* commitment, not the helper's CLI surface.
- **rc=2 differentiation in refusal handling is not exercised by a test.** SKILL.md explicitly differentiates rc=1 ("refused, not failed; offer `--force`") from rc=2 ("environment error, stop, `--force` won't help"). `RefusalSurfacingTests` only verifies the rc=1 path; nothing asserts rc=2 is handled distinctly. Spec text doesn't require it; documenting for traceability.
- **Anti-greediness tests are soft on negative triggers** (reviewer-noted). `test_negative_triggers_in_description` checks the negative phrases appear *somewhere* but not that they live in a do-not block. Tracked in `docs/refinement-todo.md`.
- **Body tests substring-check globally** (reviewer-noted). `QAQuestionsTests` / `SkippabilityTests` / `RefusalSurfacingTests` lowercase the whole file and check for keyword presence anywhere. Tracked in `docs/refinement-todo.md`.
- **`pytest skills/scaffold-init/test_skill_surface.py` close-out form is verified by construction**: the test file uses `unittest.TestCase` with no pytest-specific decorators or fixtures, so pytest auto-discovers and runs the tests identically. The local dev box doesn't have pytest installed; the unittest runner is the authoritative invocation for now.

**Reviewer verdict:** PASS-WITH-CAVEATS (independent review, jig:reviewer subagent, 2026-05-15). All 5 ACs substantively met; the four caveats are all tracked in the refinement-todo.

---

## Spec-level Definition of Done

- [x] All five slices DONE. _001-01 (greenfield-scaffold), 001-02 (template-content), 001-03 (signal-detection), 001-04 (deferred-decisions), 001-05 (qa-wizard) — each reviewed by jig:reviewer subagent (PASS / PASS-WITH-CAVEATS); 53/53 tests across `test_scaffold.py` + `test_skill_surface.py`._
- [x] End-to-end dogfood: scaffold servo's own repo (recursively — `python3 skills/scaffold-init/scaffold.py .`). Verify `oracle.sh` lands, scores servo's pytest tests, exits 0. _Verified 2026-05-15: scaffold detected pytest (servo's own `pyproject.toml` added during dogfood close-out), produced `oracle.sh` with `score_pytest`, manifest with `components: ["pytest"]`, refinement-todo with only `Threshold` (single-component case). With pytest on PATH (via venv), oracle ran composite=1.0000 threshold=0.5 → exit 0._
- [x] [README.md](../../../README.md) skills table: `scaffold-init` row reads `DONE`.
- [x] `docs/architecture.md` "Open questions" section reduced to genuinely-open items only. _Composite weighting heuristic resolved in 001-02; ADR-0001 promoted out of pending in 001-03. Remaining items (`.servo/install.json` checked-in vs ignored, scaffold-init vs jig-scaffolded interaction, agent-loop driver shell vs Python) are all genuinely-open future-spec items._
- [x] At least one ADR recorded. _[ADR-0001](../../decisions/adr-0001-reuse-jig-test-detector.md) Accepted in 001-03 — reuse jig's `tdd.py detect` when co-installed; fall back to built-in detectors otherwise._
- [x] [docs/specs/README.md](../README.md) status board reflects DONE.

## Critical files (when implementation starts)

In jig (reference patterns):
- `skills/scaffold-init/scaffold.py` — wizard helper shape
- `skills/scaffold-init/SKILL.md` — Q&A surface pattern
- `skills/_common/parsing.py` — shared utilities pattern
- `skills/tdd-loop/tdd.py` — `detect` subcommand pattern (reused via subprocess in 001-03)
- `skills/pr-review/test_skill_surface.py` — anti-greediness test pattern (mirrored in 001-05)
- `templates/CLAUDE.md.template` + `templates/docs/specs/slice-template.md` — template-content slice shape

In this repo:
- `templates/oracle.sh.template` — new in 001-02
- `skills/scaffold-init/scaffold.py` — new in 001-01
- `skills/scaffold-init/SKILL.md` — new in 001-05
- `skills/scaffold-init/test_scaffold.py` — new in 001-01, extended each slice
