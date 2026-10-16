---
status: IN_PROGRESS
kind: feature
dependencies: [035-01, adr-0044]
last_verified:
frame_review: true
arch_review: true
claimed_by: servo-live-card-evidence
---

## Slice 036-01 - bound-card-evidence

**Goal:** A developer runs the installed Servo gate on a self-contained matching
card app and gets per-constraint observations, a required veto on a wrong card,
and bound evidence that Jig can later attest.

**Readiness checkpoint (2026-10-15):** Accepted C0 and independently approved C1
release-r3 are pinned in `plan.md`, with exact package/helper hashes and an own
browser launch probe. 035-01 is DONE at the clean pinned base. The coordinator
assigned the necessary opt-in generic artifact/refusal carrier seam. The owner
selected current Opus via Claude CLI for eight first-calibration invocations;
live capture, quality, closure and mutation proof remain implementation work.
036-02 remains outside this assignment.

**DoR:**
- 035-01 DONE and ADR-0044 accepted after cross-project alignment.
- Published Vellum spec 013 input contract accepted by its owner and pinned by
  path/revision; agreed typed constraints and planned app/source/state bindings.
- C0 pins accepted/aligned decisions, exact version/serialization/digest domains
  and reviewed test vectors, required comparison inventory and served/current-
  delivery closure predicates. It does not require runnable consumers.
- Vellum013-01's author/independent source approver supply C1, a real approved-input
  checkpoint: fresh normal/open source captures scoped to `#card`, target/state/
  crop metadata and content-bound approval. That slice may be IN_PROGRESS;
  neither 013-01 DONE nor 013-02 state-handoff completion is required. Parent
  and Vellum owner approve this checkpoint boundary; old solid 240x140 PNG and
  absent open-state PNG are not used as targets.
- Parent pins the Jig attestation consumer and reconciles exact Servo output
  fields/version. No accepted cross-project schema is claimed by this draft.
- Owners agree canonical source/policy approval identities, complete local
  build-input/output closure, supported browser/transport boundary and pilot
  normalization/tolerances as defined in spec.md. The matching app, observer,
  controlled server and actual served/current-delivery proof are built by this
  slice; they need not exist before readiness.

**Acceptance Criteria:**

1. **Whole installed flow.** A documented bounded card flow consumes Vellum-
   approved targets, confirms source-to-app bindings, explicitly reviews and
   freezes project-owned policy, installs ordinary spec-oracle command/
   generated-artifact evidence and invokes real `gate.py <target> --json`.
   Matching normal and opened card states return component `pass`; when
   quality also passes, the overall installed gate returns 0 with complete
   required evidence. Installing a draft/unapproved component returns 2.
2. **Confirmed properties.** The app observations independently measure
   band width 240 CSS px/height 44 CSS px/background `#1e2329` through confirmed
   source `#band` and its approved app binding in each state; visible title
   20px/600/`#eef1f4`; visible subtitle 12px/400/`#8a929c`. The approved
   normalization and tolerance are applied and included in the result. Exact
   normal title `Trailhead`, normal subtitle `hiking route planner`, opened
   subtitle `opened` and approved normalized computed CSS-family declaration
   are required; declaration equality makes no actual rendered-font-face claim.
   No 140px card height or Inter value is inferred from old redlines.
   `normal-band-width` and `open-band-width` each reference their own bound band
   observation once; a `#card` width or separately classified non-required
   card-width diagnostic cannot substitute for either approved required ID.
3. **State and crop.** The confirmed open action changes observed subtitle
   text to exactly `opened` under a bounded approved settle rule. Capture
   provenance reports closed/open state and measured card crop. Sibling
   `#open` stays outside the source reference crop; no in-frame control
   visibility assertion or target expansion is inferred.
4. **Discriminating negatives.** Remove `#title` within the bound app frame,
   make title font size 24px instead of 20px, and break the open action in
   separate builds. Each produces an observed named required failure, raw
   actual/expected values and gate exit 1 even with quality 0.99 and
   `THRESHOLD=0`. Hidden required title text does not satisfy visible title.
   Add wrong normal title/subtitle, changed CSS-family declaration and changed
   color controls. For proposed inclusive +/-1 CSS px geometry, both exact
   boundaries pass, +/-1.01px fail without rounding. Declared title size20.01px
   fails under proposed zero size tolerance; weight, normalized color/text/
   family controls follow exact approved comparisons. Owners must approve
   this policy before scoring; unsupported required properties refuse.
   Keep `#card` width at 240px while changing only the bound band width to
   242px: each affected state reports its band-width ID failing and gate exit1
   despite quality0.99/`THRESHOLD=0`. Required geometry boundary controls
   measure the band, not the card. Generic `sans-serif` versus named
   `"sans-serif"` remains a changed CSS-family token control, not a normalized
   match or a rendered-font-face test.
