---
status: Proposed
date: 2026-07-01
deciders:
supersedes:
superseded-by:
last_verified: 2026-07-01
---

# ADR-0023: Co-locate durable spec-oracle artifacts with the spec; keep only ephemeral state under .servo/

## Status

Proposed (2026-07-01) — surfaced by an external dogfood (cwv-workbench spec 015);
awaiting acceptance. Refines the `.servo/` layout established by
[ADR-0004](adr-0004-session-state-file-format.md) and
[ADR-0016](adr-0016-execution-plan-handoff.md).

## Context

A spec-oracle's durable artifacts (`plan.md`, `checks.json`) live under
`<target>/.servo/spec-oracles/<spec-id>/`, spatially disconnected from the spec
they evaluate (`docs/specs/<spec>/slice-NN.md`). The cwv-workbench dogfood showed
this disconnect has real costs:

- it forces `spec-id`s that **duplicate the spec's own path**
  (`015-01-typed-cross-reference-schema`);
- it is part of why the freeze couples across a directory boundary (see
  [ADR-0022](adr-0022-freeze-against-parsed-acs.md));
- it **separates a spec from its oracle** in review and git history, even though
  the oracle is spec-*derived*, spec-*reviewed* evidence that goes stale when the
  spec changes — it behaves like a spec artifact, not a tool artifact;
- the shared runner `checks.py` (~39 KB) is **copied identically into every
  overlay dir** (6× in the dogfood — verified byte-identical).

## Decision

- **Co-locate the durable, spec-bound artifacts** (`plan.md`, `checks.json`) with
  the spec — e.g. `docs/specs/<spec>/oracle/<slice>/` or a sibling of the slice —
  so a spec and its oracle travel together in git and review, and the `spec-id`
  path duplication disappears.
- **Keep only ephemeral / target-runtime state under `.servo/`**: `runs/`,
  `ledger.jsonl`, the install manifest, the execution-plan handoff (ADR-0016).
- **Do not copy the shared runner per overlay.** Reference a single shared
  `checks.py`; vendor-copy only for the documented clone-portability case
  (e.g. a Routine that clones the repo into cloud infra).

## Consequences

### Positive
- A spec + its oracle is one reviewable unit; the "which oracle gates which
  slice" mapping is obvious from the tree.
- Removes the `spec-id` path duplication and the 39 KB × N `checks.py`
  duplication.
- Complements ADR-0022: the ACs the freeze hashes now live next to the spec.

### Negative
- Mixes servo-generated artifacts into the project's `docs/` tree (a
  separation-of-concerns cost some projects will dislike).
- Requires a migration of the existing `.servo/spec-oracles/` layout + the
  install/enforce-freeze path resolution.

### Neutral
- Ephemeral loop/heartbeat state stays under `.servo/` exactly as ADR-0004 /
  ADR-0010 / ADR-0016 specify — this ADR only moves the *durable, spec-derived*
  artifacts.

## Alternatives considered

- **Keep everything under `.servo/`.** Rejected — the disconnect caused concrete
  friction (freeze coupling, id duplication, split review).
- **Path-mirror `.servo/spec-oracles/<spec-path>/` without co-locating.** Partial
  — removes id duplication but not the review / git-travel separation, and the
  oracle still lives away from the spec it belongs to.

## Verification

cwv-workbench dogfood: confirmed 6× byte-identical `checks.py` copies, `spec-id`s
that restate the spec path, and the cross-boundary freeze coupling (ADR-0022).
Acceptance criterion: a spec's durable oracle artifacts sit under the spec's own
directory; `.servo/` contains no per-spec durable copies; `checks.py` is not
duplicated per overlay.

## References

- [ADR-0004](adr-0004-session-state-file-format.md),
  [ADR-0016](adr-0016-execution-plan-handoff.md) — `.servo/` state layout
- [ADR-0022](adr-0022-freeze-against-parsed-acs.md) — freeze against parsed ACs
- [Spec 006](../specs/006-spec-oracle/spec.md) — spec-oracle
- Implemented by [Spec 019](../specs/019-compile-core-simplification/spec.md)
