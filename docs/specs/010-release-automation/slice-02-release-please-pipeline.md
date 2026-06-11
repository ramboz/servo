---
status: DRAFT
dependencies: []
last_verified:
---

## Slice 010-02 — release-please-pipeline

**Goal:** Let release-please own versioning, CHANGELOG, tagging, and GitHub
releases from `main`'s commit history. End-to-end value: a merged `feat`
opens a release PR that bumps the version and updates the changelog; merging
it tags and publishes a release.

**DoR:**

- 010-01 landed (conventional-commit titles enforced; squash-merge in
  effect).
- Current version known (`plugin.json` = `0.1.0`) → seed the manifest at
  `0.1.0`.

**Acceptance Criteria:**

1. **Release workflow.** `.github/workflows/release.yml` runs
   `googleapis/release-please-action@v4` on push to `main` (+
   `workflow_dispatch`), with `permissions: contents: write,
   pull-requests: write`, exposing `release_created`, `tag_name`, and
   `version` outputs.
2. **Config.** `.github/release-please-config.json` uses
   `release-type: simple`, `include-v-in-tag: true`,
   `include-component-in-tag: false`; an `extra-files` entry bumps
   `.claude-plugin/plugin.json` `$.version`; `changelog-sections` match jig
   (`feat`/`fix`/`perf`/`docs` visible; `chore`/`refactor`/`test`/`ci`/
   `build` hidden).
3. **Manifest seeded.** `.github/.release-please-manifest.json` is
   `{ ".": "0.1.0" }`.
4. **Bump semantics (0.x).** A `feat` produces a minor bump
   (`0.1.0 → 0.2.0`), a `fix`/`perf` a patch (`0.1.0 → 0.1.1`); the release
   PR updates `plugin.json` + `CHANGELOG.md` + the manifest together.
5. **Tag + release.** Merging the release PR creates tag `vX.Y.Z` and a
   GitHub release.
6. **plugin.json becomes release-managed.** It is no longer hand-edited;
   this is stated where a maintainer will see it (a comment and/or a
   `CONTRIBUTING.md` line — the prose may land in 010-04).

**DoD:**

- [ ] All ACs pass; a release PR is observed bumping version + CHANGELOG
      (via the first real merge or a `workflow_dispatch` dry run) —
      evidence in the deviation log.
- [ ] `release-please-config.json` + `.release-please-manifest.json` are
      well-formed JSON and accepted by the action (no schema errors in the
      run log).
- [ ] Deviation log produced under this slice.
- [ ] Independent review pass completed before DONE.

**Anti-horizontal-phasing check:** After this slice, servo has a version
history and a changelog generated from commits — no manual version edits.
