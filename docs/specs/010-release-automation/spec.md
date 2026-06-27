---
status: DONE
dependencies: [007, 009]
last_verified:
---

# Spec 010 - release-automation

> Replace servo's manual release ritual with the automated pipeline jig
> already proved: conventional-commit PR titles → release-please (version
> bump, CHANGELOG, tag, GitHub release) → a built, smoke-tested release zip
> uploaded as a release asset. Servo's `build_release_zip.py` is already
> release-ready; this spec adds the orchestration around it.

## Why this spec

Releasing servo today is entirely manual: hand-edit the version in
`.claude-plugin/plugin.json`, run `python3 scripts/build_release_zip.py`
(which builds and smoke-tests `dist/servo-v<version>.zip` locally), and
stop there. There are no git tags, no GitHub releases, no `CHANGELOG.md`,
and no enforcement that commit subjects are machine-readable. Slice 007-05
recorded this deliberately in its deviation log: *"No release-please /
asset automation (AC5). Only the manual recipe is documented."*

Jig has the whole pipeline working: a `pr-title.yml` conventional-commit
gate, a `release.yml` (release-please job + package job), a
`release-please-config.json`, a `.release-please-manifest.json`, and an
auto-generated `CHANGELOG.md`. Servo is a sibling plugin with the same
shape — `plugin.json` as the version source, a deterministic
smoke-tested builder, a contract-driven verifier. The release *building
blocks already exist*; only the orchestration is missing.

## Current gap

Today:

- Version is bumped by hand-editing `.claude-plugin/plugin.json`.
- `build_release_zip.py` builds + smoke-tests the zip; nothing uploads it.
- No git tags, no GitHub releases, no `CHANGELOG.md`.
- No conventional-commit / PR-title enforcement (the convention is followed
  by hand, and unevenly).

For reference, jig's release surface: `pr-title.yml`, `release.yml`
(`release-please` + `package` jobs), `release-please-config.json`,
`.release-please-manifest.json`, auto `CHANGELOG.md`.

## Goals

1. **Enforce conventional-commit PR titles** — the precondition for
   release-please reading `main`'s history.
2. **Adopt release-please** — automated version bump (`plugin.json` via
   `extra-files`), `CHANGELOG.md` generation, git tag `vX.Y.Z`, and a
   GitHub release.
3. **Ship the artifact on release** — build + smoke-test + upload the zip
   as a release asset.
4. **Document the flow** — a `CONTRIBUTING.md` covering squash-merge +
   conventional commits + the release sequence; reconcile 007-05's
   manual-recipe note.
5. **Stay independently releasable** — no runtime dependency on jig; servo's
   own scripts do the building (sibling framing, ADR-0001 / ADR-0007).

## Non-goals

- **No public marketplace submission** (same non-goal as spec 007).
- **No change to the zip artifact shape or install contract** — spec 007
  owns `build_release_zip.py` and `install-contract.json`.
- **No monorepo / multi-package release config** — `release-type: simple`,
  a single package at the repo root.
- **No artifact signing or notarization.**
- **No 1.0 cutover decision.** Servo stays `0.x`; this spec operates under
  `0.x` semantics (a `feat` bumps the minor, a `fix` the patch). The 1.0
  decision is deferred and out of scope.

## Decision record

This spec implements
[ADR-0007 — align release with jig](../../decisions/adr-0007-align-release-with-jig.md)
(adopt release-please + conventional-commit enforcement + squash-merge).

## Core model

Two halves, mirroring jig:

1. **Decide the release** (release-please): commit history on `main` →
   version bump + `CHANGELOG.md` + tag + GitHub release, via a release PR.
2. **Ship the artifact** (package job): on a *created* release, build the
   smoke-tested zip and upload it as an asset.

Both depend on commit subjects on `main` being release-please-readable,
which the conventional-commit PR-title gate guarantees — combined with
**squash-merge**, so the PR title becomes the `main` commit subject.

## Slices

- [010-01 — conventional-commit-gate](slice-01-conventional-commit-gate.md)
- [010-02 — release-please-pipeline](slice-02-release-please-pipeline.md)
- [010-03 — release-asset-on-tag](slice-03-release-asset-on-tag.md)
- [010-04 — contributing-and-docs](slice-04-contributing-and-docs.md)
