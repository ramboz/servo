---
status: DONE
dependencies: [adr-0032, 027-02]
last_verified: 2026-08-21
claimed_by: claude/027-01-342c59
---

## Slice 027-04 — blessed Android provider

**Goal:** Ship a built-in **Android** capture provider — `adb … exec-out
screencap` for pixels, a state driver for per-screen seeding, and chrome-frame
normalization (crop status/navigation bars to the reference's logical frame) —
so a native Android (Jetpack Compose) UI can be scored against the same mockups
as its web build. Degrades honestly to `env_error` when `adb`/device absent.

**Scope note:** the first blessed native built-in. Chrome-cropping here is
new from-scratch work (no DOM/selector), per [ADR-0032](../../decisions/adr-0032-design-eval-capture-providers.md)
§5; state equivalence to the web seed is project-authored, not certified. It
registers **one** provider (`android`) into the 027-02 seam. Complex tap-flow
seeding stays the job of the 027-03 `command` provider; this slice's blessed
seed is the common declarative case (a deep link).

**DoR:**
- ✅ 027-02/03 shipped the seam + a subprocess-backed provider pattern
  (`_run_capture_subprocess`, `_resolve_capture_transport`, the `capture_provider`
  / `capture_command` ledger fields). This slice adds a provider that also crops.
- ✅ Capture path probe-verified live (2026-08-21) against a real emulator
  (`emulator-5554`, Android API 35): `adb -s <serial> exec-out screencap -p`
  emits a valid 8-bit RGBA non-interlaced PNG (1080×2400 on that device). The
  status bar (top) and gesture pill (bottom) are the device chrome to strip.
- ✅ Cropping decision: servo is **stdlib-only** (ADR-0020) — no Pillow/ImageMagick.
  A minimal pure-stdlib PNG crop (parse IHDR/IDAT, `zlib`-inflate, un-filter, slice
  rows/cols, re-filter/`zlib`-deflate, re-emit with CRC) handles exactly the
  `screencap` format (8-bit RGBA, non-interlaced) and is validated against the
  real emulator PNG. No new dependency; no ADR needed (crop output is unfrozen).
- ✅ `capture.android` is environmental (ADR-0032 §6), like `capture.transport`
  /`capture.command` — not hashed, never a staleness trigger.

**Acceptance Criteria:**

1. **Android provider selected; per-screen screencap.** `capture.transport:
   "android"` selects a provider that captures each screen via
   `adb [-s <serial>] exec-out screencap -p`, writing the PNG under `shots/`
   (retained + ledger-linked by the 027-01 plumbing, path depth unchanged).
   Device resolution precedence: `capture.android.serial` → the
   `SERVO_DESIGN_EVAL_ANDROID_SERIAL` env var → the single connected device.
   **No device, or an ambiguous multi-device set with no serial, fails closed to
   `env_error`** (rc 2) — surfaced before capture, never a silent `0.0`.
2. **Chrome-frame normalization by configured insets.** The screenshot is cropped
   by `capture.android.crop` = `{top,bottom,left,right}` (pixels, each defaulting
   to 0) to strip the status/navigation bars to the reference's logical frame,
   via a pure-stdlib PNG crop. The crop is validated against a **real-encoder PNG
   fixture** (encoded by an independent tool so it exercises real adaptive
   scanline filters, not just the module's own filter-0 output): a known inset
   yields the expected reduced dimensions and a still-valid PNG. Additionally, the
   full real-emulator `screencap → crop` path is smoke-validated live and recorded
   in the deviation log (the committed fixture stays synthetic + third-party-free
   for CI portability). A crop that meets or exceeds the image bounds (e.g.
   `top+bottom ≥ height`) fails closed to `env_error` — never a zero-area or
   garbage frame.
3. **Per-screen state seeding (optional deep link).** If a screen declares
   `deeplink: "<uri>"`, the provider fires
   `adb [-s <serial>] shell am start -a android.intent.action.VIEW -d <uri>` and
   waits a bounded settle before screencap. Absent → it screencaps the current
   state (positioning is the project's responsibility; complex flows use the
   `command` provider). State equivalence to the web seed is project-authored, not
   certified (ADR-0032 §4).
4. **Fail closed + identity in the ledger.** `adb` absent, no/ambiguous device, a
   non-zero screencap, a failed deep-link, or an out-of-bounds crop → `env_error`
   (rc 2), never a silent `0.0`, with salient stderr surfaced. The run records
   top-level `capture_provider: "android"` and the resolved screencap argv in
   `capture_command` (device identity) — advisory, never part of `definition_hash`.
   An `adb` screencap emits no `##servo-capture:` line, so per-screen provenance
   is honestly `not_attested`.
5. **`capture.android` is environmental, not frozen (additive).** The `android`
   block (serial, crop insets, per-screen deeplinks) is **not** hashed into
   `definition_hash`; adding/changing it never re-freezes an eval. The composite,
   freeze/`StaleError` validation, the `env_error` contract, and the 0/1/2 oracle
   contract are untouched. The web and command paths are unchanged.

**DoD:**
- [x] All ACs pass; full test suite green (no regressions). — `PngCropTests` +
      `CaptureAndroidProviderTests` 22/22 green; 133/133 in `test_design_eval` bar
      the one pre-existing red (`CaptureLibNodeTests.test_capture_lib_node_suite_passes`,
      Node output-format, red on a clean tree, unrelated); `test_skill_surface`
      green (its Files-table drift check now includes `pngcrop.py`).
- [x] Implementer test coverage exercises each AC with at least one fixture
      (screencap argv shape + device resolution/ambiguity; crop against a
      real-encoder PNG fixture → expected dims + valid PNG; out-of-bounds crop →
      rc2; deep-link fires `am start`; ledger `capture_provider: "android"` +
      `capture_command`; `capture.android` not in `definition_hash`). Plus
      per-filter pixel-exact codec proof (all 5 un-filter branches) and
      fail-closed on corrupt-IDAT / non-integer crop (review follow-ups).
- [x] Each new test shown to fail when the feature is removed. — the codec and
      provider tests are feature-bearing (`test_capture_android_not_in_definition_hash`
      is the one regression-guard, green without the feature).
- [x] Live end-to-end smoke recorded in the deviation log: real emulator
      screencap → crop → valid framed PNG (CI stays stub-based for portability).
- [x] Reviewed by `reviewer` subagent (compliance + craft passes). — `jig:reviewer`,
      independent, 2026-08-21; VERDICT: needs-changes (one fail-closed defect + a
      minor + a codec-coverage gap), all **fixed** (commit `e7facf6`), not deferred.
- [x] Implementation review passed. — after the fixes above.
- [x] Deviation log produced under this slice heading.
- [x] Reconciliation sweep produced under this slice heading.
- [x] Reconciliation review passed. — `jig:reviewer` reconciliation pass,
      VERDICT: pass, 2026-08-21; every deviation-log/sweep claim verified against
      `score.py`/`pngcrop.py`/`SKILL.md`/`design_eval.py`/`refinement-todo.md`, the
      review-fix commit `e7facf6` confirmed, working tree confirmed clean (only this
      slice + refinement-todo). One naming-completeness nit fixed above.
- [x] `docs/refinement-todo.md` updated if any decisions were deferred. — added
      "design-eval Android provider uses configured crop insets + a fixed settle
      delay" (inset auto-detect + `settle_ms` knob).

**Anti-horizontal-phasing check:** After this slice lands, a native Android app
on a connected device/emulator can be scored against its mockups with one
`capture.transport: "android"` block — screenshot, chrome stripped to the
reference frame, honest fail-closed, ledger identity — no hand-written script.
End-to-end native value.

**Deferred (candidate for refinement-todo):** auto-detecting the status/nav-bar
insets (via `adb shell dumpsys` / window insets) instead of configured pixels; a
configurable post-deep-link settle delay. Both noted, not built, so they aren't
silent gaps.

### Close-out (post-DONE)

- [ ] `docs/specs/README.md` regenerated by `workflow.py status-board` (only if it
      closes the spec — it does not; 05 remains).

### Deviation log (after reconciliation)

The original spec is preserved above. Implementation notes:

- **New stdlib PNG cropper (`pngcrop.py`).** servo is stdlib-only (ADR-0020), so
  a from-scratch `zlib`-based PNG decode/un-filter/crop/re-encode handles exactly
  the screencap format (8-bit truecolor, non-interlaced); interlaced/paletted/
  <8-bit/16-bit raise `PngCropError`. It is a sibling of `score.py` in both layouts,
  loaded via a single-candidate `_load_pngcrop()`, and vended by `design_eval.py::init()`.
- **Provider ownership of the three steps (ADR-0032 §1/§4/§5).** `_capture_android`
  drives state (optional per-screen `deeplink` → `am start`, then a 2s settle),
  takes pixels (`adb -s <serial> exec-out screencap -p`, captured as **bytes**, not
  text), and normalizes the frame (crop insets). Device resolution precedence
  `serial` → `SERVO_DESIGN_EVAL_ANDROID_SERIAL` → single connected device; none/
  ambiguous fails closed. `adb` via PATH or `SERVO_DESIGN_EVAL_ADB_BIN`.
- **Serial pinned once, not re-queried per screen.** `score()` resolves the serial
  up front (fail-closed before any capture) and writes it into the in-memory config
  so the per-screen provider reuses it (no N+1 `adb devices`). This mutation happens
  **after** `validate_freeze` and touches only `capture.android`, which is not in
  the hash — so the freeze is unaffected (proven by `test_capture_android_not_in_definition_hash`).
- **Ledger identity reuses `capture_command`.** The resolved screencap argv is
  recorded there (generalizing 027-03's field to "the resolved capture-driver argv"
  for command/android); adb has no `##servo-capture:` channel, so provenance is
  honestly `not_attested`.
- **Review fixes (commit `e7facf6`), not deferred.** The independent review
  (needs-changes) found: (1) `zlib.decompress` unwrapped → a corrupt IDAT escaped
  the `PngCropError`/`env_error` contract — **fixed** (wrapped, re-raised); (2) a
  non-integer crop value raised a bare `ValueError` — **fixed** (`_crop_insets`
  raises a crop-specific `EnvError`); (3) the un-filter branches 1-4 were only
  covered transitively by the fixture — **fixed** with deterministic per-filter
  pixel-exact tests, a crop-lands-exact-pixels test, and a fixture-nonzero-filters
  guard. Named tests added: `test_each_filter_type_decodes_pixel_exact`,
  `test_crop_lands_exact_pixels`, `test_fixture_uses_nonzero_filters`,
  `test_corrupt_idat_raises_pngcroperror`, `test_corrupt_screencap_png_fails_closed`,
  `test_non_integer_crop_fails_closed`.
- **CI fixture is synthetic, third-party-free (sanctioned).** The committed
  `testdata/rgba_filter_sample.png` is a synthetic gradient re-encoded by an
  independent tool (real Sub/Paeth filters), **not** a real screenshot — a real
  emulator home screen carries Google's wallpaper/icons, which must not land in a
  public repo. The real-device path is validated by the live smoke below.
- **Live end-to-end smoke (real emulator, recorded per DoD).** On `emulator-5554`
  (Android API 35, 1080×2400): a real `adb exec-out screencap` → crop
  `{top:90,bottom:60}` → a valid 1080×2250 framed PNG; a full `score.score()` run
  recorded `capture_provider: "android"`, the real resolved `adb … screencap` argv
  in `capture_command`, `provenance: "not_attested"`, and a retained cropped shot.
  Verified visually that the status bar and gesture pill are removed. CI stays
  stub-based (no device) for portability.

### Reconciliation sweep

| Artifact | Disposition | Rationale |
|----------|-------------|-----------|
| `README.md` | `no-op` | Root orientation; no surface it describes changed. |
| `docs/specs/README.md` | `deferred` | Status-board regen is post-DONE close-out; not run (spec not closed — 05 remains; known umbrella-frontmatter rollup bug). |
| `docs/product-vision.md` | `no-op` | No vision-level claim affected. |
| `docs/architecture.md` | `no-op` | Additive provider + a self-contained stdlib crop helper; no module boundary/contract/artifact-path change. |
| Primer surfaces: `CLAUDE.md` / `AGENTS.md` / scaffold templates | `no-op` | None reference capture providers or the ledger shape. |
| `docs/inbox.md` | `no-op` | Nothing to hand off. |
| `docs/refinement-todo.md` | `updated` | Added the Android inset-autodetect + settle-delay knobs deferral. |
| `docs/memory/**` | `no-op` | No durable cross-session fact beyond spec + code. |
| `docs/decisions/README.md` / ADR index | `no-op` | No ADR touched — ADR-0032 already Accepted; the stdlib-crop choice is under ADR-0020's existing constraint, not a new decision. |
| `skills/design-eval/SKILL.md` | `updated` | Documented the `android` provider + `capture.android` (serial/crop/deeplink), the stdlib crop, and the new `pngcrop.py` Files-table row. |
| `skills/design-eval/design_eval.py` vendoring (`init()`) | `updated` | Vends the new `pngcrop.py` into the target. |
| `skills/design-eval/testdata/rgba_filter_sample.png` | `added` | Synthetic real-encoder PNG fixture for the codec tests (third-party-free). |
