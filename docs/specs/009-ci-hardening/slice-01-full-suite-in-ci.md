---
status: IN_PROGRESS
dependencies: []
last_verified:
---

## Slice 009-01 — full-suite-in-ci

**Goal:** CI runs servo's complete pytest suite across a declared Python
matrix, so the skill logic (loop, gate, oracle, scaffold) is gated on every
push and PR — not just the install-surface plumbing. End-to-end value: a
regression in any skill reddens CI instead of waiting to surface on a
developer's machine.

**DoR:**

- Spec 007 DONE (install-surface CI + `verify_install_surfaces.sh` exist). ✓
- The full suite is green locally (`pytest` / `uvx pytest` from the repo
  root). ✓ — `uvx pytest` from root: **705 passed, 1 skipped, 13 subtests**
  (2026-06-11); the 1 skip is the pre-existing oracle shellcheck test
  (Docker daemon down locally — runs in CI on ubuntu).
- Decision recorded: extend `verify.yml` vs add a new `ci.yml`.
  _(Recommended: a single `ci.yml` with a `test` job (matrix) plus the
  install-surface job, mirroring jig; fold `verify.yml` in or retire it.)_
  → **DECIDED: new `ci.yml`, `verify.yml` retired.** Single
  `.github/workflows/ci.yml` with a `test` job (matrix) + an
  `install-surfaces` job (runs `verify_install_surfaces.sh` unchanged);
  the old `verify.yml` is deleted. Mirrors jig's `ci.yml` shape (Goal 5).
- Decision recorded: the Python matrix + declared floor.
  _(Recommended: `["3.11", "3.12"]` for jig parity.)_
  → **DECIDED: matrix `["3.11", "3.12"]`, floor `requires-python = ">=3.11"`.**
  Verified locally: full suite green on **both** 3.11 and 3.12 (2026-06-11)
  before declaring the floor.
- AC6 canonical command: **DECIDED: bare `python3 -m pytest` from the repo
  root** (not a `scripts/run_tests.py`). Servo is already pytest-native —
  `pyproject.toml`'s `testpaths = ["skills", "scripts"]` makes a bare
  `pytest` run the whole suite — so CI runs the identical command devs run
  locally (`python3 -m pytest`, or `uvx pytest` when pytest isn't on the
  active interpreter). A jig-style unittest `run_tests.py` would be a step
  backward for a pytest project.

**Acceptance Criteria:**

