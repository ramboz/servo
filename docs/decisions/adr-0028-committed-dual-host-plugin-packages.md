---
status: Accepted
date: 2026-07-12
deciders: ramboz
supersedes:
superseded-by:
frame_review: true
last_verified: 2026-07-12
---

# ADR-0028: Commit generated Claude and Codex plugin packages

## Status

Accepted (2026-07-12)

## Context

Servo's canonical repository is also its Claude install payload, while its
release pipeline publishes one Claude-shaped archive and has no Codex plugin
manifest or native Codex marketplace bundle. This matched Jig's older delivery
shape, but no longer matches Jig's current dual-host mechanism. Installing the
repository root also exposes development-only files as plugin content and makes
it impossible to prove that Claude and Codex receive coherent, runtime-only
packages from the same source.

The host packages must support release-please versioning, deterministic release
archives, local verification, and CI without introducing a runtime dependency on
Jig. Several Servo behaviors are genuinely Claude-specific (`claude -p`,
`/goal`, and Claude `Stop` hooks); a Codex package must preserve those explicit
contracts rather than mechanically renaming them.

## Decision

Keep the repository root as canonical source and commit two generated peers:

- `hosts/claude/` is a flat, runtime-only Claude plugin. The root Claude
  marketplace descriptor points to this directory.
- `hosts/codex/` is a Codex marketplace bundle with the Servo plugin nested at
  `plugins/servo/` and a local marketplace descriptor at
  `.agents/plugins/marketplace.json`. A second, thin descriptor at the
  repository root points at `./hosts/codex/plugins/servo`, enabling remote
  `codex plugin marketplace add ramboz/servo` without a clone/build step.

One deterministic builder regenerates both packages. CI rebuilds into scratch
space and fails when committed packages drift. Generated host packages are never
hand-edited.

Codex rendering rewrites plugin-root references from
`${CLAUDE_PLUGIN_ROOT}` to `${PLUGIN_ROOT}` in staged skill documentation, but
does not rename actual Claude runtime requirements. Release-please updates the
root Claude/Codex manifests and their committed host-package copies together.
Each release publishes two host-explicit archives:
`servo-claude-vX.Y.Z.zip` and `servo-codex-vX.Y.Z.zip`. The former is a flat
plugin; the latter is an extract-then-add marketplace bundle because Codex has
no direct zip-drop install. The old `servo-vX.Y.Z.zip` remains a deprecated
Claude alias for one compatibility release.

## Consequences

### Positive

- Claude and Codex become first-class, independently verifiable install
  surfaces built from one source tree.
- Remote/plugin installs contain runtime files rather than the development
  repository.
- CI catches source/package drift before release, and release assets state
  their host semantics in the filename.

### Negative

- Runtime files are duplicated under `hosts/`, increasing repository size and
  requiring regeneration after source edits.
- Release-please must keep four manifest versions synchronized.

### Neutral

- Claude project-local scaffolding remains supported; this decision does not
  invent a Codex project-local scaffold.
- Host packaging does not make Claude-specific execution primitives portable.

## Alternatives considered

- **Continue publishing one host-neutral archive.** Rejected because the
  archive is not host-neutral in shape or runtime semantics.
- **Generate host packages only in `dist/`.** Rejected because native
  marketplace installs from a checkout need a committed payload and because a
  CI-only artifact cannot be inspected in ordinary code review.
- **Hand-maintain two source trees.** Rejected because host copies would drift
  and fixes would need to be applied twice.
- **Mechanically replace every Claude reference with Codex.** Rejected because
  it would misdocument real subprocess and hook contracts.

## Verification

- Builder tests cover deterministic generation, runtime-only filtering,
  Codex plugin-root rendering, and drift detection.
- Release tests cover both archive shapes, version mismatches, and host-specific
  smoke validation.
- CI runs manifest coherence and host-package drift checks.

## References

- [Spec 022 — dual-host release parity](../specs/022-dual-host-release-parity/spec.md)
- [ADR-0007 — release-please release automation](adr-0007-align-release-with-jig.md)
- Jig spec 061 — dual-host plugin packages