5. **Unavailable evidence.** Unknown/ambiguous app binding, unsupported required
   target/type/version, omitted comparison/tolerance, absent source approval, unavailable browser/app,
   missing/partial observations, failed state acquisition, invalid units/
   non-finite values or mismatched source/policy/build/run identities yields
   2 with `unknown` and a concrete reason. Observed element absence is
   separately 1, not misclassified as missing capture. Duplicate/extra/
   omitted required IDs refuse; known failures remain visible beside refusal.
   Omitted tolerance never becomes default zero or drops a required comparison.
   A missing/unconfirmed band binding or card-only width record cannot establish
   required band width and returns unknown/refusal, even when card width is240px.
6. **Freeze and running-build proof.** Source target/capture, policy/binding/
   normalization/tolerance/exclusion and evaluator artifact edits invalidate
   approval. The collector implements the agreed local immutable bundle
   transport and verifies actual browser-loaded bytes against complete input/
   output closure plus independently hashed current delivery; local HEAD,
   URL or self-echoed manifest ID is not proof. Substituted served resource,
   unlisted/external/mutable dependency, wrong selected current delivery and
   incomplete build inputs refuse. A new legitimate candidate build uses
   fresh observations without rewriting design targets. Replay an old passing
   result, wrong state or another run's capture: the installed gate refuses.
7. **Inspectable output.** The proposed design-evidence envelope contains
   every approved constraint, raw observations distinct from comparisons,
   actual/expected values, reasons, capture/artifact hashes and source/config/
   build/evaluator/run identities. Repeat evaluation against a fixed build
   yields the same comparisons; timestamps/run IDs may differ. No optional
   quality/model score can overwrite required outcomes. Raw observations are
   immutable; the gate record binds component/capture digests and the same run.
   Change approved policy only through review/reapproval and fresh evaluation,
   not by rewriting collected facts.
8. **Ordinary installation and bounded claims.** Reinstall/uninstall and
   shared-engine/vendor paths follow existing Servo installation semantics;
   generated supported packages can run the documented collector/comparator
   without Claude Design/Figma network access. No new registry/DSL/controller.
   User-facing reports explicitly say this proves the bounded fixture,
   not production acceptance, general oracle accuracy or Jig DONE.
9. **Overall completion authority.** Preserve a run with deterministic component
   `pass` but quality below threshold: the installed gate is `fail`/exit1
   (`quality_below_threshold`), not completion. Also preserve overall pass and
   required-fail/refusal controls with digested component records. Jig119's
   integration must attest/refuse these preserved overall gate runs without
   re-running/re-scoring; Servo's record-producing proof occurs here, Jig's
   attestation proof in Jig119 and Vellum's integration close-out afterward.
   Servo validates the producing gate and handoff here; a completed Jig119
   attestation runtime is not a prerequisite for 036-01 DONE.

**DoD:**
- [ ] Real served-app/capture -> frozen component -> installed gate controls
      cover all criteria with witnessed failures and corrected passes.
- [ ] Per-constraint/identity/refusal cases have focused regression tests.
- [ ] Independent compliance/craft/architecture reviews pass.
- [ ] Output/command documentation, deviation log and reconciliation complete;
      no closed records amended or unsupported host claims added.

## Assumptions

- Vellum013-01 can prepare approved normal/open input while IN_PROGRESS,
  independently of the new observer and final integration. Owner approval of
  this checkpoint remains necessary; upstream DONE is not the gate.
- Owners approve the proposed geometry/declared-value/string normalization
  policy and immutable local-bundle closure boundary before readiness.
- A supported local browser can produce repeatable card observations tied to
  actually served/current delivery bytes. Build/prove this during implementation,
  not as a prerequisite for writing the observer.

**Anti-horizontal-phasing check:** The user can evaluate and repair a complete
matching card through the installed gate; the collector is not merely a
standalone measurement helper waiting for later integration.

### Final-source proof checkpoint (2026-10-15)

The coordinator handed off the existing IN_PROGRESS work for final closeout on
integration parent `6d5e5b66c7f3ed796c7cbbbafdb84012e2e29cb5`. All eight producer
files at that parent are byte-identical to sealed source `6cc759e807cab5411363b44c19c58e7a457b3715`.
[The final-source receipt](implementation-receipt.md) pins the immutable
678-artifact index, three actual live outcomes, eleven no-judge controls and
combined-source validation. Fresh full reviews and normal transitions determine
the current frontmatter status. Earlier checkpoints below retain their original
nonpassing state and source-epoch limits; they are historical, not superseded
claims about final-code acceptance.

