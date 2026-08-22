---
slice: 027-04 — blessed Android capture provider
pass: implementation (compliance + craft)
verdict: needs-changes → fixed
reviewer: jig:reviewer (in-session independent subagent, no build-conversation access)
reviewed_at: 2026-08-21
prompt_source: implementation review of commit 8044813 against slice-04 ACs; fixes in e7facf6
---

VERDICT: needs-changes (one fail-closed defect + a minor + a codec-coverage gap),
all FIXED in commit e7facf6. Re-verified green afterward.

Compliance (AC1–AC5): all met on the evidence — serial precedence + no/ambiguous
fail-closed; inset crop with out-of-bounds and negative-inset guards; optional
deep-link seed; `capture_provider`/`capture_command` ledger identity with honest
`not_attested`; `capture.android` provably excluded from `definition_hash`. The
hand-rolled `_unfilter` was checked line-by-line against the PNG spec (None/Sub/Up/
Average/Paeth, edge handling, Paeth predictor) and `crop_png`'s row/column slicing
verified off-by-one-clean against a worked 4×4 example.

Findings (all FIXED, not deferred):
1. DEFECT — `pngcrop.crop_png` did not wrap `zlib.decompress`, so a corrupt/
   truncated screencap IDAT (a plausible adb-transport hiccup — exactly the
   environmental failure this provider promises to fail closed on) escaped as an
   uncaught `zlib.error` rather than `PngCropError → env_error rc 2`. Fixed: wrapped
   and re-raised as `PngCropError`.
2. MINOR — a non-integer crop value raised a bare `ValueError` outside the crop
   guard. Fixed: `_crop_insets` raises a crop-specific `EnvError`.
3. COVERAGE GAP — the un-filter branches 1–4 were only covered transitively by the
   fixture. Fixed: deterministic per-filter pixel-exact tests forcing each branch,
   a crop-lands-exact-pixels test (not dims-only), a fixture-uses-nonzero-filters
   guard, and provider-level corrupt-screencap / non-int-crop fail-closed tests.

Craft notes: the in-memory serial pin happens after `validate_freeze` and touches
only `capture.android` (not hashed) — freeze-safe. Screencap captured as bytes
(`text` unset) — correct for binary stdout.

Disclosed, sanctioned: the committed CI fixture is synthetic/third-party-free
(a real emulator home screen carries Google imagery). The real-device path is
validated by the live-emulator smoke recorded in the slice deviation log.
