---
status: DONE
dependencies: []
last_verified:
---

## Slice 007-02 — release-zip

**Goal:** A deterministic release zip builder that packages only the
runtime artifacts named by the contract and proves the extracted archive
passes plugin verification. End-to-end value: servo can be distributed
as a single installable archive instead of a whole development checkout.

**DoR:**

- 007-01 DONE.
- Release zip include/exclude policy agreed in the contract.
- Plugin verifier can run against arbitrary extracted directories.

**Acceptance Criteria:**

1. **Zip builds.** `python3 scripts/build_release_zip.py --output
   <path>` writes a zip containing the required runtime artifacts and no
   top-level wrapping directory.
2. **Deterministic output.** Running the builder twice against the same
   tree produces byte-identical zip files.
3. **Forbidden files excluded.** Tests, caches, `.git/`, docs, dist
   outputs, logs, and Python bytecode are not present in the archive.
4. **Version source.** The builder reads the version from
   `.claude-plugin/plugin.json`; if a requested version or output name
   conflicts with the manifest version, it fails clearly.
5. **Smoke extraction.** With the default smoke behavior, the builder
   extracts the zip into a temp dir and runs
   `verify_install.py plugin <extract-root>` against it.
6. **Unsafe paths refused.** The verifier rejects zips with absolute
   paths or `..` traversal entries.

**DoD:**

- [x] Builder tests cover inventory, exclusions, determinism, version
  mismatch, smoke extraction, and unsafe path rejection. _23 tests in
  `scripts/test_build_release_zip.py`; 37 total script tests with
  `scripts/test_verify_install.py`._
- [x] `dist/` remains ignored or otherwise untracked. _Added to
  `.gitignore`._
- [x] README documents the zip install command after this slice or in
  007-05 if docs are intentionally deferred. _Deferred to 007-05 so
  the public docs land once plugin, zip, and scaffold surfaces can be
  described together._
- [x] Deviation log produced under this slice.
- [x] Independent review pass completed before DONE. _Final subagent
  review (`Halley`), 2026-05-28: PASS, no blocker or should-fix
  findings._

**Anti-horizontal-phasing check:** After this slice, a user can build a
release archive locally and verify that the extracted plugin is
installable.

### Deviation log

**Slice 007-02 - implementation started 2026-05-28.** Added
`scripts/build_release_zip.py`, `verify_install.py zip` mode, and
`scripts/test_build_release_zip.py`. Verification:

- `PYTHONDONTWRITEBYTECODE=1 python3 scripts/test_build_release_zip.py`
  -> 23/23 tests passing.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s scripts -p 'test_*.py'`
  -> 37/37 tests passing.
- `PYTHONDONTWRITEBYTECODE=1 python3 scripts/build_release_zip.py --output /private/tmp/servo-v0.1.0.zip`
  -> built a 21-entry archive and smoke-verified it through
  `verify_install.py zip`.

Deviations from draft spec text:

- **`--version` is optional.** The spec says the builder reads the
  version from `.claude-plugin/plugin.json`; implementation follows
  that as the default and treats `--version` as an optional assertion
  that must match the manifest.
- **Filename version mismatch is pattern-based.** Output filenames of
  the form `servo-v<version>.zip` are checked against the manifest
  version. Arbitrary filenames such as `servo-test.zip` are allowed for
  local smoke builds.
- **Local metadata exclusion added.** The implementation adds
  `**/.DS_Store`, `**/.gitkeep`, and
  `templates/crew-postmortem.md` to `release_zip.exclude_globs`; these
  are deterministic-release hygiene rules in the spirit of "caches /
  local logs / dev files" even though the initial JSON sketch did not
  spell them out.
- **README install docs deferred.** 007-05 owns the public install docs
  for plugin, zip, and scaffold together; this slice records the
  deferral rather than adding zip-only docs early.

### Review reconciliation

Independent review:

- `Nash` subagent, 2026-05-28: **FAIL** with two should-fix findings.
  1. Release zip inventory included non-runtime sentinel/contributor
     files (`hooks/.gitkeep`, `skills/.gitkeep`, and
     `templates/crew-postmortem.md`).
  2. Unsafe-path validation missed Windows-drive absolute paths such as
     `C:/evil.txt`.

Reconciliation:

- Added `**/.gitkeep` and `templates/crew-postmortem.md` to
  `release_zip.exclude_globs`; added
  `test_gitkeep_and_crew_postmortem_excluded`.
- Added Windows drive/absolute detection via `PureWindowsPath`; added
  `test_windows_drive_absolute_entry_rejected`.
- Re-ran focused checks: release zip tests now 21/21; script discovery
  now 35/35; real zip build now contains 21 runtime entries.

Independent follow-up review:

- `Boyle` subagent, 2026-05-28: **FAIL** with one should-fix finding.
  The builder accepted unsafe `release_zip.include` entries such as
  `../outside.txt` when `--no-smoke` was used, allowing it to write an
  unsafe archive before the verifier could reject it.

Reconciliation:

- Added release-include and final-archive path validation in
  `scripts/build_release_zip.py`, including Windows drive detection.
- Added `UnsafeContractTests` for parent traversal and Windows-drive
  include paths.
- Re-ran focused checks: release zip tests now 23/23; script discovery
  now 37/37; real zip build still contains 21 runtime entries.

Independent final review:

- `Halley` subagent, 2026-05-28: **PASS**. No blocker or should-fix
  findings. Verified that all three prior findings are fixed: forbidden
  sentinel/contributor files are absent from the inventory, `C:/evil.txt`
  is rejected by zip verification, and unsafe contract include paths are
  rejected before the builder writes an archive.

Slice 007-02 is DONE. Slices 007-03 through 007-05 remain DRAFT.

---

