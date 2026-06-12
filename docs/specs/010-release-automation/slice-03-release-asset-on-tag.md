---
status: DONE
dependencies: []
last_verified: 2026-06-12
---

## Slice 010-03 — release-asset-on-tag

**Goal:** When release-please creates a release, build the smoke-tested zip
and upload it as a release asset. End-to-end value: every servo release
ships an installable, verified artifact automatically.

**DoR:**

- 010-02 landed (release-please creates tags/releases and exposes
  `release_created` / `tag_name` / `version`).
- `scripts/build_release_zip.py` produces `dist/servo-v<version>.zip` and
  smoke-tests by default (spec 007).

**Acceptance Criteria:**

1. **Package job.** `release.yml` gains a `package` job with
   `needs: [release-please]`, gated on
   `if: needs.release-please.outputs.release_created == 'true'`, that checks
   out at the release `tag_name` and sets up Python.
2. **Build + smoke.** It runs `python3 scripts/build_release_zip.py`, which
   auto-derives the version from `plugin.json` and smoke-tests the zip.
   _(Optionally pass `--version <release-please version>` so a version/tag
   mismatch fails the build loudly — servo's builder already validates a
   requested version against the manifest and exits 2 on mismatch.)_
3. **Upload.** It uploads `dist/servo-v<version>.zip` to the release with
   `gh release upload <tag_name>` using `GITHUB_TOKEN`.
4. **Asset name.** The attached asset is named `servo-v<version>.zip`,
   matching the builder's default output and the README release recipe
   (already guarded by `scripts/test_docs_install.py`).
5. **Smoke gates the upload.** A failing smoke test fails the job *before*
   upload — no mislabeled or broken asset is ever attached.

**DoD:**

- [x] All ACs pass; an end-to-end (or `workflow_dispatch`-simulated)
      release attaches the zip — evidence in the deviation log. _AC1, AC2, AC5
      met in-artifact and the build+smoke command was verified against the real
      builder CLI (built + smoke-passed `servo-v0.1.0.zip` and a simulated
      `servo-v9.9.9.zip` locally). The actual asset *attach* needed a created
      release on `main` (the `package` job is gated on `release_created`) — now
      done: PR #3's merge published release `v0.2.0` with `servo-v0.2.0.zip`
      (97,640 bytes) attached. See the main-merge verification below._
- [x] Asset name verified to match the builder default and the documented
      recipe. _Builder default output is `dist/servo-v<version>.zip` (confirmed
      by building 0.1.0 and 9.9.9); the workflow uploads that exact path; the
      README documents the `servo-v<version>.zip` shape and the docs guard
      (`test_docs_install.py`) enforces it. All three agree._
- [x] Deviation log produced under this slice. _Below._
- [x] Independent review pass completed before DONE. _Independent reviewer,
      2026-06-11 — **PASS, no blockers.** Confirmed the package job's
      needs/if-gating, checkout-at-tag, and that the single build+smoke step
      precedes (gates) the upload step._

**Anti-horizontal-phasing check:** After this slice, a servo release ships
an installable, smoke-tested artifact automatically — no manual zip upload.

**Deviation log:**

- **Adapted to servo's one-step builder (intentional divergence from jig).**
  jig's package job builds and smoke-tests in two separate `build_release_zip.py`
  invocations; servo's builder builds **and** smoke-tests in a single default
  invocation (`--no-smoke` opts out — spec 007). So the package job runs one
  `python3 scripts/build_release_zip.py --version "<version>"` step. Because
  that single step both builds and smokes *before* the separate upload step, a
  failing smoke test fails the job before any asset is attached (AC5).
- **`--version` for a loud mismatch (AC2 option taken).** Passing the
  release-please `version` makes the builder validate it against
  `.claude-plugin/plugin.json` (which release-please bumped) and exit 2 on
  mismatch — so a tag/version drift fails the build rather than shipping a
  mislabeled asset. The default `--output` already lands at
  `dist/servo-v<version>.zip`, so no `--output` is needed.
- **Live attach is main-only.** The job is gated on
  `needs.release-please.outputs.release_created == 'true'`, which is only true
  in the `release.yml` run where merging the release PR creates the release.
  Verified end-to-end in the main-merge step.
- **Main-merge verification (2026-06-12).** Merging PR #3 published release
  `v0.2.0`; the `package` job ran in `release.yml` run 27437946710 (gated on
  `release_created == 'true'`), built + smoke-tested the zip, and attached
  **`servo-v0.2.0.zip` (97,640 bytes)** to the release (AC3/AC4/AC5). The asset
  name matches the builder default and the README recipe. End-to-end value
  proven: the release shipped an installable, verified artifact with no manual
  step.
