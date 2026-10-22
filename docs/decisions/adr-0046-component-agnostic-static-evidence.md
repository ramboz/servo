---
status: Accepted
dependencies: []
last_verified: 2026-10-22
frame_review: true
---

# ADR-0046: Component-agnostic static evidence with native required verdicts

## Status

Accepted (2026-10-22)

## Context

Reusable design evidence must not ship a component-specific evaluator.

The owner explicitly chose to retire the unmerged proof-of-concept interfaces
and replace the initial design-oracle effort with product-only changes.
[Spec 037](../specs/037-reusable-design-evidence/spec.md) records that
prospective scope. This decision does not amend an old record or approve any
application, source package, policy, or evaluation result.

Inspection of source cut `f0041335ac42f0892874f275e61d4b135ff46205`
establishes a useful existing boundary: the generic required gate operates
on ordinary check plans and declared artifacts
(`skills/quality-gate/required_runtime.py:308-342,524-556,704-725`), while
the static observer's comparison, bindings and resource acquisition take
explicit input data
(`skills/design-eval/static_contract.py:110-200,304-342,385-510,617-640`;
`static_snapshot.py:24-86`). These are citations to that inspected source
cut, not current-main line claims.

The same observer unnecessarily copies complete pilot modules to obtain
strict file/JSON/hash operations, Python startup checks, native-link inventory,
and invocation/summary helpers
(`static_contract.py:24-26,523-529,643-645,739-740,962-963`).
Copying the pilot evaluator intact, even into a fixture or renamed module,
would violate the owner-approved product boundary.

## Decision Options Considered

### Option A: Retain the pilot and add generic adapters

This preserves experimental interfaces, but leaves the shipped runtime coupled
to a specific component and its capture/quality policy. Rejected: the owner
explicitly chose retirement, not compatibility.

### Option B: Extract only used primitives and retain the bounded static profile

This reuses the generic gate, native consumers and static algorithms while
removing the pilot dependency. Manifests supply roles, IDs, bindings, resources
and environment. Its limit is explicit: the currently supported producer,
copy-build/resource shape, runtime closure and comparison semantics remain
bounded.

### Option C: Build a provider registry, new schema language or generalized engine

This could serve future producers and frameworks, but introduces unrequested
abstractions and changes the contract instead of removing the actual coupling.
Rejected: component independence does not require arbitrary framework support.

## Recommended Decision

Choose **Option B**.

1. Keep required evidence separate from weighted quality. Native overall
   authority rejects a required failure even when quality passes and refuses
   when required evidence is unknown. Existing no-opt-in behavior stays intact.
   Consumers retain that native result and its immutable references, rather
   than reconstructing success from a diagnostic score.
2. Put only used strict JSON, canonicalization, no-follow file/hash, path,
   inventory and publication primitives in `evidence_io.py`. Put only used
   startup checks, native-link inventory, invocation ownership and summary
   helpers in `evidence_runtime.py`. The static copied runtime contains those
   two files, `static_contract.py`, and `static_snapshot.py`, not a pilot module.
3. Retain `static-source-contract-app/1` and the existing finite static
   comparison/resource semantics. The source contract remains
   `vellum-confirmed-source/0.2` with profile `static-css-subset/1`.
   Vellum owns source interpretation and live original-source freshness.
   Its clean producer closure is the actual
   `confirmed_source.py`, `capture_confirmed.py`, `design_input.py`,
   `redline_intake.py`, `resolve_redline.py`, `validate_redline.py` set,
   pinned to the new cut. Changed helper bytes require new approvals.
4. Keep the existing public prepare, review/approve, ordinary overlay install,
   evaluate, and pure verify-current path. Native gate consumers remain
   read/hash-only during preserved readback. A pure producer readback checks
   current source/policy/runtime/selected delivery without capturing or rescoring.
5. Prove reuse with two different non-card source/application shapes through
   actual public entry points, with explicit new test-only approvals and native
   0/1/2 controls. This is product validation, not real-app attestation.
6. Leave the existing general quality engine untouched. Retire the pilot's
   fixed role/geometry inventory and model/attempt/threshold policy rather
   than making those product defaults.

## Consequences

**Becomes easier:**
- A project can supply its own component inventory without importing pilot code.
- Distribution and currentness checks can enumerate a small real helper closure.
- Consumers share native required/quality authority across execution surfaces.

**Becomes harder:**
- Old experimental installations do not receive compatibility or approval
  migration; they remain historical and need fresh explicit preparation.
- Runtime/producer changes invalidate old approved bytes and need a new epoch.
- The bounded macOS native-link/runtime and static snapshot profile must be
  documented honestly; no arbitrary-platform or full-application claim follows.

## Assumptions

None.

## Kill criteria

If either non-card public workflow needs a fixed role, component dispatch,
invented source authority, skipped runtime closure check, or bundled pilot
module to succeed, the extraction is not complete and must not ship.

## Open questions

None. The producer cut and runtime are integration inputs verified before
sealing, not permission to infer new source semantics.
