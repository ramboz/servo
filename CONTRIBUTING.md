# Contributing to servo

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
   `.claude-plugin/plugin.json` `$.version`, updates `CHANGELOG.md`, and bumps
   `.github/.release-please-manifest.json` — all together.
3. **Merge the release PR.** That creates the git tag `vX.Y.Z` and a GitHub
   release.
4. On the created release, the `package` job builds + smoke-tests the release
   zip and uploads `servo-v<version>.zip` as a release asset.

**Do not hand-edit `.claude-plugin/plugin.json`'s version** — it is
release-managed. The local `python3 scripts/build_release_zip.py` recipe still
works for building/verifying a zip on your machine, but it is not how releases
are published.

## Before you open a PR

Run the same gates CI runs:

```bash
python3 -m pytest                              # full suite (or: uvx pytest)
uvx ruff check .                               # lint floor (ruff.toml)
bash scripts/verify_install_surfaces.sh        # install-surface gate
```
