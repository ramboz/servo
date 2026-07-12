# Contributing to servo

## Local plugin install

Regenerate the committed host packages before installing a checkout:

```bash
python3 scripts/build_host_packages.py
```

Start Claude Code against the generated local package:

```bash
claude --plugin-dir "$(pwd)/hosts/claude"
```

The repository's root Claude marketplace descriptor is intentionally the
remote-install pointer; it is not the local development loader.

For Codex, add this repository as a local marketplace using its absolute path:

```bash
codex plugin marketplace add "$(pwd)"
codex plugin add servo@servo
```

Start a fresh session after installing or refreshing either plugin. Generated
files under `hosts/` are install payloads; edit canonical source and regenerate
them rather than patching them directly.

## Merging: squash + conventional-commit PR titles

Servo uses **squash-merge** as its only merge mode, and the squash commit
subject is taken from the **PR title**. release-please reads those subjects on
`main` to decide the next version and build the changelog — so the PR title is
load-bearing, and a [`pr-title.yml`](.github/workflows/pr-title.yml) check
validates it on every PR.

A PR title must be a [Conventional Commit](https://www.conventionalcommits.org/):

```
<type>(<scope>): <subject>
```

- **type** — one of: `feat`, `fix`, `perf`, `docs`, `chore`, `refactor`,
  `test`, `build`, `ci`.
- **scope** — **required** (e.g. `agent-loop`, `quality-gate`, `release`,
  `specs`).
- **subject** — must start lowercase and **not** end with a period.

Examples: `feat(agent-loop): add resume guard` ✓ ·
`fix(quality-gate): correct exit code on timeout` ✓ ·
`Update stuff.` ✗ (no type/scope, capitalized, trailing period).

## How a PR title becomes a release

Servo is pre-1.0, so it follows `0.x` semantics (a `feat` bumps the **minor**,
not the major):

| PR title type | Example | Version effect (`0.x`) |
|---|---|---|
| `feat` | `feat(agent-loop): …` | minor bump (`0.1.0 → 0.2.0`) |
| `fix` / `perf` | `fix(quality-gate): …` | patch bump (`0.1.0 → 0.1.1`) |
| `feat!` or a `BREAKING CHANGE:` footer | `feat(gate)!: …` | major bump (still pre-1.0 caveats apply) |
| `docs` / `chore` / `refactor` / `test` / `ci` / `build` | `ci(release): …` | **no release** (changelog-hidden) |

## The release flow (automated)

Releases are handled by [release-please](.github/workflows/release.yml) — no
hand-edited versions:

1. Merge your PRs to `main` as usual (squash, conventional title).
2. release-please opens/maintains a **release PR** that bumps
   both root plugin manifests, both committed host-package manifests,
   `CHANGELOG.md`, and `.github/.release-please-manifest.json` together.
3. **Merge the release PR.** That creates the git tag `vX.Y.Z` and a GitHub
   release.
4. On the created release, the `package` job builds + smoke-tests
   `servo-claude-v<version>.zip` and `servo-codex-v<version>.zip`, then uploads
   both. A deprecated `servo-v<version>.zip` Claude alias remains for one
   compatibility release.

**Do not hand-edit plugin-manifest versions**—release-please owns all four.
Host packages are generated artifacts: edit canonical root source, run
`python3 scripts/build_host_packages.py`, and commit the regenerated `hosts/`
tree. Never patch `hosts/` by hand.

Local release verification:

```bash
python3 scripts/build_host_packages.py --check
python3 scripts/build_release_zip.py --host claude --version <version>
python3 scripts/build_release_zip.py --host codex --version <version>
```

## Before you open a PR

Run the same gates CI runs, in the same order:

```bash
python3 scripts/ci_check.py
```

The individual commands remain available for focused work:

```bash
python3 scripts/run_tests.py
bash scripts/verify_install_surfaces.sh
python3 scripts/validate_manifests.py
python3 scripts/build_host_packages.py --check
```
