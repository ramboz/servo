---
slice: 027-04 — blessed Android provider (reopen: regression fix)
pass: bug-review + craft (reopen)
verdict: pass
reviewer: jig:reviewer (in-session independent subagent)
reviewed_at: 2026-08-21
prompt_source: review of the lazy-load regression fix after PR #31 CI failure (slice reopened DONE → IN_PROGRESS)
---

PASS — lazy-loading is the correct STRUCTURAL fix, not a workaround.

Context: slice 027-04 shipped a regression — `score.py` loaded `pngcrop.py` at
module-import time (`_pc = _load_pngcrop()`), hard-raising `ModuleNotFoundError`
when the sibling was absent — crashing the web/command/fake-scores paths and
breaking `skills/_common/test_fidelity_eval.py::ImportResolutionTests`. CI caught
it (Python 3.9 + 3.12); the maintainer flagged it on PR #31. A subset-only local
run (`test_design_eval` only, never `scripts/run_tests.py`) had missed it.

Diagnostic question answered ("problem with the process, not the output"): the real
defect is that `score.py` hard-required a NATIVE-ONLY dependency at import time.
`pngcrop.py` is used only by `_capture_android`/`_capture_ios`, so the non-native
paths must import cleanly without it.

Correctness confirmed (by reading `score.py`):
- `_pc = None` + cached `_pngcrop()` accessor; NO residual `_pc.` attribute access
  survives — both crop sites use `pc = _pngcrop()` then `pc.crop_png(...)` /
  `except pc.PngCropError`.
- `EnvError` (assigned from `_fe`) is a module global by the time `_pngcrop()` is
  first called (runtime, native only) — no import-order hazard.
- Blast radius: the web/command/fake paths never call `_pngcrop()`; zero effect.
- Thread-safety: unsynchronized check-then-set on `_pc`, but single-process CLI and
  idempotent load — a race would at worst re-import harmlessly. Acceptable.
- Provisioning intact: `design_eval.py::init()` still vends `pngcrop.py`, so a real
  native install has the sibling; a native run without it now fails closed to
  `EnvError`, not a bare traceback.

Red→green: the pre-existing `ImportResolutionTests` are the regression coverage —
confirmed RED on the committed branch state (2 failures, exact `ModuleNotFoundError`),
GREEN after the fix. Full CI runner `python3 scripts/run_tests.py` = 1774 passed,
2 skipped.

Coverage gap (raised by review, CLOSED): the NEW fail-closed branch (`_pngcrop()`
→ `EnvError` when the sibling is absent during a native run) had no direct test.
Added `CaptureAndroidProviderTests.test_missing_pngcrop_fails_closed` — asserts a
native lazy-load without pngcrop.py raises `EnvError` (feature-bearing: reverting
to `ModuleNotFoundError` fails it). Design-eval suite 145 → 146.

Prevention (class-of-error): a subset-only local run let an import-time regression
reach CI. Standing rule recorded: validate with the full CI runner
(`python3 scripts/run_tests.py`) — or at minimum the `_common` import tests — before
marking a native-provider slice DONE. The slice DoD's "full suite green" tick was
corrected to cite the CI runner, not the subset.
