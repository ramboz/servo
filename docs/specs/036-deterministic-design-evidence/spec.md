---
status: IN_PROGRESS
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
The component's `pass` is component success only. Completion authority is the
preserved **overall installed gate-payload policy verdict**, with component
records bound beneath it by run identity and content digest.

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
spec 013 `docs/specs/013-design-to-oracle-handoff/`, published in draft
[PinkException/vellum#50](https://github.com/PinkException/vellum/pull/50).
The [spec 013 proposal](https://github.com/PinkException/vellum/blob/7f4c06077318859c0aabec33d00c2eebd6cba74f/docs/specs/013-design-to-oracle-handoff/spec.md)
and [Proposed ADR-0011](https://github.com/PinkException/vellum/blob/7f4c06077318859c0aabec33d00c2eebd6cba74f/docs/decisions/adr-0011-approved-design-contract-as-oracle-input.md)
are pinned at `7f4c06077318859c0aabec33d00c2eebd6cba74f`, not an approved
executable input-contract revision. Parent must pin the later agreed
input-contract path/revision and Jig consumer artifact before
readiness. Servo does not invent JSON fields for that input or infer bindings
from design prose. Unsupported input versions/required types refuse.

The Jig consumer owner is proposed ADR-0065
`docs/decisions/adr-0065-attest-external-policy-verdict-delivered-revision.md`
and [spec 119 - mixed design-evidence attestation](https://github.com/ramboz/jig/blob/c118595ca122351f4f213d29ff5f06302321c2b0/docs/specs/119-mixed-design-evidence-attestation/spec.md),
with rich-policy, stale-delivery and legacy-opt-in slices. They are published
in draft [ramboz/jig#242](https://github.com/ramboz/jig/pull/242), pinned at
`c118595ca122351f4f213d29ff5f06302321c2b0`. ADR-0065 remains Proposed and
spec119 DRAFT, not accepted dependencies. Cross-project acceptance must reconcile these new owners,
not reinterpret or amend closed Jig spec 071.

Claude Design is the first source; Figma is deferred and not a prerequisite.
Later a source export alone can establish source-side grounding. It cannot
establish build identity, app observations, matching implementation or Jig DONE.

## Proposed ordering and preparation checkpoint

The coordinator proposes this order to avoid circular readiness. It is not
user/owner approval or a lifecycle shortcut:

1. **C0 (shared contract checkpoint):** parent/owners accept and align the
   Proposed decisions separately, pin input/output versions, serialization/
   digest domains and reviewed test vectors, required comparison inventory and
   served/current-delivery closure predicates. This is agreement/preparation,
   not runnable-all-consumers proof. Servo035-01 then implements its installed required gate using standalone
   existing-check fixtures; no Vellum/Jig DONE or design observer is needed.
2. **C1**, Vellum013-01's **approved-input preparation checkpoint**, owned by that
   slice's author and independent source approver, supplies real normal/open
   source artifacts, typed targets, crop/state bindings and content-bound
   approval while 013-01 can remain IN_PROGRESS. Source-only capture prep
   does not require Servo's future app observer, complete integration or
   Vellum013-02's state-handoff completion. Parent/owners must approve this
   checkpoint boundary in Vellum's open draft before relying on it.
   C1 preparation and standalone 035-01 can proceed independently after C0;
   neither needs the other's implementation completion.
3. With that approved input checkpoint and agreed identity/closure contract,
   Servo036-01 creates the matching app, observer and local-bundle transport,
   then proves actual served-bundle/current-delivery linkage and the installed
   overall gate. Those proofs are implementation deliverables, not readiness
   prerequisites. Missing required input approval still blocks this start;
   upstream slice DONE does not substitute for or gate the checkpoint.
4. Jig119 consumes preserved overall gate runs and their run/digest-bound
   component records without re-running or re-scoring, then Vellum013-01
   integration closes. Its 013-02 state handoff closes on its own criteria;
   fresh open input preparation here does not claim that handoff complete.

Servo035-02 follows 035-01 independently; Servo036-02 additionally needs
035-02. No integration completion is a prerequisite for drafting/agreeing the
shared input/output contract. No upstream slice dependency is inserted into
Servo's lifecycle frontmatter merely to stand in for an approved checkpoint.

## Bounded first pilot

The first app is a self-contained matching web fixture based on Vellum's card,
not an existing production app. These are confirmed fixture target values,
**not an agreed final input JSON schema**:

| Constraint | Fixture target | Implementation observation |
|------------|----------------|----------------------------|
| Content band | Width 240 CSS px, height 44 CSS px, background `#1e2329` | Confirmed band's layout rectangle and resolved background color under approved viewport/device scale. |
| Title | 20 CSS px, weight 600, color `#eef1f4` | Visible bound title, resolved font size/weight/color. |
| Subtitle | 12 CSS px, weight 400, color `#8a929c` | Visible bound subtitle, resolved font size/weight/color. |
| Normal text | Title `Trailhead`, subtitle `hiking route planner` | Exact visible bound normal-state text, not source text substituted as an app observation. |
| CSS family declaration | Vellum's approved normalized computed CSS-family declaration | Normalized app `getComputedStyle(...).fontFamily`; no claim about the font face actually used to render glyphs. |
| Open state | Activating open changes subtitle text to `opened` | Actual app action and bound subtitle text after the approved settle condition. |

Parent verified the three source text literals; that verifies fixture content,
not owner acceptance of targets or tolerance policy. Approved C1 input must
carry them and the declared CSS-family target explicitly.

The [Vellum C0 appendix at `453945c`](https://github.com/PinkException/vellum/blob/453945cdc0402841b6d1886b15fdbdcf81f74c98/docs/specs/013-design-to-oracle-handoff/input-contract-pilot.md)
names `normal-band-width` and `open-band-width` in its required state
inventories. Both must observe the confirmed source `#band` and its approved
app binding, once each in the corresponding state. `#card` is the capture root,
not a substitute for that band binding; equal declared widths do not make the
elements interchangeable. Any extra card-width observation is separately
classified as a non-required diagnostic, cannot satisfy a band-width ID, and
cannot replace or alter Vellum's approved required inventory.

Confirmed source anchors are `#card`, `#band`, `#title`, `#subtitle`, with sibling
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
height or state references from the old redline/PNG. Computed CSS-family
declaration equality is supported by the proposal; actual font-face/glyph
metrics are not inferred from it.

**Coordinator-proposed tolerance, not owner-approved:** compare derived
`getBoundingClientRect()` geometry in CSS pixels with inclusive absolute
error <=1 CSS px for required band width/band height. Keep zero tolerance for declared
font size/weight, exact visible text and normalized color/CSS-family strings.
Record raw geometry without rounding away failures; test exact +/-1px
boundaries and immediately outside them. Owner review/approval must pin
normalization and these tolerances in policy before scoring; a different
approved choice needs updated controls, not a runtime fallback.

Normalize resolved colors to exact sRGB RGBA including alpha, declared sizes
to CSS px and weights to numeric values without inferring a rendered font
face. CSS-family normalization must preserve family order and token semantics,
including generic `sans-serif` versus the named family `"sans-serif"`; these
are not equivalent tokens. Vellum owns the normalizer and its corrected
vectors; a quote-stripping rule that equates these tokens cannot clear C0.
normal text uses the approved text rule, not an ad hoc fuzzy match. Required
unsupported properties or omitted comparison/tolerance policy remain
`unknown`/refusal, never dropped. In particular, omitted geometry tolerance
does not default to zero and override Vellum's approved +/-1px policy. Exact
comparisons must also be explicit, not a catch-all for absent policy. Hidden text,
source images or model estimates cannot replace named app observations.

## Identity, approval and build-input closure

Agree this bounded identity contract **before readiness**, then build and prove
the acquisition/transport in 036-01. These are coordinator-proposed definitions
pending owner/cross-project acceptance, not existing runtime capabilities:

| Identity/closure | Proposed first-pilot definition |
|------------------|---------------------------------|
| Approved source | SHA-256 of the exact Vellum input artifact bytes and each declared source/export/normal/open reference artifact; version, state/crop/binding metadata and approval record must bind that complete declared source set. Vellum owns its schema and canonicalization; Servo does not reinterpret its JSON into a competing input format. |
| Servo policy/config | SHA-256 of schema/version-named canonical JSON (UTF-8, sorted keys, compact separators, finite numeric values only) and separate byte hashes of collector/comparator/install artifacts. Include every required ID, binding, state action/settle rule, normalization, tolerance/exclusion, viewport/device scale and closure/transport rule; approval names the digest set, author and distinct reviewer/owner, not just a status flag. |
| Candidate input closure | Explicit normalized relative POSIX paths and byte hashes for every transitive local build input: HTML/CSS/JS, local font/image/data assets, build script/config and relevant lockfile. A sorted canonical manifest binds the complete declared set; missing/extra reachable inputs, path escapes or unlisted inputs refuse. Checkout/commit labels are diagnostic only. |
| Evaluated/current delivery | The immutable output bundle manifest lists every served HTML/CSS/JS/font/image/data resource by normalized relative path and byte hash. Hash its canonical manifest and verify actual resource bytes; independently identify the current delivery's bundle and compare content closure/digest rather than accepting an echoed build ID. |
| Preserved evidence | Each immutable observation/capture/component record has a content digest and current gate run ID. The overall gate record binds approved source/policy, input/output closure and component digests for that invocation; Jig consumes that preserved record plus independent current-delivery identity. |

Proposed Servo digest domains are version-specific labels followed by a newline
and the defined content bytes: `servo-policy-v1`, `servo-input-closure-v1`,
`servo-output-closure-v1`, `servo-design-evidence-v1` and `servo-gate-policy-v2`.
Use SHA-256 over those exact preimages; raw capture/file hashes are byte hashes.
Vellum defines its own input/source digest domain. Self-digest fields and
approval metadata are excluded from a content preimage and represented in
separate binding records; semantic policy/evidence fields are not excluded.
Canonical manifests sort entries by normalized path; semantic arrays, including
CSS-family order, preserve their order. C0 must approve exact serialization/
numeric/string rules, digest exclusions and positive/negative test vectors
before treating these proposed domain names as an interoperable contract.
Test vectors must cover changed artifact/required membership, reordered keys,
semantic array order, non-finite values and missing tolerance. Unsupported
or unknown semantic fields refuse rather than being omitted from a digest.

**Narrow proposed transport:** a static immutable local fixture bundle served
only by the bounded collector's controlled read-only loopback server. Resolve
all resources from the declared bundle, exclude symlink/path escapes,
external network resources, mutable API/backend output and dynamic build-at-
serve behavior. An empty set for an absent input category must be explicit.
The collector verifies browser-loaded response bytes against the output
manifest (including redirects/caches or refusing unsupported paths), links
them to that capture's state/run, and independently hashes the selected current
delivery files. A manifest endpoint that merely echoes the expected ID or
matching local HEAD is insufficient. No arbitrary HTTP app provenance is
claimed; unsupported transport/resource closure refuses.

The input/output closure may change for a new candidate without reapproving
design targets; every build/evaluation/delivery binding must be refreshed.
Policy/source changes require explicit reviewed reapproval. No deterministic
observation record is mutated to fit later policy; a new evaluation produces
new bound records. A local fixture's complete declared closure and controlled
transport are a bounded trust model, not adversary-proof remote attestation.

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
| Evaluated-build identity | Verified immutable input/output bundle closure and actually loaded resource-byte identity, linked to independently identified current delivery. Git HEAD, URL or self-echoed manifest ID alone is insufficient. |
| Invocation identity | Current gate/evaluation run ID, capture IDs and evaluator version; duplicate/partial/foreign-run artifacts refuse. |
| Raw observations | Per-bound-element presence/visibility, measured values/units, state/action observations, viewport/device scale/browser identity and relevant capture/artifact references with hashes. |
| Interpreted constraints | Stable source constraint ID, required flag, expected target, actual observation reference, comparator/tolerance, `pass|fail|unknown`, reason and correction-localization context. |
| Summary | Component-only `status: pass|fail|env_error`, `required_status: pass|fail|unknown`, counts/IDs, optional diagnostic metrics and evidence references; not the overall completion verdict. |

Here `pass` means complete required-constraint success for this component;
the overall gate still applies diagnostic quality policy. Jig must attest the
**overall gate-payload policy verdict** with every required condition conclusive-
pass, validated record digests/run links and current-delivery binding, not this
component summary alone. Integration control: component `pass` plus quality
below threshold is overall `fail`/exit1, and Jig119 cannot attest. Observed absence of
the title after successful acquisition is `fail`; failed acquisition or an
unconfirmed title binding is `unknown` with `env_error`. Numeric anomalies
(non-finite values, invalid units, invalid color normalization), incomplete
state acquisition and unsupported comparisons cannot pass. Emit available raw
observations and specific reasons even when the summary refuses.

Gate validation checks content-bound source/policy approval, immutable bundle
closure/served-byte/current-delivery linkage, component record digests,
exact required-ID coverage and current invocation before
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
  fresh normal/open source captures and explicit source/state/crop bindings at
  the proposed 013-01 approved-input checkpoint while IN_PROGRESS. Approve the
  checkpoint and real artifact input before 036-01 readiness, not upstream DONE.
- Owners approve the proposed +/-1 CSS px geometry/zero declared-size-weight/
  exact normalized string/color policy, missing-tolerance refusal, digest
  definitions/test vectors and immutable local-bundle closure.
  Those are recommended choices, not user-approved facts.
- A controlled local fixture can verify actually served/current-delivery bytes
  and acquire repeatable CSS/state observations. The observer/transport and
  live mismatch/replay controls are 036-01 implementation work, not prebuilt
  readiness artifacts or a claim of arbitrary HTTP provenance.
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
