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
