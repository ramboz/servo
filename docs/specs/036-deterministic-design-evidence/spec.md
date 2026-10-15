---
status: DRAFT
skill: spec-oracle
use_cases: []
---

# Spec 036: Deterministic design-evidence component

## Overview

A developer evaluates a small matching web app against Vellum-approved design
targets and receives exact/tolerant per-constraint evidence through an installed
Servo gate. A wrong value or observed absent required element vetoes success;
missing, stale or unbound observations refuse. Raw implementation observations
remain separate from policy-interpreted results and any optional model score.

This implements proposed
[ADR-0044](../../decisions/adr-0044-required-constraints-cannot-be-averaged-away.md)
using [spec 035's required policy](../035-required-evidence-alongside-quality-scores/spec.md).
It serves evaluation compilation and reporting in
[the product vision](../../product-vision.md#two-phases-servo-compile-and-servo-run);
there is no `## Use cases` section, so `use_cases: []` is intentional.
Every slice ends with a real installed gate and a usable correction report.

## Ownership and upstream contract

| Owner | Authority |
|-------|-----------|
| Vellum | Source grounding, fresh approved reference captures, design targets, source identity and input-contract version/semantics. |
| Servo | Independently acquired implementation observations, approved comparison policy, deterministic comparisons, required composition and evaluation output. |
| Jig | Completion attestation and lifecycle gates consuming bound Servo evidence; not measurement or re-scoring. |

The upstream draft owners are Vellum ADR-0011
`docs/decisions/adr-0011-approved-design-contract-as-oracle-input.md` and
spec 013 `docs/specs/013-design-to-oracle-handoff/`, on
`vellum-oracle-contract` (publication pending when authored). The
[spec 013 link](https://github.com/PinkException/vellum/blob/vellum-oracle-contract/docs/specs/013-design-to-oracle-handoff/spec.md)
is a proposed dependency, not an accepted contract. Parent must pin its
published input-contract path/revision and Jig consumer artifact before
readiness. Servo does not invent JSON fields for that input or infer bindings
from design prose. Unsupported input versions/required types refuse.

The Jig consumer owner is proposed ADR-0065
`docs/decisions/adr-0065-attest-external-policy-verdict-delivered-revision.md`
and [spec 119 - mixed design-evidence attestation](https://github.com/ramboz/jig/blob/jig-mixed-evidence-attestation/docs/specs/119-mixed-design-evidence-attestation/spec.md),
with rich-policy, stale-delivery and legacy-opt-in slices. These are provisional
`--no-push` IDs on unpublished `jig-mixed-evidence-attestation`, not accepted
dependencies. Cross-project acceptance must reconcile these new owners,
not reinterpret or amend closed Jig spec 071.

Claude Design is the first source; Figma is deferred and not a prerequisite.
Later a source export alone can establish source-side grounding. It cannot
establish build identity, app observations, matching implementation or Jig DONE.

## Bounded first pilot

The first app is a self-contained matching web fixture based on Vellum's card,
not an existing production app. These are confirmed fixture target values,
**not an agreed final input JSON schema**:

| Constraint | Fixture target | Implementation observation |
|------------|----------------|----------------------------|
| Card width | 240 CSS px | Bound card's layout rectangle under approved viewport/device scale. |
| Content band | Height 44 CSS px, background `#1e2329` | Bound band's rectangle and resolved background color. |
| Title | 20 CSS px, weight 600, color `#eef1f4` | Visible bound title, resolved font size/weight/color. |
| Subtitle | 12 CSS px, weight 400, color `#8a929c` | Visible bound subtitle, resolved font size/weight/color. |
| Open state | Activating open changes subtitle text to `opened` | Actual app action and bound subtitle text after the approved settle condition. |

Confirmed source anchors are `#card`, `#title`, `#subtitle`, with sibling
`#open` **outside** the card reference crop. App bindings must be explicitly
confirmed, not assumed identical to source anchors. The open control can
drive state without being asserted visible in the reference PNG.

Source-grounding corrections supplied by the coordinating parent on
2026-10-14: old `base.md` calls the font Inter and the frame 240x140 while HTML
uses system-ui and a 44px content band; old `card.render.png` is a solid
240x140 dimension fixture, not a captured rendered title/subtitle. It is not a
valid visual target. The mentioned `card-open.render.png` is absent.
**Preserve those old fixtures**; require new Vellum-approved closed/open
captures scoped to `#card`, excluding `#open`, with measured crop/frame
dimensions and source typography. Do not infer font family, complete card
height or state references from the old redline/PNG.

Initially comparisons use normalized CSS pixels, resolved sRGB colors, numeric
font weight and exact approved state text. Proposed pilot tolerance is zero
for the named scalar properties after documented normalization; any practical
nonzero tolerance must be reviewed, justified and frozen, not silently added
to make a failure pass. Font-family metrics, hidden text presence, source
images and model estimates cannot substitute for the named app observations.

## Reuse and grounded seams

At main `067ef5092d3c3ebe7d55a4e27610d7fe1d688463`:

- Spec-oracle already exposes `command` and `generated_artifact_command`
  checks, explicit approval, colocated durable artifacts and an ordinary SEED
  component: `skills/spec-oracle/SKILL.md`, `oracle_overlay.py:80-99,185-280`.
  Use a bounded collector/comparator command through these seams. Do not add
  a parallel evaluator registry, new generic constraint DSL or new controller.
- Existing frozen-eval helpers provide hash validation, splicing and ledger
  primitives: `skills/_common/fidelity_eval.py:97-102,210-307,369-509`.
  Reuse applicable primitives without pretending a deterministic component
  has a judge model or n-sample statistical calibration.
- Design-eval records capture provenance, definition identity and per-screen
  shots: `skills/design-eval/score.py:1228-1280`; its capture dispatch supplies
  useful transport patterns. Reuse the capture seam where it fits, but app
  DOM/style/state observation and verified build identity are **new work**.
  Existing screenshots/ledger labels do not already provide this proof.

## Proposed evaluation-output envelope

Servo owns a **design-evidence envelope**, tentatively `schema_version: 1`,
`kind: design_evidence`, emitted as a versioned result artifact through the
existing command/generated-artifact seam and bound to the installed gate run.
This is neither **gate-payload schema version 2** (spec 035), nor existing
**design-eval policy schema version 2**, nor Vellum's input-contract version.
Exact field spellings/version are proposed until parent/owners reconcile.

| Required information | Proposed meaning |
|----------------------|------------------|
| Source identity | Vellum-approved input-contract version, source/export/capture hashes and approved target identity; never regenerated silently. |
| Policy/config identity | Frozen required IDs, source-to-app bindings, state actions/settle rule, normalization, units, tolerances, exclusions and collector/comparator artifact hashes. |
| Evaluated-build identity | Actual served immutable build artifact identity, verified against captured app runtime/build manifest. Git HEAD/URL alone is insufficient. |
| Invocation identity | Current gate/evaluation run ID, capture IDs and evaluator version; duplicate/partial/foreign-run artifacts refuse. |
| Raw observations | Per-bound-element presence/visibility, measured values/units, state/action observations, viewport/device scale/browser identity and relevant capture/artifact references with hashes. |
| Interpreted constraints | Stable source constraint ID, required flag, expected target, actual observation reference, comparator/tolerance, `pass|fail|unknown`, reason and correction-localization context. |
| Summary | `status: pass|fail|env_error`, `required_status: pass|fail|unknown`, counts/IDs, optional diagnostic metrics and evidence references. |

Here `pass` means complete required-constraint success for this component;
the overall gate still applies diagnostic quality policy. Observed absence of
the title after successful acquisition is `fail`; failed acquisition or an
unconfirmed title binding is `unknown` with `env_error`. Numeric anomalies
(non-finite values, invalid units, invalid color normalization), incomplete
state acquisition and unsupported comparisons cannot pass. Emit available raw
observations and specific reasons even when the summary refuses.

Gate validation checks source approval and hashes, frozen policy, evaluated
build manifest, exact required-ID coverage and current invocation before
accepting pass. Changing source, comparator, bindings, tolerance or exclusions
invalidates approval; changing build identity needs a fresh evaluation, not
reapproval of the design policy. App observations must come from the candidate
app, never be copied from source targets. A hash is an honest-drift check,
not adversary-proof attestation against a writer of all artifacts.

Propose colocating approved policy and evaluator artifacts with the pilot
spec's existing `oracle/<pilot-id>/` tree; invocation results/captures use
run-scoped paths and an append-only evidence ledger there. Temporary browser
state can remain under `.servo/`. Reuse spec-oracle's explicit shared-engine /
vendor portability choice. Do not mutate the approved source or use a last
successful result as the current evaluation.

## Later regional image evidence

036-02 may add a pinned deterministic raster comparison through the same
component and gate. Report raw per-region metrics separately from project-
approved thresholds and required outcomes; retain named local blockers and
correction artifacts (actual/reference crop, difference/overlay and affected
constraint/region). A good whole-image metric cannot hide a required regional
failure or missing region.

**Engine is not selected.** The public Impeccable candidate snapshot
`2f98774f86bc05563876643db37e6c37c322850f` reportedly exposes
`crates/comp-verbs/src/{comp_diff.rs,approved_comp.rs,build_phase.rs}` and an
`integrity_tests.rs` veto control. That supplied candidate lead is not a
verified dependency/calibration result here. A pinned isolated CLI comparison
is permitted as a later bounded validation; adoption of its phase workflow,
aesthetic defaults or whole runtime is out of scope. Parent/owner must supply
the canonical repository/license and verify the pinned source before adoption.
Parity on golden images establishes only implementation parity, not Vellum
metric accuracy or calibrated thresholds.

## Non-goals

No competing Vellum input schema, Figma prerequisite, generalized oracle-
accuracy claim, real-app acceptance claim, native Copilot Servo autonomy,
new registry/orchestration/DSL, mandatory model judge or selected image-engine
dependency. No source code or global plugin changes in this authoring PR.
Spec 030's suitability-signal work remains separate.

## Assumptions

- Vellum's approved draft will supply complete typed targets, source identities,
  fresh closed/open captures and explicit source/state/crop bindings. Parent
  must resolve this before 036-01 readiness; current fixtures are insufficient.
- A controlled pilot can verify the actually served build and acquire repeatable
  CSS/state observations. Demonstrate the build mismatch control and repeated
  runs, rather than treating a passed unit fixture as live capture proof.
- Candidate raster engines may be portable and their regional metrics may be
  meaningful on these inputs. 036-02 must independently validate portability
  and false-pass/false-block behavior before any required threshold adoption.

## Decomposition

First Data/Rules slice: one controlled card, both states, concrete exact/tolerant
observations, approved targets/policy and an installed required gate. Second
Data/Interface slice: the same user evaluates approved image regions, receives
local blockers and correction artifacts through that gate. Neither an input
parser nor an uninstalled metric helper is a standalone slice. No preliminary
spike; unresolved engine/calibration work is a readiness gate for the later
useful vertical slice.

## Slices

- [036-01 - bound card evidence through installed gate](slice-01-bound-card-evidence.md)
- [036-02 - regional image evidence and local corrections](slice-02-regional-image-evidence.md)
