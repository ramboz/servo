---
slice: 027-04 — blessed Android capture provider
pass: compliance
verdict: pass
reviewer: jig:reviewer (in-session independent subagent, no build-conversation access)
reviewed_at: 2026-08-21
prompt_source: independent implementation review of commit 8044813 against slice-04 ACs
---

PASS — all five ACs satisfied on the evidence.

- AC1: `capture.transport: "android"` captures via `adb [-s <serial>] exec-out
  screencap -p`; device resolution `capture.android.serial` →
  `SERVO_DESIGN_EVAL_ANDROID_SERIAL` → single connected device; no/ambiguous device
  fails closed to env_error up front (`_resolve_android_serial`). Shot retained +
  ledger-linked by 027-01 plumbing.
- AC2: crop by `capture.android.crop` insets via the stdlib `pngcrop`; out-of-bounds
  and negative insets fail closed.
- AC3: optional per-screen `deeplink` → `adb … am start`, bounded settle.
- AC4: fail-closed on adb-absent / no-ambiguous device / non-zero screencap / bad
  crop; ledger `capture_provider: "android"` + resolved screencap argv in
  `capture_command`; `not_attested` provenance (adb has no attestation channel).
- AC5: `capture.android` proven out of `definition_hash`.

Verified by inspection: `_unfilter` correct for all five filter types (None/Sub/Up/
Average/Paeth, edge handling at i<bpp, Paeth predictor); `crop_png` row/column
slicing off-by-one-clean against a worked 4×4 example. Tests feature-bearing;
`test_capture_android_not_in_definition_hash` is the regression-guard.
