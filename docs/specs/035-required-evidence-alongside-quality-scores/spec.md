---
status: DRAFT
skill: quality-gate
use_cases: []
---

# Spec 035: Required evidence alongside quality scores

## Overview

A project can mark approved assertions as required and receive a failing gate
when any is contradicted, even if its continuous quality score passes. Evidence
that is missing, unknown, invalid or stale refuses evaluation rather than
passing. Scalar-only projects keep their existing behavior.

This implements proposed
[ADR-0044](../../decisions/adr-0044-required-constraints-cannot-be-averaged-away.md).
It serves the evaluation-model, oracle-synthesis and evaluation-report goals in
[the product vision](../../product-vision.md#two-phases-servo-compile-and-servo-run).
The vision has no `## Use cases` section; `use_cases: []` is intentional.
This is new opt-in policy, not a repair or amendment of shipped specs.

## Current state and existing owners

Inspected at main `067ef5092d3c3ebe7d55a4e27610d7fe1d688463` on 2026-10-14:

| Grounded seam | Evidence | Implication |
|---------------|----------|-------------|
| Scalar composite and threshold | `templates/oracle.sh.template:39-110` | No independent required verdict in this driver. |
| Fraction passed; scalar-only exit 0 for ordinary failures | `skills/spec-oracle/checks.py:753-778,996-1002` | A fraction/threshold can mask a particular failed check. |
| Frozen overlay and normal SEED installation | `skills/spec-oracle/oracle_overlay.py:80-99,234-280`; `checks.py:836-907` | Extend existing artifacts and approval, not a registry. |
| Exit 1 labeled below_threshold | `skills/quality-gate/gate.py:554-573` | New mixed failures need versioned, honest reasons. |
| Hook retry wording is scalar-oriented | `templates/meta-judge.sh.template:64-74` | A template-only change would leave misleading recovery advice. |
| Existing loop/heartbeat reporting | `skills/agent-loop/loop.py:2363-2419`; `skills/heartbeat/heartbeat.py:2086-2110` | Preserve verdict/reason/evidence through these consumers. |

The seam inventory is bounded to canonical repository consumers, not a claim
about unknown external scripts. Generated host packages and target-vendored
runtimes must be included when the canonical surfaces change.

Spec 006 owns the shipped check/overlay library; spec 012 and ADR-0033 own
vision-judged design scoring. Spec 030 owns suitability's approved-eval signal,
not required evidence. Do not modify their closed records or take over their
open work. Spec 036 consumes this gate for deterministic design observations.

## Proposed policy and result contract

**Opt-in is approved project policy**, recorded through the existing install /
overlay mechanisms. Absence of the policy keeps legacy behavior. Once enabled,
runtime flags or scalar threshold overrides cannot disable it. No unapproved
auto-upgrade or rewritten customized oracle is allowed.

For spec-oracle checks, propose optional `required: true` on existing check
entries; omitted means the current diagnostic/scoring behavior. A component
declared required must provide complete structured evidence for its approved
assertion set. Scalar-only legacy components are not silently promoted to proof.
The exact extension and component/result binding are reviewed in 035-01.

The invocation emits its existing score plus a versioned run-matched result
artifact. Reuse the component's artifact directory and existing ledger writer;
do not rerun commands to obtain the second channel or scan for the "latest"
successful ledger row. Bind run identity, component identity, approved required
set/config hash and evaluator artifact identity; consumers validate completeness
and exact invocation correspondence.

The installed **overall gate-payload policy verdict**, not an individual
component's `pass`, is completion authority. Its preserved run record binds
every referenced component result by that gate run ID and content digest.
Component success plus failed quality threshold is overall failure; Jig must
not attest it by inspecting the component envelope in isolation. This keeps
quality policy and required policy both authoritative, without re-scoring.
The gate record includes effective quality threshold/weights and permitted
runtime override provenance, approved required policy identity and all
run/digest-bound component references; a consumer cannot reconstitute a
different overall verdict by ignoring the policy or changing those values.

| Policy outcome | Oracle/gate exit | Enabled gate v2 status / reason |
|----------------|------------------|--------------------------------|
| All required pass, quality passes | 0 | `pass`, no failure reason |
| Complete required contradiction, quality passes | 1 | `fail` / `required_constraints_failed` |
| Required pass, quality below threshold | 1 | `fail` / `quality_below_threshold` |
| Complete required contradiction and low quality | 1 | `fail` / `required_and_quality_failed` |
| Any required observation/result/binding is unavailable, invalid or stale | 2 | `env_error` / `required_evidence_unavailable`, with per-item causes |

Refusal takes precedence over evaluated failure; record every available
contradiction as well. `required_status: pass|fail|unknown` and required IDs,
counts, per-item reasons and evidence references accompany the v2 result.
Unknown is not not-applicable. An approved required residual/unsupported check
cannot pass until an executable binding exists or an owner explicitly changes
the frozen policy. A valid empty required set leaves the quality gate intact;
an absent result for a nonempty set is not empty. Duplicate, extra, removed or
unrecognized required IDs are invalid evidence, not a denominator adjustment.

Default gate JSON stays schema version 1 with today's status vocabulary,
component scores and 0/1/2 exits. Enabled projects opt into version 2 with
`pass|fail|env_error`; in-repository readers support both explicitly and refuse
unknown versions. A high-score veto is never presented as numerically
`below_threshold`. The names/version are proposed for parent reconciliation,
not an accepted external interface.

**Version namespaces:** "gate v2" in this spec means the quality-gate payload's
`schema_version: 2`, not the existing design-eval policy schema version 2.
Spec 036 separately proposes a design-evidence envelope version 1. Vellum owns
its input version; no equality or automatic conversion between these versions
is implied.

Policy changes (required membership, component bindings, comparisons,
tolerances or exclusions) invalidate approval and require explicit reapproval.
Freeze protects honest drift, not malicious co-rewriting of policy and hashes.
A reference/model ignore-list cannot waive a required assertion.

## Readiness and cross-project order

035-01 is independently implementable with existing deterministic check
fixtures after its own decision/readiness review. It does not require Vellum
captures, Vellum013-01 DONE, a new observer or completed Jig attestation.
Agree component/gate identity serialization, approval records and closed
required-ID/config/artifact sets before readiness; actual race-safe publication
and installed linkage are implementation proof, not prerequisites.
The proposed shared **C0** checkpoint pins accepted/aligned decisions plus
input/output versions, serialization/digest domains and reviewed test vectors,
required comparison inventory and served/current-delivery closure predicates.
No runnable-all-consumers or upstream integration completion is required at C0.

For the design pilot, the coordinator proposes: Vellum013-01 provides **C1**, an
owner-approved normal/open source-artifact checkpoint while IN_PROGRESS;
036-01 builds/proves the observer and served/current-bundle binding; Jig119
attests preserved overall gate runs; then Vellum integration closes. 035-02
can follow 035-01 without waiting on Vellum/Jig completion. Cross-project
contract decisions need alignment, not completed integrations. Exact checkpoint
and transport approval remain owner choices in spec036.
Input preparation C1 and standalone gate implementation can proceed
independently after C0; neither requires the other's runtime completion.

## Scope and non-goals

Wire canonical scaffold/template/overlay installers, checks and approved
policy, quality-gate, supported loop drivers and resume/report paths,
oracle-hook advice, execution-planner evidence references, heartbeat handoff
and generated/vendored installation surfaces. Add user-facing diagnostics and
negative controls, not a generic constraint language or orchestration layer.

No Vellum input schema, Jig lifecycle change, new evaluator registry, changed
default weights/thresholds, automatic approval, native Copilot unattended loop,
or implementation in this authoring PR. Preserve hook env-error fail-open
continuation semantics: inability to block a turn is not evidence of completion.

## Assumptions

- Cross-project consumers can adopt the opt-in v2 proposal. Confirm exact
  fields/names before readiness; no compatibility claim for unknown external
  consumers that insist on an exact old payload.
- A run-matched result can travel through existing component artifact seams
  without duplicate evaluation or concurrent-run aliasing. Prove this with
  real installed gate invocations, not a direct scorer-only test.

## Decomposition

Two vertical slices using Rules, then Interface/Path. First deliver a working
installed CLI gate for existing deterministic checks, including freeze and
legacy behavior; then carry that same veto and recovery evidence through
supported execution/report consumers. Neither slice is a parser-only or
template-only phase. Research stays inside each slice's readiness/validation,
not a preliminary spike.

## Slices

- [035-01 - installed required gate](slice-01-installed-required-gate.md)
- [035-02 - required verdict through consumers](slice-02-required-verdict-consumers.md)
