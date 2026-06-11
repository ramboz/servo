---
status: IN_PROGRESS
dependencies: [007]
last_verified:
---

# Spec 009 - ci-hardening

> Make servo's CI actually exercise servo. Today CI proves the install
> *plumbing* but never runs the skill logic that is the product. This spec
> runs the full test suite across a declared Python matrix and adds a lint
> floor, aligning servo's CI gates with jig's.

## Why this spec

Servo's only workflow, `.github/workflows/verify.yml`, runs
`scripts/verify_install_surfaces.sh`. That script runs the plugin verifier
plus pytest over exactly four files — `test_verify_install.py`,
`test_build_release_zip.py`, `test_scaffold_runtime.py`,
`test_docs_install.py`. Those prove the three install surfaces stay
coherent. They do **not** run the skill suites that are servo's actual
product: `agent-loop/test_loop.py`, `quality-gate/test_gate.py`,
`oracle-hook/test_hook.py`, `spec-oracle/test_checks.py`, and the rest
(13 skill test files in total).

`pyproject.toml` already scopes pytest with `testpaths = ["skills",
"scripts"]`, so a bare `pytest` from the repo root runs everything — which
is how the suite is run locally. CI just never invokes it that way. The
practical consequence already bit us once: a not-green suite surfaced on a
developer's Mac rather than in CI, because CI was not running the skill
tests at all.

Jig long ago closed this: its `ci.yml` runs the whole suite
(`run_tests.py`) on a `3.11` + `3.12` matrix, then spec-lint, manifest
validation, and a ruff code-health floor. Servo runs a strict subset on a
single Python with no Python linter.

## Current gap

Running in CI today (`verify.yml` → `verify_install_surfaces.sh`):

- `verify_install.py plugin .`
- pytest over four install-surface files only.

Not running in CI:

- The skill suites — the loop / gate / oracle / scaffold logic that is the
  product (13 test files under `skills/`).
- Any Python other than 3.12 (servo declares no supported floor anywhere).
- Any Python linter. Only `shellcheck` runs, and only because it rides
  along inside the install-surface tests.

## Goals

1. **Run the complete suite in CI.** CI runs every test under `skills/`
   and `scripts/` (the existing `testpaths`), not the install-surface
   subset.
2. **Declare a Python floor and test a matrix.** Establish servo's
   supported Python versions and run the suite across them (recommended:
   `3.11` + `3.12`, for jig parity), and record the floor in
   `pyproject.toml` (`requires-python`).
3. **Add a ruff lint floor.** Introduce a ruff config mirroring jig and a
   CI lint step, and bring the tree to green.
4. **Keep install-surface verification.** `verify_install_surfaces.sh`
   stays a distinct, still-running gate — full-suite coverage is added
   *alongside* it, not in place of it.
5. **Align the workflow shape with jig.** Land on a `ci.yml` with a `test`
   job (matrix) + a lint step, plus the install-surfaces check — so the two
   projects' CI read the same way.

## Non-goals

- **No release automation.** Versioning, CHANGELOG, tags, and GitHub
  releases are spec 010.
- **No type-checker.** mypy / pyright are out of scope; a possible later
  spec, not this one.
- **No change to test content.** This spec changes what CI *runs*, not what
  the tests assert. No new or rewritten tests beyond a throwaway canary to
  prove the suite runs.
- **No coverage-threshold gate.**
- **No new test framework.** pytest stays.

## Core model

Servo has two orthogonal questions CI must answer on every push and PR:

| Question | Gate today | Gate after this spec |
|---|---|---|
| **Does servo work?** (loop / gate / oracle / scaffold logic) | *not run in CI* | full pytest suite across the Python matrix + ruff floor |
| **Does servo install?** (plugin / release-zip / scaffold surfaces) | `verify_install_surfaces.sh` | unchanged — still runs as its own gate |

Both must be green to merge. Today only the second runs.

## Slices

- [009-01 — full-suite-in-ci](slice-01-full-suite-in-ci.md)
- [009-02 — ruff-lint-floor](slice-02-ruff-lint-floor.md)