Fresh compliance/craft/architecture all returned `needs-changes` for the
reproduced ancestor-overflow required-title visibility defect. The coordinator
authorized the [narrow capture/test correction](visibility-correction-receipt.md);
its witnessed red/green, independent source/driver reviews and actual installed
diagnostic veto/restoration pass within their stated scope. Full-slice reviews
remain nonpassing pending affected actual-quality proof. No lifecycle gate is
waived and the earlier live runs are not relabeled as corrected-source proof.

### Historical implementation checkpoint (not reconciliation)

036-01 remains IN_PROGRESS. The first Opus attempt's expired-OAuth response
is preserved. Following explicit replacement authorization, attempts2-9
produced actual overallpass0, all28requiredpass and genuine quality0.9675
against default0.8. A fixed, preselected misalignment on attempts10-17 retained
all28 required facts but scored0.512065 at the unchanged0.8, preserving actual
component-pass/quality-fail/overallfail1. Native replies report `claude-opus-5`;
new definitions freeze that concrete observed CLI ID.
The owner authorizes necessary further bounded pilot calls, not adaptive
search or policy tuning. Each batch documents its purpose, inherits all
consumed claims and allocates exactly8 judgments.

Twenty actual no-judge diagnostic controls are preserved as an earlier source
epoch (twelve veto1, eight refusal2; no overall pass). Their0.99 is explicitly
synthetic negative-control quality, not live fidelity. Matching required
observations retain component pass but unavailable quality/overall2.
Later witnessed fixes bind the default quality threshold, separate
gate-owned acquisition claims/receipts, reject relabelled cached captures,
and distinguish hidden descendant text from visible boxless wrappers.
Historical records are not rewritten as final-code proof.

The durable compliance checkpoint is `needs-changes`. Final-code source-epoch
consolidation, complete controls/package/uninstall acceptance and
compliance/craft/architecture/reconciliation reviews remain open.
This is not REVIEWED, RECONCILED, DONE or Jig attestation.
No 036-02 implementation or closed-record amendment occurred.

### Historical execution-closure recovery checkpoint (2026-10-15)

The exact 74,424-byte dirty patch from base
`5440b63458bf862d4fe0b19e274db18c38c170aa` is preserved in `b73306c`.
All eleven applied/staged source hashes matched the race-checked snapshot.
Patch SHA-256:
`7ed90f2096e60cd8815e28274ebacaf89c7976dcee00871d522f267eda14fdc6`.
Subsequent focused red-to-green controls close unimported Python-extension
native linkage, native CLI launcher symlinks, unrelated credential forwarding,
cross-state sealed-image mutation, original PNG/observation mutation during
quality, and Playwright Node startup overrides. Public schemas and the pure
output-reference API are unchanged; official host packages were regenerated.

Independent bounded source/definition and staged-driver reviews passed for
`closure-preflight-v3`. Its ordinary no-judge install/reinstall preserved full
oracle hash `37a3d5e5e6c442fdf49526416afded0e6ee4ee77d9a8e1a767e64f1dccc3e108`.
Installed controls observed all28requiredpass/qualityunavailable/exit2,
real-quality-wrapper drift refusal2, Node-startup refusal2, and font24
26pass/2fail/exit1 at `THRESHOLD=0`; current-delivery readback passed.
Its complete 3,887-file runtime inventory, approvals and frozen-context/control
receipts remain in recovery session artifacts, not the runtime package.

Final lint-only import/string-formatting/test-binding cleanup passed scoped
lint, 261 focused pytest cases and all47 card unittests including all10 actual
browser tests. Changed helper bytes are not relabelled as v3 proof.
Fresh `closure-preflight-v4` policy identity is
`sha256:db6b7fa969f51f540577f45aa0b0cd1c6a268ac01e3bf8ecdab36e2966c6268d`.
Its exact-byte review/reseal/preflight remains open: independent refresh
attempts encountered model HTTP408/connection timeout and unavailable artifact
access approval, not code or judge failures. This source checkpoint does not
claim that final v4 definition is approved.

This recovery made zero live judge calls; inherited actual calls remain25.
Historical samples and prior control epochs are unchanged. Trusted-local
closure only: no hostile-writer/full-host attestation, whole-slice compliance,
REVIEWED, RECONCILED, DONE or renewed live-call allowance is claimed.

### Deviation log

Prepared during closeout; final reconciliation review and lifecycle acceptance
are still pending. Original ACs above are preserved.

- The assigned ordinary command output/refusal carrier and pure consumer
  readback use existing spec-oracle/required-runtime seams. The combined
  integration parent includes the completed 035-02 consumer; no new registry,
  controller, generic constraint language or cross-project completion
  dependency was added.
