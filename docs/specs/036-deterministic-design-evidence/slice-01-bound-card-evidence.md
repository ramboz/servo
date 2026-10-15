---
status: DRAFT
kind: feature
dependencies: [035-01, adr-0044]
last_verified:
frame_review: true
arch_review: true
---

## Slice 036-01 - bound-card-evidence

**Goal:** A developer runs the installed Servo gate on a self-contained matching
card app and gets per-constraint observations, a required veto on a wrong card,
and bound evidence that Jig can later attest.

**DoR:**
- 035-01 DONE and ADR-0044 accepted after cross-project alignment.
- Published Vellum spec 013 input contract accepted by its owner and pinned by
  path/revision; confirmed typed constraints and app/source/state bindings.
- New approved closed/open source captures scoped to `#card` are available;
  old solid 240x140 PNG and absent open-state PNG are not used as targets.
- Parent pins the Jig attestation consumer and reconciles exact Servo output
  fields/version. No accepted cross-project schema is claimed by this draft.
- Self-contained candidate app/serve command, independent observation command,
  verified served-build manifest and supported browser capture are available.

**Acceptance Criteria:**

1. **Whole installed flow.** A documented bounded card flow consumes Vellum-
   approved targets, confirms source-to-app bindings, explicitly reviews and
   freezes project-owned policy, installs ordinary spec-oracle command/
   generated-artifact evidence and invokes real `gate.py <target> --json`.
   Matching closed and opened card states return 0 with complete required
   evidence. Installing a draft/unapproved component returns 2.
2. **Confirmed properties.** The app observations independently measure card
   width 240 CSS px; band height 44 CSS px/background `#1e2329`; visible title
   20px/600/`#eef1f4`; visible subtitle 12px/400/`#8a929c`. The approved
   normalization and tolerance are applied and included in the result.
   Do not assert font family or a 140px card height from old redlines.
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
   An observation outside an approved tolerance fails; exact boundary cases
   match the frozen comparator definition.
5. **Unavailable evidence.** Unknown/ambiguous app binding, unsupported required
   target/type/version, absent source approval, unavailable browser/app,
   missing/partial observations, failed state acquisition, invalid units/
   non-finite values or mismatched source/policy/build/run identities yields
   2 with `unknown` and a concrete reason. Observed element absence is
   separately 1, not misclassified as missing capture. Duplicate/extra/
   omitted required IDs refuse; known failures remain visible beside refusal.
6. **Freeze and running-build proof.** Source target/capture, policy/binding/
   normalization/tolerance/exclusion and evaluator artifact edits invalidate
   approval. A collector proves the served immutable build manifest matches
   the captured app, not just local HEAD or URL; a substituted running build
   refuses. A new legitimate candidate build uses fresh observations without
   rewriting design targets. Replay an old passing result, wrong state or
   another run's capture: the installed gate refuses.
7. **Inspectable output.** The proposed design-evidence envelope contains
   every approved constraint, raw observations distinct from comparisons,
   actual/expected values, reasons, capture/artifact hashes and source/config/
   build/evaluator/run identities. Repeat evaluation against a fixed build
   yields the same comparisons; timestamps/run IDs may differ. No optional
   quality/model score can overwrite required outcomes.
8. **Ordinary installation and bounded claims.** Reinstall/uninstall and
   shared-engine/vendor paths follow existing Servo installation semantics;
   generated supported packages can run the documented collector/comparator
   without Claude Design/Figma network access. No new registry/DSL/controller.
   User-facing reports explicitly say this proves the bounded fixture,
   not production acceptance, general oracle accuracy or Jig DONE.

**DoD:**
- [ ] Real served-app/capture -> frozen component -> installed gate controls
      cover all criteria with witnessed failures and corrected passes.
- [ ] Per-constraint/identity/refusal cases have focused regression tests.
- [ ] Independent compliance/craft/architecture reviews pass.
- [ ] Output/command documentation, deviation log and reconciliation complete;
      no closed records amended or unsupported host claims added.

## Assumptions

- Vellum will provide approved fresh references and complete source/state
  bindings; current fixture redlines and solid PNG do not meet the prerequisite.
- A supported local browser can produce repeatable card observations tied to
  the served build. This must be demonstrated live before acceptance.

**Anti-horizontal-phasing check:** The user can evaluate and repair a complete
matching card through the installed gate; the collector is not merely a
standalone measurement helper waiting for later integration.

### Close-out (post-DONE)

- [ ] Regenerate board and record exact pilot scope and upstream contract pin.
- [ ] Reconcile live skill/output/install docs; parent owns cross-project attestation.
