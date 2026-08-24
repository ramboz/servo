---
slice: 027-04 — blessed Android capture provider
pass: craft
verdict: pass
reviewer: jig:reviewer (in-session independent subagent)
reviewed_at: 2026-08-21
prompt_source: independent implementation review of commit 8044813 (craft pass); fixes in e7facf6
---

NEEDS-CHANGES — one fail-closed defect + a minor + a codec-coverage gap. All FIXED
in commit e7facf6, then re-verified green. This is the review that most earned its
keep: it caught a real crash-instead-of-clean-error path in the hand-rolled codec.

1. DEFECT — `pngcrop.crop_png` did not wrap `zlib.decompress`, so a corrupt /
   truncated screencap IDAT (a plausible adb-transport hiccup — exactly the
   environmental failure this provider promises to fail closed on) escaped as an
   uncaught `zlib.error` rather than `PngCropError → env_error rc 2`. Fixed: wrapped
   and re-raised as `PngCropError`; provider-level `test_corrupt_screencap_png_fails_closed`
   added.
2. MINOR — a non-integer crop value raised a bare `ValueError` outside the crop
   guard, landing in main()'s generic catch. Fixed: `_crop_insets` raises a
   crop-specific `EnvError`; `test_non_integer_crop_fails_closed` added.
3. COVERAGE GAP — the un-filter branches 1–4 were only covered transitively by the
   fixture (static review could not confirm the fixture exercised them). Fixed:
   deterministic per-filter pixel-exact tests forcing each branch
   (`test_each_filter_type_decodes_pixel_exact`), a crop-lands-exact-pixels test
   (not dims-only), and a `test_fixture_uses_nonzero_filters` guard.

Craft notes (no change needed): the in-memory serial pin happens after
`validate_freeze` and touches only `capture.android` (not hashed) — freeze-safe;
screencap captured as bytes (no `text=True`) — correct for binary stdout.