1. **Full suite runs in CI.** CI invokes the complete test suite over
   `skills/` and `scripts/` (today's `pyproject.toml` `testpaths`), not a
   hand-listed file subset. The skill suites (`agent-loop`, `quality-gate`,
   `oracle-hook`, `spec-oracle`) demonstrably execute.
2. **Python matrix.** The suite runs once per version of an explicit matrix
   (recommended `["3.11", "3.12"]`) with `fail-fast: false`.
3. **Declared floor.** `pyproject.toml` declares `requires-python` matching
   the matrix floor.
4. **Install-surface gate preserved.** `verify_install_surfaces.sh` (or its
   steps) still runs in CI as a distinct check; the existing install-surface
   coverage is not dropped or weakened.
5. **Triggers.** CI runs on `push` and `pull_request`.
6. **One canonical local command.** A single documented local command runs
   the same full suite CI runs (bare `python3 -m pytest` from root, or a
   `scripts/run_tests.py` entrypoint à la jig — implementer's call,
   recorded).

**DoD:**

- [~] All ACs pass; CI green across the matrix. _ACs 1–6 met in-artifact (see
      AC-compliance in the deviation log); the full suite is green **locally**
      on both matrix Pythons (705 passed, 1 skipped, 13 subtests — 3.11 and
      3.12). **CI-green-on-the-runner pending the push** (remote Actions run)._
- [ ] Canary check: a deliberately failing skill test (e.g. under
      `skills/agent-loop/`) is shown to redden CI, then reverted — evidence
      (run link or log excerpt) in the deviation log. Proves the suite is
      really running, not silently skipped. _Pending push (needs a remote
      Actions run)._
- [x] Install-surface gate confirmed still running in the same workflow.
      _`.github/workflows/ci.yml` has a distinct `install-surfaces` job whose
      final step runs `bash scripts/verify_install_surfaces.sh`; gate re-run
      locally → exit 0._
- [x] Deviation log produced under this slice. _Below._
- [x] Independent review pass completed before DONE. _Independent reviewer
      subagent (no access to this conversation), 2026-06-11 — **PASS, no
      blockers.** Independently re-ran `ruff check .` (clean), `bash
      scripts/verify_install_surfaces.sh` (102 passed, exit 0), and a 252-test
      targeted pytest over the most-edited files (all pass); verified all six
      009-01 ACs met (cited file:line) and `on:` is not boolean-coerced. Two
      non-blocking nits, consciously left out of scope (neither is a ruff
      finding): a pre-existing redundant function-local `import re` in
      `test_scaffold.py`, and a cosmetic ci.yml comment._

**Anti-horizontal-phasing check:** After this slice, servo's product logic
cannot regress silently — every skill test runs in CI, not just on a
developer's Mac.

**Deviation log:**

- **AC compliance.** (1) Full suite — `ci.yml`'s `test` job runs
  `python3 -m pytest` from the repo root, which honours `pyproject`'s
  `testpaths = ["skills", "scripts"]`; the loop/gate/oracle/scaffold/spec-oracle
  suites all collect (705 tests). Not a hand-listed subset. (2) Matrix
  `["3.11", "3.12"]`, `fail-fast: false`. (3) `pyproject.toml` declares
  `requires-python = ">=3.11"`. (4) Install-surface gate preserved as a
  distinct `install-surfaces` job. (5) Triggers `push` + `pull_request`.
  (6) Canonical command `python3 -m pytest` (CI and local identical).
- **New `ci.yml`; `verify.yml` deleted (decision).** A single
  `.github/workflows/ci.yml` carries two jobs — `test` (matrix) and
  `install-surfaces` — mirroring jig's `ci.yml` shape (spec Goal 5). The
  slice-007-05 `verify.yml` (install-surfaces only) is removed, not kept
  alongside, to avoid a redundant second workflow. Jig-specific steps
  (`fetch-depth: 0`, the "ensure local main" step that jig needs for
  `slice-land`'s `land.py`) were **omitted** — no servo test needs a `main`
  ref or full history (suite verified green in this detached worktree branch).
- **`on:` is quoted.** Kept the slice-007-05 convention of `"on":` to dodge
  the YAML-1.1 truthy-`on` coercion; parsed back with PyYAML → real string key
  `on` carrying `{push, pull_request}` (not the boolean `True`).
- **Test-content touch, forced by retiring `verify.yml` (deviation from the
  spec non-goal).** Spec 009's non-goal says "No change to test content," but
  the *permitted* decision to retire `verify.yml` collides with
  `scripts/test_docs_install.py::CiWorkflowTests`, which bound the workflow
  path to `verify.yml` by name (a slice-007-05 docs-stale-path guard). The
  guard's `WORKFLOW` constant + assertion message were retargeted
  `verify.yml` → `ci.yml`. **What the test asserts is unchanged** — the
  install-surface command (`bash scripts/verify_install_surfaces.sh`) plus
  `push`/`pull_request` triggers are present in the workflow; only the
  filename it inspects moved. This was caught by the test itself reddening
  mid-implementation (good — the guard worked). The stale `verify.yml`
  reference in `scripts/verify_install_surfaces.sh`'s header comment was also
  updated to name `ci.yml`'s install-surfaces job. Historical `verify.yml`
  mentions in *prior* slice deviation logs (007-05) and in 009's own
  problem-statement prose were left as-is (accurate as history).
- **`requires-python` placement avoids a second version source.** servo is a
  Claude Code plugin, not a pip package, and its canonical version lives in
  `.claude-plugin/plugin.json` (`0.1.0`). A `[project]` table was added with
  `name = "servo"`, `requires-python = ">=3.11"`, and `dynamic = ["version"]`
  — deliberately **no** hardcoded `version`, so no duplicate source. There is
  no `[build-system]`, so nothing tries to build it. Verified: `tomllib`
  parses it; `uvx pytest` still runs (uvx is isolated, never builds the local
  project); the CI path (`pip install pytest` → `python3 -m pytest`) ignores
  `[project]` entirely.
- **CI-green + canary DEFERRED to the push.** Two DoD items —
  "CI green across the matrix" and the canary (a deliberately-failing skill
  test reddens CI, then reverted) — require a remote GitHub Actions run and
  cannot be satisfied from the working tree. They will be completed once the
  branch is pushed and a run link captured here. Local equivalents are green
  (see Verification).
- **No commit/transition yet.** Per servo convention (and pending a push
  decision), the slice frontmatter is left at `IN_PROGRESS`; status will move
  to DONE only after the review pass and the remote CI evidence land.

Verification (local):

- `uvx --python 3.11 pytest -q` → **705 passed, 1 skipped, 13 subtests** (2:25).
- `uvx --python 3.12 pytest -q` → **705 passed, 1 skipped, 13 subtests** (2:25).
  Identical to the pre-change baseline — no behavior drift. The 1 skip is the
  oracle shellcheck test (Docker daemon down locally; it runs in CI on ubuntu).
- `bash scripts/verify_install_surfaces.sh` → exit 0 (distinct install-surface
  gate, including the live `verify_install.py plugin .`).
- `ci.yml` parsed with PyYAML: jobs `{test, install-surfaces}`; matrix
  `["3.11","3.12"]`; `fail-fast: false`; `on` carries `{push, pull_request}`.
