---
status: DONE
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
- [x] All ACs pass; full test suite green (no regressions). — `CaptureIOSProviderTests`
      12/12 green; 145/145 in `test_design_eval` bar the one pre-existing red
      (`CaptureLibNodeTests.test_capture_lib_node_suite_passes`, Node
      output-format, red on a clean tree, unrelated); `test_skill_surface` green;
      the Android sibling tests still pass after the shared `_crop_insets`
      generalization.
- [x] Implementer test coverage exercises each AC with at least one fixture
      (screenshot argv shape + target resolution incl. `booted` default; crop in
      place against the real-encoder PNG fixture → expected dims; out-of-bounds /
      non-int crop → rc2; deep-link fires `simctl openurl`; ledger
      `capture_provider: "ios"` + `capture_command`; xcrun-absent / non-zero
      screenshot / missing-output fail closed; `capture.ios` not in
      `definition_hash`).
- [x] Each new test shown to fail when the feature is removed. — feature-bearing
      (`test_capture_ios_not_in_definition_hash` is the one regression-guard).
- [x] Reviewed by `reviewer` subagent (compliance + craft passes). — `jig:reviewer`,
      independent, 2026-08-21; VERDICT: pass. One craft nit (a generic
      missing-output message) **fixed** (commit `e5d821b`), not deferred.
- [x] Implementation review passed. — no blocking issues.
- [x] Deviation log produced under this slice heading.
- [x] Reconciliation sweep produced under this slice heading.
- [x] Reconciliation review passed. — `jig:reviewer` reconciliation pass,
      VERDICT: pass, 2026-08-21; deviation-log/sweep claims verified against
      `score.py`/`SKILL.md`/`refinement-todo.md`, review-fix `e5d821b` confirmed,
      `pngcrop.py` confirmed untouched by the 05 commits (its `xcrun` docstring
      predates this slice, so the `no-op` sweep row is correct), working tree clean.
- [x] `docs/refinement-todo.md` updated: record the **deferred live-simulator
      smoke** (validate `xcrun simctl` screenshot→crop end-to-end on an Xcode
      machine) so it isn't a silent gap; plus any inset-autodetect / settle knobs
      shared with 027-04. — added "design-eval iOS provider has no live-simulator
      end-to-end smoke" (the shared knobs already live in 027-04's entry).

**Anti-horizontal-phasing check:** After this slice lands, a native iOS/SwiftUI
app on a booted simulator can be scored against its mockups with one
`capture.transport: "ios"` block — screenshot, chrome stripped to the reference
frame, honest fail-closed, ledger identity — no hand-written script. This closes
spec 027: web, custom-command, Android, and iOS all score through the one seam.

**Deferred (candidate for refinement-todo):** the live-simulator end-to-end smoke
(no Xcode on the authoring machine); auto-detecting iOS chrome insets; a
configurable settle delay (shared with 027-04). All noted, not silent.

### Close-out (post-DONE)

- [ ] `docs/specs/README.md` regenerated by `workflow.py status-board` — **deferred
      to land-time.** Spec 027 was authored on this branch and is absent from the
      board; adding it requires the generator, but this environment lacks BOTH
      prerequisites the board's own preamble mandates (probed 2026-08-21):
      `python3.13`/Python ≥3.10 is not installed (system `python3` is 3.9), and the
      file-per-slice-aware jig copy is not present (only `…/cache/jig/jig/2.12.0/…`,
      which the preamble warns regenerates an EMPTY board). Running it here would
      corrupt the board for every spec (and re-trigger the documented umbrella-rollup
      bug on 013/016). Run at land on a machine with `python3.13` + the file-per-slice
      jig copy; the board picks up spec 027 (all slices DONE) then. Recorded so it is
      not a silent gap.
- [x] Primer hygiene per spec 025-01 rule — this slice **closes spec 027** (all
      five slices DONE). Verified: `spec.md` frontmatter is `status: DONE`, its
      Slices list marks 01–05 **DONE** (with the iOS live-smoke-deferred caveat),
      and there is no stale `> Status: DRAFT` prose banner to reconcile (unlike
      specs 013/016).

