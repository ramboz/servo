---
slice: 027-05 — blessed iOS capture provider
pass: implementation (compliance + craft)
verdict: pass
reviewer: jig:reviewer (in-session independent subagent, no build-conversation access)
reviewed_at: 2026-08-21
prompt_source: implementation review of commit 36f1aa9 against slice-05 ACs; nit fixed in e5d821b
---

VERDICT: pass — a faithful, correct parallel to the Android provider; one craft
nit raised and FIXED (commit e5d821b).

Compliance (AC1–AC5): all met — provider selected + `simctl io … screenshot` argv
shape + target precedence (udid → env → "booted"); crop in place + out-of-bounds/
non-int fail-closed; optional `simctl openurl` deep-link seed; fail-closed on
xcrun-absent / non-zero screenshot / missing output file / bad crop; ledger
`capture_provider: "ios"` + `capture_command`; `not_attested` provenance;
`capture.ios` proven out of `definition_hash`. Tests feature-bearing;
`test_capture_ios_not_in_definition_hash` is the one regression-guard.

Craft (the android→ios differences, scrutinized):
- File-not-stdout handled correctly: simctl writes to `str(out)`; the provider reads
  that file back only AFTER guarding `not out.is_file()`, then crops in place. No
  read-before-write, no path bug (`out` computed once, used for both argv and readback).
- No silent-garbage path: rc≠0 → fail closed; rc 0 + no file → fail closed; a
  present-but-corrupt file → `crop_png` raises even at default-0 insets (signature
  validated first). An empty/failed screenshot can never reach the judge.
- `text=True` correct (the PNG goes to a file, so stdout/stderr are messages only).
- "booted" default stays honest: device readiness deferred to simctl, whose
  non-zero exit trips the guard.
- The `_crop_insets` generalization did not break the android caller.

Nit (FIXED in e5d821b): the missing-output-file case reused the generic
"screenshot failed: <stderr>" message, blank when stderr is empty → split into a
dedicated "produced no output file" `EnvError`.

Disclosed, human-approved: no Xcode/simctl on the authoring machine, so the
live-simulator smoke is DEFERRED (recorded in `docs/refinement-todo.md`); iOS is
validated to the stub/CI bar, with the crop pixel-exact-tested by 027-04.
