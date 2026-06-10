---
status: DONE
dependencies: []
last_verified:
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

