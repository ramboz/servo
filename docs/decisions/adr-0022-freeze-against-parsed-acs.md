---
status: Accepted
date: 2026-07-01
deciders: ramboz
supersedes:
superseded-by:
last_verified: 2026-07-02
---

# ADR-0022: Freeze the spec-oracle against parsed ACs, not the raw spec file

## Status

Accepted (2026-07-02)

Surfaced by an external dogfood (cwv-workbench spec 015); awaiting acceptance.
Refines [spec 006](../specs/006-spec-oracle/spec.md)'s freeze-and-controls
(006-04).

## Context

`checks.py --enforce-freeze` ([spec 006-04](../specs/006-spec-oracle/spec.md))
freezes a spec-oracle and refuses to score (`spec_oracle_stale`) when the source
spec has changed since approval. It detects change via a hash of the **raw spec
file**.

That coupling breaks for consumers whose spec files are **living documents**. In
the cwv-workbench dogfood the spec author is jig: the slice `.md` carries a
mutable `status:` frontmatter that is **rewritten on every lifecycle transition**
(DRAFT → … → DONE, mirrored onto `spec.md`), and deviation-log / reconciliation
sections are appended later. So the frozen oracle went `spec_oracle_stale` the
instant the slice advanced state — at *every* transition — even though **no
acceptance criterion changed**. The only workaround was to perform all
transitions before freezing and uninstall the overlay after DONE: brittle, and it
defeats the point of a durable frozen oracle.

## Decision

Freeze the spec-oracle against the **parsed acceptance-criteria set** — the ACs
servo already extracts into `checks.json` — **not** the raw spec-file bytes.

- `--enforce-freeze` compares the *current parsed ACs* against the *approved*
  ones. Servo already stores `approved_content_hash` over `checks.json`; keep
  that and **drop the raw-source-file hash check**.
- Only a change to the acceptance criteria themselves re-triggers `stale`.
  Mutations to volatile frontmatter (`status`, `last_verified`) or appended prose
  (deviation logs, reconciliation) do not.
- Define "the AC set" canonically (normalize whitespace + item order) so trivial
  reformatting does not false-stale.

## Consequences

### Positive
- The freeze survives living-document lifecycles (jig — or any workflow that
  annotates specs as work progresses). No more spurious `spec_oracle_stale` on a
  status bump.
- Decouples servo entirely from any consumer's frontmatter schema.

### Negative
- Requires a canonical AC-normalization so reformatting is not seen as a change.
- A prose edit *around* ACs that leaves the ACs unchanged will not re-freeze —
  acceptable, since the ACs are what the oracle gates.

### Neutral
- `approved_content_hash` over `checks.json` already exists; this mostly *removes*
  the extra raw-file check rather than adding machinery.

## Alternatives considered

- **Hash the raw file, then fall back to a semantic "is this only a status
  change?" diff.** Rejected — nondeterministic, and couples servo to the
  consumer's frontmatter schema (it would have to know jig's fields).
- **Require consumers to keep spec files immutable after approval.** Rejected —
  living specs are jig's model (and a reasonable one); servo should not dictate
  the consumer's authoring lifecycle.

## Verification

cwv-workbench dogfood finding F4: the frozen overlay refused with
`spec_oracle_stale` on each jig transition; the transitions-before-freeze
workaround proves the coupling is to the raw file, not the ACs. Acceptance
criterion: a status-frontmatter change (or an appended deviation log) on an
approved spec does **not** trigger `spec_oracle_stale`; an edit to an AC does.

## References

- [Spec 006-04](../specs/006-spec-oracle/spec.md) — freeze-and-controls,
  `--enforce-freeze`, `approved_content_hash`, `spec_oracle_stale`
- [ADR-0005](adr-0005-eval-oracle-component.md) — frozen oracle component
- cwv-workbench ADR-0015 (Amendment: F4 living-spec-vs-freeze)
- Implemented by [Spec 019](../specs/019-compile-core-simplification/spec.md)
