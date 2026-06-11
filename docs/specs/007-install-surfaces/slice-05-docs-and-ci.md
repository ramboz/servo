---
status: DONE
dependencies: []
last_verified:
---

## Slice 007-05 — docs-and-ci

**Goal:** Document the install surfaces and run install-contract checks
as part of normal repo verification. End-to-end value: contributors can
change servo artifacts without accidentally breaking plugin install,
release zip install, or project-local scaffold install.

**DoR:**

- 007-01 through 007-04 DONE.
- Repo verification command(s) are known.
- Decision made whether this repo should add GitHub Actions now or only
  a local verification script.

**Acceptance Criteria:**

1. **README install section.** README explains plugin install, release
   zip install, and project-local scaffold mode, including when to
   choose each.
2. **Spec/docs status updated.** `docs/product-vision.md`,
   `docs/architecture.md`, and `docs/specs/README.md` describe install
   surfaces using the two-layer distinction: servo runtime install vs
   project oracle install.
3. **One verification command.** A single documented local command runs
   plugin verifier tests, zip builder tests, and scaffold verifier
   tests.
4. **Automation wired.** CI, if present or added in this slice, runs the
   install verification command on PR and push. If CI is deferred, the
   deferral is recorded with a resolution trigger.
5. **Release recipe.** Docs include the manual release recipe for
   building and verifying the zip. If release-please or GitHub release
   asset automation is added, tests/docs cover its expected artifact
   name.

**DoD:**

- [x] Docs reviewed for stale path examples. _Automated by
  `scripts/test_docs_install.py` (9 tests): asserts every install-section
  script path exists on disk, the three runtime surfaces + release recipe +
  two-layer distinction are documented, and the README zip example matches the
  real default builder output name (`dist/servo-v0.1.0.zip`)._
- [x] Local verification command passes. _`bash
  scripts/verify_install_surfaces.sh` exits 0 (102 install-surface tests +
  live `verify_install.py plugin .`)._
- [x] CI decision recorded if automation is not added. _CI was **ADDED** (not
  deferred): `.github/workflows/verify.yml` runs the verification command on
  push and pull request. Recorded in the deviation log below._
- [x] Deviation log produced under this slice.
- [x] Independent review pass completed before DONE. _Independent reviewer
  (general-purpose subagent), 2026-06-01 — **PASS**. All 5 ACs independently
  verified: reviewer ran all 8 documented install commands verbatim (exit 0),
  confirmed the release artifact name matches the real builder output, the
  two-layer distinction is stated across README + product-vision + architecture
  + specs/README, the CI workflow is valid and Docker-free, and the docs
  stale-path guard is substantive. No design-principle violations. One cosmetic
  README prose fix applied (docs-guard added to the "verifying all surfaces"
  enumeration)._

**Anti-horizontal-phasing check:** After this slice, install reliability
is part of servo's ordinary development loop, not an oral tradition.

**Deviation log (after reconciliation):**

- **CI was ADDED, not deferred (AC4).** Per the maintainer decision,
  `.github/workflows/verify.yml` runs on `push` and `pull_request`,
  checks out, sets up Python 3.12, `pip install pytest`, then runs `bash
  scripts/verify_install_surfaces.sh`. ubuntu-latest ships `shellcheck`
  preinstalled, so the oracle shellcheck test (which skips locally on machines
  without it / with Docker down) actually runs in CI. The workflow assumes no
  Docker. The `on:` key is quoted (`"on":`) to dodge the YAML 1.1
  truthy-`on` coercion; verified the parsed mapping still carries `push` /
  `pull_request`.
- **Verification command runs pytest via a CI-vs-local fallback (AC3).**
  `scripts/verify_install_surfaces.sh` prefers `python3 -m pytest` (works in
  CI where pytest is installed) and falls back to `uvx pytest` when the
  module is not importable (the local dev case). It does **not** hard-code
  `uvx` as the only path. The script resolves the repo root from
  `BASH_SOURCE` so it runs from any cwd, and `set -euo pipefail` makes it
  fail on the first failing step.
- **Docs guard added to the verification command.** Beyond AC3's three named
  suites (`test_verify_install.py`, `test_build_release_zip.py`,
  `test_scaffold_runtime.py`), the wrapper also runs the new
  `scripts/test_docs_install.py` so the stale-path guard runs in CI rather
  than only under a full `pytest` sweep. Additive to AC3's explicit list.
- **README install section structure (AC1/AC5).** Added `## Installing servo`
  with an explicit two-layer preamble (servo runtime install vs project oracle
  install), a chooser table, one `###` subsection per runtime surface (plugin
  / release zip / project-local scaffold), a `### Release recipe`, and a
  `### Verifying all surfaces at once`. The release recipe states the produced
  artifact as `dist/servo-v<version>.zip` (read from
  `build_release_zip.py`'s default output: `dist/servo-v{plugin_version}.zip`),
  not an invented name. The project-oracle-install distinction links to the
  existing `## The scaffolded oracle.sh` section.
- **No release-please / asset automation (AC5).** Only the manual recipe is
  documented, which AC5 explicitly permits. No GitHub release-asset upload was
  added; the zip is a local build artifact and `dist/` stays git-ignored.
  **→ SUPERSEDED by spec 010 (release-automation), 2026-06-11:** release-please
  now owns versioning/CHANGELOG/tags/releases and a `package` job uploads
  `servo-v<version>.zip` as a release asset; the README's manual recipe was
  reframed to the local/fallback path. See
  [spec 010](../010-release-automation/spec.md) and
  [ADR-0007](../../decisions/adr-0007-align-release-with-jig.md).
- **Docs status updates kept additive (AC2).** `docs/architecture.md` gains an
  `## Install surfaces` section with the two-layer table pointing at the
  contract + verifier; `docs/product-vision.md` gains a "Two install layers,
  named explicitly" design principle; `docs/specs/README.md`'s
  install-surface-drift gap note now names the two-layer distinction and the
  CI command. No doc duplicates the full contract table.
- **Did not run `workflow.py transition`.** Per slice instructions, the
  orchestrator owns DONE + the spec-close-out board compression; this slice
  only ticked its DoD boxes (except the review box) and left the status board
  row at IN_PROGRESS.

Verification:

- `bash scripts/verify_install_surfaces.sh` -> exit 0 (102 install-surface
  tests pass + live `verify_install.py plugin .` PASS).
- `uvx pytest -q` (full suite from repo root) -> 427 passed, 1 skipped
  (the skip is the oracle shellcheck test; Docker daemon down locally — it
  runs in CI on ubuntu).
- Documented README commands smoke-run clean: `build_release_zip.py` ->
  `dist/servo-v0.1.0.zip` (21 entries); `verify_install.py zip
  dist/servo-v0.1.0.zip` -> PASS; `scaffold_runtime.py <tmp>` +
  `verify_install.py scaffold <tmp>` -> PASS.
- `.github/workflows/verify.yml` parses as valid YAML with `on: {push,
  pull_request}`, `runs-on: ubuntu-latest`, and the verification command as
  the final step.
