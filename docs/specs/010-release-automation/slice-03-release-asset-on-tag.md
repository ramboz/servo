---
status: DRAFT
dependencies: []
last_verified:
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

- [ ] All ACs pass; an end-to-end (or `workflow_dispatch`-simulated)
      release attaches the zip — evidence in the deviation log.
- [ ] Asset name verified to match the builder default and the documented
      recipe.
- [ ] Deviation log produced under this slice.
- [ ] Independent review pass completed before DONE.

**Anti-horizontal-phasing check:** After this slice, a servo release ships
an installable, smoke-tested artifact automatically — no manual zip upload.
