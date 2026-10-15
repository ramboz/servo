---
slice: 036-01 - bound-card-evidence
pass: spec-readiness
verdict: pass
reviewer: jig:reviewer / card-readiness-resolution (fresh context)
reviewed_at: 2026-10-15
---

# Independent specification readiness

The first fresh `card-readiness` review returned `needs-changes`: accepted
checkpoints, scope, candidate/delivery plan and opt-in carrier/refusal semantics
were sound, but the exact raw-evidence embedding, design-envelope mapping and
pinned consumer readback boundary were not specified.

The plan now names the exact `result_artifact` wire shape, complete run-scoped
inventory, raw-byte hash encoding/preimages, pure
`validate_output_references(check, evidence, run_id, base)` API, 035-02/Jig
consumer boundary, and design-envelope field/observation mapping.

Actual fresh-context resolution verdict:

> VERDICT: pass
>
> The exact-output blocker is resolved: `plan.md:98–135` specifies the
> raw-evidence `result_artifact` wire shape, byte-digest/inventory bindings,
> pure `validate_output_references` API, and pinned 035-02/Jig119 consumer
> boundary without re-scoring. The design-envelope mapping and
> serialization/reference rules are explicit at `plan.md:166–188`.
> Live acquisition, quality and closure proofs correctly remain implementation
> obligations; owner-selected Opus/ClaudeCLI and the eight-total-invocation
> allowance are recorded at `plan.md:190–212`.
> DoR can clear for READY_FOR_IMPLEMENTATION to IN_PROGRESS; no remaining
> readiness blockers were found.

These line references describe the reviewed snapshot. DoR dispositions:
035-01/ADR0044 clear; accepted C0 and independently approved C1 clear;
exact versions/inventories/normalization/bindings clear; output/consumer
mapping clear; controlled bundle/browser/comparison boundary clear.
No implementation compliance, source/candidate quality result, reviewed
quality freeze or Jig completion is claimed by this specification review.
The owner-authorized first calibration is limited to eight total judge calls;
further live scoring requires further allowance.
