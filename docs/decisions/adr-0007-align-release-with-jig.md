---
status: Accepted
date: 2026-06-11
deciders: ramboz
supersedes:
superseded-by:
---

# ADR-0007 — Adopt release-please + conventional-commit enforcement for servo releases (align with jig)

## Context

Servo releases are entirely manual: a maintainer hand-edits the version in
`.claude-plugin/plugin.json`, runs `python3 scripts/build_release_zip.py`
to build and smoke-test `dist/servo-v<version>.zip`, and stops there. There
are no git tags, no GitHub releases, no `CHANGELOG.md`, and no enforcement
that commit subjects are machine-readable. Slice 007-05 recorded this as a
conscious deferral, not an accident.

Jig — servo's sibling plugin, same install shape — has already worked
through the operational form of automated releases and runs it at
production scale (`v1.x`): a conventional-commit PR-title gate, release-please
for version/CHANGELOG/tag/release, and a package job that builds and uploads
the artifact. Servo already has the release *building blocks* (a single
version source in `plugin.json`, a deterministic smoke-tested builder, a
contract-driven verifier). What it lacks is the orchestration.

The choice of release mechanism is hard to reverse cheaply once a version
history, a changelog format, and a tag scheme exist and people depend on
them — so it warrants a recorded decision rather than an ad-hoc workflow
file. This ADR is implemented by spec 010.

## Decision

Adopt jig's release model, tailored to servo:

1. **Conventional-commit PR titles, enforced.** A `pr-title.yml` workflow
   runs `amannn/action-semantic-pull-request@v5` with the jig type set
   (`feat, fix, perf, docs, chore, refactor, test, build, ci`), required
   scope, and a lowercase / no-trailing-period subject rule.
2. **Squash-merge.** PRs squash-merge so the (validated) PR title becomes
   the `main` commit subject release-please reads.
3. **release-please owns the release.** A `release.yml` runs
   `googleapis/release-please-action@v4` on push to `main`; it bumps
   `.claude-plugin/plugin.json` `$.version` via `extra-files`, generates
   `CHANGELOG.md`, and on release-PR merge creates tag `vX.Y.Z`
   (`include-v-in-tag: true`, `release-type: simple`) and a GitHub release.
4. **Artifact on release.** A `package` job builds the zip with servo's
   existing `build_release_zip.py` (which auto-derives the version and
   smoke-tests), then uploads `servo-v<version>.zip` as a release asset.
5. **0.x semantics for now.** Servo stays pre-1.0: a `feat` bumps the minor,
   a `fix`/`perf` the patch. No `release-as: 1.0.0` pin; the 1.0 cutover is
   a separate future decision.
6. **No runtime dependency on jig.** Servo's own scripts do the building
   and verifying. Jig is the reference *pattern*, not a dependency — the
   sibling framing from ADR-0001 holds.

## Consequences

**Positive.**

- Releases become automated, traceable, and changelog-backed; the version
  can no longer drift from the tag or the artifact.
- Servo and jig release the same way, so maintainer knowledge transfers and
  the two `.github/` surfaces read alike.
- The package job reuses servo's already-tested deterministic builder and
  smoke test — the asset is verified before it is published.

**Negative.**

- Contributors must write conventional-commit PR titles, and the repo must
  use squash-merge. This is new discipline (mitigated: the `pr-title.yml`
  gate makes it self-correcting).
- release-please has its own mental model (release PRs, the manifest file)
  that a maintainer must learn.

**Neutral.**

- The decision binds servo to release-please and the
  `amannn/action-semantic-pull-request` action. Replacing either later is
  possible but is itself a release-mechanism change.
- Real branch-protection (requiring the PR-title check, restricting direct
  pushes to `main`) is server-side and out of band — the workflows enforce
  shape, not merge policy.

## Alternatives considered

- **Keep the manual recipe (status quo).** Rejected: no changelog, no tags,
  no published artifact, and version edits are error-prone — exactly the
  gap this ADR closes.
- **semantic-release.** Rejected: heavier Node-centric toolchain and
  plugin surface than this single-package plugin needs; release-please is
  lighter here and gives servo↔jig parity for free.
- **A custom version-bump / changelog script.** Rejected: reinvents
  release-please and diverges from jig with no upside.
- **Convert servo to JSON-less, jig-style hardcoded release lists.**
  Rejected: servo's data-driven `install-contract.json` is the better
  pattern (it is the *source* of the separate servo→jig alignment item);
  this ADR keeps it.

## Verification

- Spec 010's slices and their acceptance criteria implement clauses 1–4;
  the `pr-title.yml` / `release.yml` / `release-please-config.json` /
  `.release-please-manifest.json` artifacts are the concrete evidence.
- The model mirrors jig's `.github/workflows/{pr-title,release}.yml`, which
  is proven across jig's `v1.x` release history.

## References

- [Spec 010 — release-automation](../specs/010-release-automation/spec.md).
- [Spec 007 — install-surfaces](../specs/007-install-surfaces/spec.md) —
  the builder / verifier / contract this release flow drives, and 007-05's
  deferral of release automation.
- [ADR-0001 — reuse jig's test detector](adr-0001-reuse-jig-test-detector.md)
  — the "sibling, not dependency" framing this ADR inherits.
- Jig's `.github/workflows/release.yml`, `pr-title.yml`, and
  `release-please-config.json` — the reference implementation.
