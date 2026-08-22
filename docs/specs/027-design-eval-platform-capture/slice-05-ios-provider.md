---
status: IN_PROGRESS
dependencies: [adr-0032, 027-02, 027-04]
last_verified: 2026-08-21
claimed_by: claude/027-01-342c59
---

## Slice 027-05 — blessed iOS provider

**Goal:** Ship a built-in **iOS** capture provider — `xcrun simctl io <target>
screenshot` for pixels, an optional per-screen deep-link seed, and chrome-frame
normalization to the reference's logical frame — so a native iOS/SwiftUI UI can
be scored against the same mockups. Degrades honestly to `env_error` when the
simulator/`simctl` is absent.

**Scope note:** the second blessed native built-in, **parallel in shape to the
Android provider (027-04)** — same per-platform-seeding + frame-normalization
contract (ADR-0032 §4/§5), reusing the shared stdlib PNG cropper (`pngcrop.py`)
and the `capture_command` ledger identity. Registers one provider (`ios`) into
the 027-02 seam. Complex flows stay the job of the 027-03 `command` provider.

**DoR:**
- ✅ 027-04 shipped the native-provider pattern (device resolution, deep-link
  seed, stdlib crop, fail-closed, `capture_provider`/`capture_command` ledger
  identity, `not_attested` provenance) and the reusable `pngcrop.py`. iOS is the
  same shape with `xcrun simctl` in place of `adb`.
- ✅ Capture mechanics probe-verified (2026-08-21): `xcrun simctl io <target>
  screenshot <file>` writes a PNG to a **file path** (unlike adb's stdout) — so
  the provider writes to the retained shot path, then crops it in place.
  `<target>` is a udid or the literal `booted` (simctl's single-booted-device
  selector). Deep-link seed is `xcrun simctl openurl <target> <uri>`.
- ⚠️ **Environment limitation (probed, not assumed):** this dev machine has
  Command Line Tools only — **no full Xcode, no `simctl`, no iOS simulator**
  (`xcrun --find simctl` → not found). So unlike 027-04, the **live-simulator
  smoke is DEFERRED** to a machine with Xcode. This slice is validated to the same
  bar as 027-04's *committed CI tests* (stubbed `simctl` + the synthetic
  real-encoder PNG fixture); the crop itself is already pixel-exact-tested by
  027-04's `PngCropTests`. This is a disclosed, human-approved trade-off, not a
  hidden gap.
- ✅ `capture.ios` is environmental (ADR-0032 §6) — not hashed, never a staleness
  trigger. No ADR needed.

**Acceptance Criteria:**

1. **iOS provider selected; per-screen screenshot.** `capture.transport: "ios"`
   captures each screen via `xcrun simctl io <target> screenshot <shot_path>`,
   writing the PNG to the retained, stamped path under `shots/` (027-01 plumbing,
   path depth unchanged). Target resolution precedence: `capture.ios.udid` →
   `SERVO_DESIGN_EVAL_IOS_UDID` → the literal `"booted"`. `xcrun` is found on
   `PATH` or via `SERVO_DESIGN_EVAL_XCRUN_BIN`; **absent `xcrun` fails closed to
   `env_error`** (rc 2) before any capture.
2. **Chrome-frame normalization by configured insets.** The screenshot is cropped
   in place by `capture.ios.crop` = `{top,bottom,left,right}` (pixels, default 0)
   via the shared stdlib cropper (`pngcrop.py`). An out-of-bounds crop
   (`top+bottom ≥ height`) or a non-integer inset fails closed to `env_error` —
   never a zero-area or garbage frame.
3. **Per-screen state seeding (optional deep link).** If a screen declares
   `deeplink: "<uri>"`, the provider runs `xcrun simctl openurl <target> <uri>`
   and waits a bounded settle before the screenshot. Absent → it screenshots the
   current state (positioning is the project's responsibility; complex flows use
   the `command` provider). State equivalence to the web seed is project-authored,
   not certified (ADR-0032 §4).