- Earlier review findings about threshold binding, acquisition ownership,
  visible descendant text and the exact execution closure received witnessed
  fixes in their own source epochs. The prior unsuccessful reviews, expired
  authentication attempt and actual runs remain historical; they were not
  rewritten as proof that the final guards already existed.
- The three actual 6cc759e runs proved distinct bounded overall outcomes.
  Full review nevertheless reproduced ancestor-overflow title invisibility.
  The coordinator then explicitly authorized the capture/test-only correction.
  Its real red/green, independent narrow source/driver reviews, installed
  synthetic-quality veto and restored required-pass/unavailable-quality
  control are recorded separately. Actual-quality proof on that corrected
  source and fresh full verdicts remain necessary; diagnostic 0.99 never
  becomes live fidelity.
- Before new 09f judge calls, the coordinator assigned the existing
  quality-budget seam to permit explicitly approved whole eight-judgment
  batches under one frozen definition for a fresh changed-build A/B pair.
  Default one-batch behavior, eight judgments per run, prior history,
  monotonic claims and exhaustion remain strict. The cap/purpose remain
  frozen; raising them still requires ordinary reapproval. This is not a new
  judge framework, score cache or generalized convergence claim.
- The approved inclusive geometry comparison is unchanged. Exact +/-1.01px
  arithmetic controls and measured +/-1.02px browser controls distinguish
  policy from Chromium layout quantization; no measured failure is rounded
  into a pass. The title-size 20.01px control retains zero tolerance.
- The visibility correction rejects fully clipped rectangular text while
  allowing surviving positive-area partial visibility. It does not certify
  full glyph visibility, arbitrary masking/transforms or general occlusion.
  No source design, comparison tolerance, exclusion, threshold, sample policy
  or frozen model was changed to improve a score.
- This closeout made zero live judge calls. Owner-level consumed history
  stays attached to each proof epoch; a new target or unused diagnostic
  allowance does not grant new judge authorization.

### Reconciliation sweep

Prepared dispositions; the independent reconciliation reviewer must verify
these against the final fixed-epoch proof before RECONCILED.

| Surface | Disposition |
|---|---|
| Acceptance criteria, plan and tasks | Updated current checkpoints and explicit pending proof/review work; original nine ACs and historical nonpassing checkpoints preserved. Downstream Jig/Vellum tasks are explicitly owned/deferred, not hidden prerequisites. |
| Output/command/install guidance | Updated walkthrough and live guidance for exact driver sealing, ordinary shared/vendor installation, pure readback, source epochs and honest 0/1/2 authority. Official hosts are regenerated, never hand-edited. |
| Architecture and decisions | Updated live bounded-observer description with source citations. No module boundary or new load-bearing alternative was introduced by the visibility correction; Accepted ADR-0044 remains the existing authority. No new ADR or amendment to Accepted/DONE records is needed. |
| Conventions | No-op: no convention change was requested or made. |
| Inbox | No-op: this plugin-only project has no `docs/inbox.md`; remaining 036-02 and cross-project work stays in its existing owner records. |
| Memory | Updated through `memory.py` with the overflow visibility/proof-epoch lesson; existing ownership/threshold/history lessons retained. Team-context bootstrap was skipped as unrelated to this lane. |
| Primer/scaffold surfaces | No root AGENTS/CLAUDE primer exists in this plugin-only scaffold. 036-02 remains DRAFT, so this is not whole-spec compress-on-closeout. No scaffold template or global plugin change was needed. |
| Use-case trace | Advisory helper reports no-op because the vision has no `## Use cases` section; no new use case was invented. |
| Closed-spec drift | No closed spec/slice, DONE035 record, Accepted ADR or historical approval was amended. Earlier open 036 checkpoints remain explicitly historical. |
| Status board | Derived with `workflow.py status-board`, not hand-edited; 036 remains IN_PROGRESS while full evidence gates are open. Candidate-selection telemetry reflects the actual richer craft/arch selections. |
| Final proof and verdicts | Pending fixed-epoch actual proof and normal full compliance/craft/arch/reconciliation; neither narrow patch passes nor peer lifecycle completion substitutes. |

### Leanness sweep

The visibility correction adds one local rectangle-intersection predicate and
two focused browser regression methods in existing files. The separately
authorized repeated-run allowance stays in the existing quality helper, with
private durable claim accounting rather than a new registry or controller.
Neither adds a runtime module, policy/config field or platform. Source/input/output
and current-delivery validation retain the existing approved carrier and pure
consumer API. Detailed receipts are audit documentation, not installed runtime
inputs. No out-of-spec UI/product decision was settled; no lightweight
decision record or broader architecture proposal is introduced.

### Close-out (post-DONE)

- [ ] Regenerate board and record exact pilot scope and upstream contract pin.
- [ ] Reconcile live skill/output/install docs; parent owns cross-project attestation.
