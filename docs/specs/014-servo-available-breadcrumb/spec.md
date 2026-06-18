---
status: DONE
dependencies: [007, adr-0013]
last_verified: 2026-06-18
---

# Spec 014 - servo availability breadcrumb

> Follow-up to [ADR-0013](../../decisions/adr-0013-servo-available-breadcrumb.md):
> write a host-neutral user-state breadcrumb so sibling tools can detect that
> servo has been observed on the machine without invoking servo or depending on
> Claude-specific plugin registries.

## Overview

Servo has several install surfaces: source or release plugin roots, local clone
verification, and project-local runtime scaffold copies. Jig's prepare path
needs a cheap way to answer "servo is probably available here" while the target
project may not yet have `.servo/` state.

ADR-0013 defines the shared breadcrumb contract:

```text
${XDG_STATE_HOME:-$HOME/.local/state}/servo/available.json
```

This spec implements that contract across the servo writer paths and updates
the docs/refinement records that originally parked the item.

> **Status: DONE.** Slice 014-01 ships all ADR-0013 writer paths, docs, review
> evidence, and reconciliation.

## Assumptions

- The breadcrumb is advisory. Consumers must treat absence, stale content, or a
  moved `source_path` as inconclusive rather than proof that servo is
  unavailable.
- Target-local scaffold authority stays under `.servo/`; the breadcrumb is
  only a machine/user-level availability hint.
- Marker writes remain best-effort so locked-down user-state locations do not
  break install, scaffold, or verification flows.

## Decomposition

SPIDR - primarily **Interface** plus **Rules**:

- **Interface:** a versioned JSON marker at the ADR-0013 path, with a small
  stable schema.
- **Rules:** writer paths refresh the marker only after their primary work
  succeeds, and marker write failures warn without changing the command result.

No spike is needed. ADR-0013 fixes the contract; this slice wires the known
writer paths and regression tests it.

## Slices

- [014-01 - breadcrumb marker writers](slice-01-breadcrumb-marker-writers.md)
