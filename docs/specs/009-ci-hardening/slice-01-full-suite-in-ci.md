---
status: DRAFT
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

- Spec 007 DONE (install-surface CI + `verify_install_surfaces.sh` exist).
- The full suite is green locally (`pytest` / `uvx pytest` from the repo
  root).
- Decision recorded: extend `verify.yml` vs add a new `ci.yml`.
  _(Recommended: a single `ci.yml` with a `test` job (matrix) plus the
  install-surface job, mirroring jig; fold `verify.yml` in or retire it.)_
- Decision recorded: the Python matrix + declared floor.
  _(Recommended: `["3.11", "3.12"]` for jig parity.)_

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

- [ ] All ACs pass; CI green across the matrix.
- [ ] Canary check: a deliberately failing skill test (e.g. under
      `skills/agent-loop/`) is shown to redden CI, then reverted — evidence
      (run link or log excerpt) in the deviation log. Proves the suite is
      really running, not silently skipped.
- [ ] Install-surface gate confirmed still running in the same workflow.
- [ ] Deviation log produced under this slice.
- [ ] Independent review pass completed before DONE.

**Anti-horizontal-phasing check:** After this slice, servo's product logic
cannot regress silently — every skill test runs in CI, not just on a
developer's Mac.