4. **Fail closed + identity in the ledger.** `xcrun` absent, a non-zero/failed
   screenshot (e.g. no booted simulator), a failed `openurl`, a missing output
   file, or a bad crop → `env_error` (rc 2), never a silent `0.0`, with salient
   stderr surfaced. The run records top-level `capture_provider: "ios"` and the
   resolved screenshot argv in `capture_command` (device identity) — advisory,
   never part of `definition_hash`. `simctl` has no `##servo-capture:` channel, so
   per-screen provenance is honestly `not_attested`.
5. **`capture.ios` is environmental, not frozen (additive).** The `ios` block
   (udid, crop insets, per-screen deeplinks) is **not** hashed into
   `definition_hash`; adding/changing it never re-freezes an eval. The composite,
   freeze validation, the `env_error` contract, and the 0/1/2 oracle contract are
   untouched; the web, command, and android paths are unchanged.

**DoD:**
- [ ] All ACs pass; full test suite green (no regressions).
- [ ] Implementer test coverage exercises each AC with at least one fixture
      (screenshot argv shape + target resolution incl. `booted` default; crop in
      place against the real-encoder PNG fixture → expected dims; out-of-bounds /
      non-int crop → rc2; deep-link fires `simctl openurl`; ledger
      `capture_provider: "ios"` + `capture_command`; xcrun-absent / non-zero
      screenshot / missing-output fail closed; `capture.ios` not in
      `definition_hash`).
- [ ] Each new test shown to fail when the feature is removed.
- [ ] Reviewed by `reviewer` subagent (compliance + craft passes).
- [ ] Implementation review passed.
- [ ] Deviation log produced under this slice heading.
- [ ] Reconciliation sweep produced under this slice heading.
- [ ] Reconciliation review passed.
- [ ] `docs/refinement-todo.md` updated: record the **deferred live-simulator
      smoke** (validate `xcrun simctl` screenshot→crop end-to-end on an Xcode
      machine) so it isn't a silent gap; plus any inset-autodetect / settle knobs
      shared with 027-04.

**Anti-horizontal-phasing check:** After this slice lands, a native iOS/SwiftUI
app on a booted simulator can be scored against its mockups with one
`capture.transport: "ios"` block — screenshot, chrome stripped to the reference
frame, honest fail-closed, ledger identity — no hand-written script. This closes
spec 027: web, custom-command, Android, and iOS all score through the one seam.

**Deferred (candidate for refinement-todo):** the live-simulator end-to-end smoke
(no Xcode on the authoring machine); auto-detecting iOS chrome insets; a
configurable settle delay (shared with 027-04). All noted, not silent.

### Close-out (post-DONE)

- [ ] `docs/specs/README.md` regenerated by `workflow.py status-board`.
- [ ] Primer hygiene per spec 025-01 rule — this slice **closes spec 027**
      (all five slices DONE), so verify the spec-level frontmatter/banner.

### Deviation log (after reconciliation)

The original spec is preserved above. Implementation notes:

_TBD during reconciliation._

### Reconciliation sweep

| Artifact | Disposition | Rationale |
|----------|-------------|-----------|
| `README.md` | `no-op` | _TBD._ |
| `docs/specs/README.md` | `deferred` | _TBD: status-board regen at close-out; this slice CLOSES the spec._ |
| `docs/product-vision.md` | `no-op` | _TBD._ |
| `docs/architecture.md` | `no-op` | _TBD: additive provider reusing the existing crop helper, no module-boundary change._ |
| Primer surfaces: `CLAUDE.md` / `AGENTS.md` / scaffold templates | `no-op` | _TBD._ |
| `docs/inbox.md` | `no-op` | _TBD._ |
| `docs/refinement-todo.md` | `updated` | _TBD: record the deferred iOS live-simulator smoke._ |
| `docs/memory/**` | `no-op` | _TBD._ |
| `docs/decisions/README.md` / ADR index | `no-op` | _TBD: no ADR touched (ADR-0032 already Accepted)._ |
| `skills/design-eval/SKILL.md` | `updated` | _TBD: document the `ios` provider + `capture.ios` (udid/crop/deeplink)._ |
