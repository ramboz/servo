---
status: IN_PROGRESS
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
- [ ] All ACs pass; full test suite green (no regressions).
- [ ] Implementer test coverage exercises each AC with at least one fixture
      (screencap argv shape + device resolution/ambiguity; crop against a
      real-encoder PNG fixture → expected dims + valid PNG; out-of-bounds crop →
      rc2; deep-link fires `am start`; ledger `capture_provider: "android"` +
      `capture_command`; `capture.android` not in `definition_hash`).
- [ ] Each new test shown to fail when the feature is removed.
- [ ] Live end-to-end smoke recorded in the deviation log: real emulator
      screencap → crop → valid framed PNG (CI stays stub-based for portability).
- [ ] Reviewed by `reviewer` subagent (compliance + craft passes).
- [ ] Implementation review passed.
- [ ] Deviation log produced under this slice heading.
- [ ] Reconciliation sweep produced under this slice heading.
- [ ] Reconciliation review passed.
- [ ] `docs/refinement-todo.md` updated if any decisions were deferred (e.g.
      auto-detecting chrome insets via `dumpsys` instead of configured insets;
      a settle-delay knob).

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

_TBD during reconciliation._

### Reconciliation sweep

| Artifact | Disposition | Rationale |
|----------|-------------|-----------|
| `README.md` | `no-op` | _TBD._ |
| `docs/specs/README.md` | `deferred` | _TBD: status-board regen at close-out; spec not closed._ |
| `docs/product-vision.md` | `no-op` | _TBD._ |
| `docs/architecture.md` | `no-op` | _TBD: additive provider + stdlib crop helper, no module-boundary change._ |
| Primer surfaces: `CLAUDE.md` / `AGENTS.md` / scaffold templates | `no-op` | _TBD._ |
| `docs/inbox.md` | `no-op` | _TBD._ |
| `docs/refinement-todo.md` | `no-op` | _TBD: note the inset-autodetect / settle-delay knobs if deferred._ |
| `docs/memory/**` | `no-op` | _TBD._ |
| `docs/decisions/README.md` / ADR index | `no-op` | _TBD: no ADR touched (ADR-0032 already Accepted)._ |
| `skills/design-eval/SKILL.md` | `updated` | _TBD: document the `android` provider + `capture.android` (serial/crop/deeplink) + the stdlib crop + Files table (new `pngcrop.py`)._ |
| `skills/design-eval/design_eval.py` vendoring (`init()`) | `updated` | _TBD: vend the new `pngcrop.py` into the target._ |
