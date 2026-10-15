---
status: Proposed
dependencies: []
last_verified:
frame_review: true
---

# ADR-0044: Required constraints cannot be averaged away

## Status

Proposed (2026-10-14)

## Context

An approved required constraint must remain a gate even when the quality score is high.

Servo currently composes scalar signals. At the inspected main revision
`067ef5092d3c3ebe7d55a4e27610d7fe1d688463`,
[`oracle.sh.template`](../../templates/oracle.sh.template#L39-L110) compares a
single score or weighted average with a threshold;
[`checks.py`](../../skills/spec-oracle/checks.py#L753-L778) calculates the
fraction of passing checks, and its
[`--score-only` path](../../skills/spec-oracle/checks.py#L996-L1002) deliberately
returns 0 for ordinary check failures. This is the shipped scoring contract,
not a defect to retroactively rewrite into closed specs 001/006.

That contract cannot represent "all these particular assertions are mandatory"
by increasing weights: a required contradiction can still coexist with an
acceptable composite. Similarly, the current
[`gate.py`](../../skills/quality-gate/gate.py#L554-L573) labels oracle exit 1
`below_threshold`; a new high-score veto needs an honest explanation rather
than that numerical claim. [ADR-0033](adr-0033-design-eval-structured-scoring-policy.md)
owns the vision judge's reviewed catalogue and exclusions, not deterministic
required-assertion composition.

The initial cross-project consumer is a bounded Vellum card pilot. Vellum owns
source grounding and the approved design-input contract; Servo observes the
implementation and emits evaluation evidence; Jig attests completion from
that evidence. Claude Design is first, Figma is deferred. An export can later
prove source grounding without proving an application matches it. No production
application or calibrated general design oracle exists in this proposal.

## Decision Options Considered

### Option A: Keep all evidence in the weighted average
- **Pros:** No contract change; continuous scores remain convenient diagnostics.
- **Cons:** Weight/threshold tuning cannot guarantee that a particular required
  contradiction vetoes success. Missing or unmeasured assertions can disappear
  from a denominator.

### Option B: Add opt-in required evidence beside diagnostic quality scores
- **Pros:** Required constraints and quality retain their distinct meanings.
  Existing components and project-owned oracle machinery can be reused.
- **Cons:** Requires a versioned result channel, frozen policy bindings and
  updates to consumers, not merely a new template branch.

### Option C: Replace the oracle with a separate design evaluator workflow
- **Pros:** Could specialize every stage for design evaluation.
- **Cons:** Duplicates orchestration, approval and runtime ownership; makes
  non-design required checks a second system. A generic constraint language or
  evaluator registry is unnecessary for the bounded first consumer.

## Recommended Decision

Recommend **Option B**, pending owner acceptance and cross-repository contract
reconciliation. Required evidence is an opt-in project policy on existing
components, not a replacement for the scalar score or a new registry.

1. **Two independent channels.** Preserve continuous component scores,
   weights and the composite as diagnostics. Under enabled policy, pass
   requires both the existing quality threshold and a complete `pass` for
   every approved required assertion. Lowering `THRESHOLD`, assigning a zero
   weight, excluding an item from a judge rubric, or improving another
   component cannot waive a required assertion.
2. **Three exits, explicit mixed outcomes.** Preserve `0 = pass`,
   `1 = evaluated failure`, `2 = evaluation/environment refusal`.
   A collected observation that contradicts a required assertion, including
   an observed absent required element, is 1. Missing observations, unknown
   bindings, unsupported comparisons, invalid/stale identities or failed
   capture are 2, never a fabricated pass or a low score standing in for
   unavailable evidence. Refusal takes precedence over failure.
3. **Compatible opt-in reporting.** Default projects retain the version-1
   gate payload, legacy `pass/below_threshold/env_error` status and existing
   component semantics. Enabled policy uses a proposed version-2 gate payload
   with `status: pass|fail|env_error`, a reason distinguishing
   `quality_below_threshold`, `required_constraints_failed`,
   `required_and_quality_failed` and `required_evidence_unavailable`, plus
   required counts/IDs and evidence references. Consumers must understand
   this version before consuming it; an unknown version refuses rather than
   falling back to the scalar. These names are a proposal, not an accepted
   cross-project contract. **Gate-payload schema version 2** is a distinct
   namespace from existing design-eval policy `schema_version: 2`, the proposed
   design-evidence envelope version 1 and Vellum's input-contract version.
4. **Bound, fresh results.** Source identity, approved policy/configuration
   hash, evaluator artifact identity, evaluated-build identity and current
   evaluation-run identity bind to the evidence. Each required component is
   invoked once per evaluation; its score and structured result refer to that
   same invocation. The installed **overall gate-payload policy verdict** is
   completion authority, not a component envelope's `pass`. It binds each
   component record by run identity and content digest; a passing deterministic
   component plus failed quality threshold is overall failure and cannot
   support Jig attestation. An old ledger row, self-echoed build label or
   checkout hash is not proof of the running/current delivered bundle.
   Define canonical identity, approval and build-input closure before readiness;
   prove actual served-bundle/current-delivery linkage during implementation.
   Validate bindings before passing, retaining immutable raw observations on
   failure/refusal. Hashes are honest-drift tripwires, not protection against
   an actor who can rewrite both policy and hashes.
5. **Project-approved policy; observed facts stay separate.** Extend existing
   freeze/approval mechanisms to cover the required set, source mapping,
   explicit normalizations/tolerances, comparison implementation and any
   exclusions. Changing them requires review and explicit reapproval.
   Per-constraint observations remain distinguishable from policy-interpreted
   verdicts. A model score does not prove deterministic facts.
6. **Ordinary Servo evidence.** Reuse spec-oracle's `command` /
   `generated_artifact_command`, approved overlay, SEED splice and ledger
   seams, plus existing capture/hash/ledger helpers where appropriate.
   Deterministic design evidence consumes Vellum's approved targets; Servo
   does not define a competing input schema. A missing required binding
   refuses. Do not retrofit new semantics into frozen installations silently.

The implementation owners are
[spec 035](../specs/035-required-evidence-alongside-quality-scores/spec.md) and
[spec 036](../specs/036-deterministic-design-evidence/spec.md). Spec 030 retains
suitability-signal ownership; this ADR does not accept or complete it.
**Proposed implementation order, not owner approval:** 035-01 can start with
standalone existing-check fixtures after the agreed C0 contract checkpoint.
Vellum's 013-01 C1 approved-input preparation checkpoint can provide real
approved normal/open inputs while that slice is
IN_PROGRESS, without completing its Servo integration or 013-02 state handoff.
036-01 then builds and proves its observer, immutable local fixture-bundle
transport and gate linkage; Jig119 consumes preserved overall gate runs without
re-running/re-scoring; Vellum integration closes afterward. No upstream DONE
or not-yet-written observer is a 036-01 readiness prerequisite.
Copilot native unattended Servo execution remains unsupported under
[ADR-0043](adr-0043-copilot-capability-boundaries.md); app-native project
coordination and runnable project oracles are sufficient for the pilot.

## Consequences

**Becomes easier:**
- A missing title or wrong subtitle state can veto an otherwise excellent
  quality score with a concrete, inspectable reason.
- Jig can attest the exact build/source/policy/run evaluated without owning
  measurement or reinterpreting a diagnostic average.
- Teams can introduce required policy deliberately while retaining existing
  scalar-only projects.

**Becomes harder:**
- Template, installer, gate, loop, hook, planner and report paths need
  coordinated version-aware behavior and negative controls.
- Reliable running-build identity and complete constraint bindings must be
  supplied; a screenshot, export, timestamp or commit label alone is insufficient.
- Regional image metrics need bounded calibration and portability evidence
  before they can become approved required thresholds.

## Assumptions

- A version-2 opt-in envelope is acceptable to cross-project and external
  consumers. Confirm the exact version, names and adoption behavior before
  readiness; default version-1 compatibility is the bounded guarantee.
- Vellum can deliver approved targets with confirmed card bindings, states,
  source identity and crop boundaries. Its sibling input-contract draft is
  authoritative and remains a prerequisite, not a schema inferred here.
- The first controlled web fixture can expose independently checkable build
  identity and repeatable observations using a closed immutable local bundle.
  Its closure/approval contract must be agreed before readiness, and actual
  transport/current-delivery proof demonstrated during implementation, not
  assumed from a manifest or made a circular precondition.
- Impeccable's raster routines may be portable/useful as an isolated pinned
  comparison. Neither dependency selection nor metric calibration on Vellum
  is established; golden parity alone would not establish either.

## Kill criteria

- A required contradiction passes at high quality, zero required-component
  weight or `THRESHOLD=0`: reject the implementation and keep policy disabled.
- Results cannot distinguish missing measurement from an observed
  contradiction, or cannot bind to the running/current delivered bundle:
  block pilot acceptance; unresolved identity/closure definitions block readiness.
- Component `pass` alone permits completion while quality policy fails:
  reject the gate/attestation integration.
- Reuse requires bypassing an approved freeze or changing untouched scalar
  installations: redesign the adapter instead of accepting that migration.
- Raster portability/calibration is not demonstrated: do not adopt its engine
  or required thresholds; the exact-observation card slice remains useful.

## Open questions

- Parent reconciliation must pin Vellum ADR-0011/spec013's input-contract
  artifact/revision and Jig's proposed ADR-0065/spec119 attestation consumer
  before owners accept the decision. Vellum's proposal is published in draft
  [PinkException/vellum#50](https://github.com/PinkException/vellum/pull/50) at
  `7f4c06077318859c0aabec33d00c2eebd6cba74f`; this is not an approved executable
  input revision. Jig's Proposed ADR-0065/DRAFT spec119
  are published in [ramboz/jig#242](https://github.com/ramboz/jig/pull/242),
  pinned at `c118595ca122351f4f213d29ff5f06302321c2b0`; publication is not
  acceptance, and closed Jig spec 071 is not the new consumer owner.
- Confirm the version-2 output proposal with cross-project consumers. A
  material change to versioning or authority requires fresh frame review.
- Owners must approve the proposed preparation checkpoint/order, immutable
  local fixture-bundle identity/transport boundary, missing-tolerance refusal
  and normalization policy at C0 before C1 input preparation/runtime work.
  The coordinator recommends inclusive +/-1 CSS px for derived DOM geometry,
  zero tolerance for declared font size/weight, and exact normalized text,
  CSS-family declaration and color; this is not user-approved policy.
- Regional metric engine, bounded calibration set and permitted licensing /
  dependency footprint remain unsettled; spec 036-02 owns that readiness gate.
