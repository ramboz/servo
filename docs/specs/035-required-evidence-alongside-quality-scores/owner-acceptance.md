# Owner acceptance and standalone readiness

## Approval received

On 2026-10-14 the coordinating parent relayed the owner's selected action
verbatim:

> Approve the ADRs and pilot contract; start implementation (Recommended)

The explicit grant covers Vellum ADR-0011, Servo ADR-0044, Jig ADR-0065 and the
pinned C0/card-pilot defaults at these reviewed proposal snapshots:

| Owner | Approved snapshot | Authority |
|-------|-------------------|-----------|
| Vellum | [`a538a2b474a9f3e1119379aba44257d319e1c276`](https://github.com/PinkException/vellum/blob/a538a2b474a9f3e1119379aba44257d319e1c276/docs/specs/013-design-to-oracle-handoff/input-contract-pilot.md) | C0 input serialization/version/digest domains/vectors, required state inventory, comparison normalizers/defaults and source approval meaning. |
| Servo | [`91f8d97d2d6f7c358a5de93c22aa143fd417d07c`](https://github.com/ramboz/servo/tree/91f8d97d2d6f7c358a5de93c22aa143fd417d07c/docs/specs/035-required-evidence-alongside-quality-scores) | Required veto, installed overall gate authority, separate result namespaces, runtime observation and bounded local-bundle identity/closure responsibility. |
| Jig | [`e83ad795e5bc692ea9ac4e2a25c9b6923e26522e`](https://github.com/ramboz/jig/blob/e83ad795e5bc692ea9ac4e2a25c9b6923e26522e/docs/specs/119-mixed-design-evidence-attestation/spec.md) | Preserved-run completion attestation, independent current-delivery binding and renewed provenance for new legacy attestations. |

This records approval conveyed by the owner through the coordinator, not an
independent agent approval or authenticated signature. The peer snapshots still
contain their pre-acceptance wording; this dated record identifies the newly
approved revisions without rewriting their historical snapshot bytes.

The accepted pilot defaults include required normal/open band-width identity,
inclusive +/-1 CSS px derived band geometry, zero declared size/weight
tolerance, exact normalized text/color and typed CSS-family declarations,
unknown/refusal for missing/unsupported required evidence, and the controlled
immutable local fixture-bundle boundary. Generic versus quoted named font
tokens remain distinct; no font-face detection is claimed.

**Not approved by this grant:** PR merges; future real-design target values;
source facts/captures or C1 packages not yet produced and reviewed; an
unwritten project's effective live quality policy; raster engine/dependency
adoption; new global plugins; or any relaxation of unsupported native Copilot
Servo autonomy. Approval of the contract does not prove implementation or
complete the source/runtime integration.

## ADR acceptance

Installed Jig `adr.py accept 0044` accepted
[`docs/decisions/adr-0044-required-constraints-cannot-be-averaged-away.md`](../../decisions/adr-0044-required-constraints-cannot-be-averaged-away.md)
with its genuine passing
[frame-critique artifact](../../decisions/reviews/adr-0044-frame-critique.md).
The ADR's decision body was unchanged from its reviewed alignment revision
through the approved Servo snapshot. The helper changed only canonical status,
its prose mirror and `last_verified`; index regeneration changed the derived
status. No acceptance bypass was used.

The ADR is now immutable. Its original "proposed/pending" prose records the
proposal-time context; this acceptance record supplies the owner disposition
and approved peer references without altering Accepted decision content.

## Actual 035-01 readiness

| Existing Definition of Ready item | Current evidence / disposition |
|----------------------------------|--------------------------------|
| ADR-0044 acceptance after alignment/frame critique | Satisfied by the explicit grant, unchanged reviewed decision and installed-helper acceptance. |
| Required-field/result-channel/version-2 proposal independently reviewed | Passing fresh 035-01 frame artifact plus approval of the pinned Servo/Jig authority/version proposal. |
| Unavailable evidence and migration behavior pinned | Approved spec035 decision table and compatibility criteria; missing/stale/unknown evidence refuses, defaults remain scalar-compatible. |
| Identity serialization/approval closure pinned | Approved Vellum C0 owns its input domains/vectors; approved Servo snapshot owns separate policy/gate/component domains and closure predicates. Exact implementation carrier/field mapping must be made explicit in the implementation plan before readiness is advanced; do not apply Vellum's serializer to Servo's separate namespace or infer wire interoperability from common digest labels. |
| Existing command-check fixtures available | `CommandPrimitiveTests` and `GeneratedArtifactCommandTests` ran through the existing unittest runner: 17 tests passed. No future observer or design input was needed. |
| No completed Vellum/Jig slice, capture or observer prerequisite | Confirmed by 035-01's existing DoR. New installed-result/race proof remains implementation work, not a readiness gate. |

**Standalone 035-01 has no upstream runtime blocker.** Its remaining pickup
work is to record the concrete required-check/result-carrier encoding and
approval-field closure in its implementation plan under the accepted semantics,
then complete normal spec/readiness review and transition through
READY_FOR_REVIEW to READY_FOR_IMPLEMENTATION using Jig. The present
`check-reviews --stage READY_FOR_REVIEW` clears the frame-evidence gate only;
it is not implementation proof or a completed readiness transition.

This short turn leaves both specs and all four slices DRAFT. It does not claim
035-01 IN_PROGRESS or approve a live quality policy. The next implementation
session must start from this accepted proposal branch, not main's reserved
stubs, and preserve the ordinary ceremony before source changes.

## Cross-project order and remaining later prerequisites

After C0 acceptance, standalone Servo035-01 and Vellum013-01 C1 input preparation
can proceed independently. Vellum's author/distinct approver still must produce
real approved normal/open source inputs while 013-01 can remain IN_PROGRESS.
036-01 consumes that C1 checkpoint and builds/proves its observer, immutable
bundle transport and actual served/current-delivery linkage. Jig119 consumes
preserved overall gate runs, then Vellum integration closes. Preparing open
source inputs does not complete 013-02, and upstream DONE is not required to
start either standalone gate work or the later observer.

036-01 still needs 035-01 DONE, actual C1 input and its own normal readiness
review. 035-02 follows 035-01; 036-02 additionally needs its declared prior
slices and separately approved regional engine/license/portability/calibration.
None of those later prerequisites is a new blocker for standalone 035-01.