### Deviation log (after reconciliation)

The original spec is preserved above. Implementation notes:

- **Parallel to Android, with the file-vs-stdout difference handled.** `_capture_ios`
  mirrors `_capture_android`, but `xcrun simctl io <target> screenshot <path>`
  writes the PNG to a **file** (adb's `screencap -p` streams to stdout). So the
  provider passes the retained shot path as the argv's last element, then reads
  that file back and crops **in place** (read → crop → overwrite). The readback is
  guarded by `not out.is_file()`, so a rc-0-but-no-file simctl call fails closed
  rather than judging a missing image. The screenshot subprocess uses `text=True`
  (messages only; no binary stdout to preserve).
- **Target resolution is subprocess-free.** Precedence `capture.ios.udid` →
  `SERVO_DESIGN_EVAL_IOS_UDID` → the literal `"booted"` (simctl's own
  single-booted-simulator selector). Unlike Android — which queries `adb devices`
  and pins a concrete serial once — iOS needs no device-list query, so
  `_capture_ios` re-resolves the target per screen with no N+1 cost, and device
  *readiness* (none/ambiguous booted) is fail-closed by simctl's own non-zero exit
  at capture time. `xcrun` via PATH or `SERVO_DESIGN_EVAL_XCRUN_BIN`.
- **Shared crop helper generalized.** `_crop_insets` now takes a crop dict plus a
  `where=` label (for the fail-closed message path) instead of reaching into the
  android config, so both native providers share it; the android caller was
  updated to `_crop_insets(_android_cfg(config).get("crop"), where="capture.android.crop")`
  and its tests still pass.
- **Ledger identity reuses `capture_command`** (the resolved screenshot argv,
  minus the per-screen path); simctl has no `##servo-capture:` channel → provenance
  `not_attested`. `capture.ios` kept out of `_EXTRA_HASH_FIELDS` → not frozen.
- **Review fix (commit `e5d821b`), not deferred.** The independent review (PASS)
  noted the missing-output-file case reused the generic "screenshot failed:
  <stderr>" message, blank when stderr is empty — split into a dedicated
  "produced no output file" `EnvError`.
- **Live-simulator smoke DEFERRED (disclosed, human-approved).** The authoring
  machine had Command Line Tools only (no full Xcode / `simctl`, probed), so — unlike
  027-04's real-emulator smoke — the iOS real-device path is unproven here. Validated
  to the committed-CI bar (stubbed simctl + the synthetic real-encoder fixture; the
  crop is pixel-exact-tested by 027-04). Recorded in `docs/refinement-todo.md` with
  a resolution trigger (run on an Xcode machine).

### Reconciliation sweep

| Artifact | Disposition | Rationale |
|----------|-------------|-----------|
| `README.md` | `no-op` | Root orientation; no surface it describes changed. |
| `docs/specs/README.md` | `deferred` | Status-board regen is the spec-CLOSE close-out step (below); handled there with a frontmatter re-check against the known umbrella-rollup bug. |
| `docs/product-vision.md` | `no-op` | No vision-level claim affected. |
| `docs/architecture.md` | `no-op` | Additive provider reusing the existing crop helper; no module boundary/contract/artifact-path change. |
| Primer surfaces: `CLAUDE.md` / `AGENTS.md` / scaffold templates | `no-op` | None reference capture providers or the ledger shape. |
| `docs/inbox.md` | `no-op` | Nothing to hand off. |
| `docs/refinement-todo.md` | `updated` | Added the deferred iOS live-simulator smoke entry. |
| `docs/memory/**` | `no-op` | No durable cross-session fact beyond spec + code. |
| `docs/decisions/README.md` / ADR index | `no-op` | No ADR touched — ADR-0032 already Accepted; iOS reuses the ADR-0020-constrained stdlib crop. |
| `skills/design-eval/SKILL.md` | `updated` | Documented the `ios` provider + `capture.ios` (udid/crop/deeplink) under the capture-transport list. |
| `skills/design-eval/pngcrop.py` / `design_eval.py` | `no-op` | Reused as-is from 027-04 (cropper + vendoring already in place); no change needed for iOS. |
