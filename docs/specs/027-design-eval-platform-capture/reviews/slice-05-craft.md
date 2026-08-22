---
slice: 027-05 — blessed iOS capture provider
pass: craft
verdict: pass
reviewer: jig:reviewer (in-session independent subagent)
reviewed_at: 2026-08-21
prompt_source: independent implementation review of commit 36f1aa9 (craft pass); nit fixed in e5d821b
---

PASS — a faithful, correct parallel to the Android provider; the android→ios
differences were handled properly.

- File-not-stdout: `simctl` writes the PNG to `str(out)`; the provider reads that
  file back only AFTER guarding `not out.is_file()`, then crops in place. No
  read-before-write, no path bug — `out` is computed once and used for both the
  argv and the readback.
- No silent-garbage path: rc≠0 → fail closed; rc 0 + no file → fail closed; a
  present-but-corrupt file → `crop_png` raises even at default-0 insets (signature
  validated first). An empty/failed screenshot can never reach the judge.
- `text=True` correct (PNG goes to a file, so stdout/stderr are messages only).
- `"booted"` default stays honest — device readiness deferred to simctl's own
  non-zero exit; no N+1 cost (target resolution is config/env/literal, subprocess-free).
- The `_crop_insets(crop, *, where=…)` generalization did not break the android
  caller (`where="capture.android.crop"`), and its tests still pass.

Nit (FIXED in e5d821b): the missing-output-file case reused the generic
"screenshot failed: <stderr>" message, blank when stderr is empty → split into a
dedicated "produced no output file" `EnvError`.
