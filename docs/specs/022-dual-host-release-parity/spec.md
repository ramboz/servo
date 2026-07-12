---
status: DONE
dependencies: [007-05, 009-02, 010-04, adr-0007, adr-0028]
last_verified: 2026-07-12
---

# Spec 022 — dual-host release parity

> Bring Servo to Jig's current CI and release baseline: committed generated
> Claude and Codex plugin packages, a drift guard, host-explicit release assets,
> synchronized release-please versions, and symmetric documentation.

## Why this spec

Specs 009 and 010 aligned Servo with Jig's earlier full-suite CI and
release-please pipeline. Jig has since moved its install boundary forward:
canonical source is projected into committed host-native packages, CI guards
those packages against drift, and releases carry one archive per host. Servo
still points Claude at the repository root and publishes one Claude-shaped zip.

## Goals

1. Generate committed runtime-only packages for Claude Code and Codex from one
   canonical source tree.
2. Fail CI when either committed package or any root/host manifest drifts.
3. Publish and smoke-test host-explicit Claude and Codex release archives.
4. Document native install commands, package topology, host-specific runtime
   limitations, contributor regeneration, and release-please behavior.
5. Treat spec 008 as complete for next-release planning without editing its
   parallel-owned implementation files.

## Non-goals

- Making `claude -p`, `/goal`, or Claude `Stop` hooks execute natively in Codex.
- Adding a Codex project-local scaffold mode.
- Changing Servo's oracle or evaluation contracts.
- Editing spec 008's slice files while its implementation is in flight.

## Assumptions

None. Current package and workflow behavior was verified directly against the
Servo and Jig working trees on 2026-07-12.

## SPIDR analysis

**Interface split, delivered as one release-boundary slice.** The user-facing
unit is a coherent release: both hosts must install, validate, and receive
version-matched artifacts together. Splitting the builder, CI guard, workflow,
and docs into independently landed horizontal slices would temporarily publish
an incomplete host contract.

## Slices

- [022-01 — dual-host release boundary](slice-01-dual-host-release-boundary.md)
