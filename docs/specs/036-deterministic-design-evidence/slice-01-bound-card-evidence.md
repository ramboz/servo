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

### Implementation checkpoint (not reconciliation)

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

### Close-out (post-DONE)

- [ ] Regenerate board and record exact pilot scope and upstream contract pin.
- [ ] Reconcile live skill/output/install docs; parent owns cross-project attestation.
