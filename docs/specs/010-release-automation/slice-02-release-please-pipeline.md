---
status: IN_PROGRESS
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

- [~] All ACs pass; a release PR is observed bumping version + CHANGELOG
      (via the first real merge or a `workflow_dispatch` dry run) —
      evidence in the deviation log. _AC1–AC3 + AC6 met in-artifact (workflow
      shape, config, manifest, and the "release-managed, do-not-hand-edit"
      note in CONTRIBUTING/README). **AC4 (0.x bump semantics) and AC5 (tag +
      GitHub release) plus the *observed* release PR are deferred to
      main-merge** — release-please only acts on `main`'s history; it cannot
      open a release PR from a feature branch. Captured in the main-merge
      verification._
- [~] `release-please-config.json` + `.release-please-manifest.json` are
      well-formed JSON and accepted by the action (no schema errors in the
      run log). _**Well-formed JSON verified locally** (both parse; the
      config package key `.` matches the manifest key `.`; config is
      byte-identical to jig's proven file). "Accepted by the action" (no
      schema errors) is confirmed in the first `release.yml` run on main —
      deferred._
- [x] Deviation log produced under this slice. _Below._
- [x] Independent review pass completed before DONE. _Independent reviewer,
      2026-06-11 — **PASS, no blockers.** Verified the release-please job
      shape/outputs/permissions and that the config is a faithful jig mirror._

**Anti-horizontal-phasing check:** After this slice, servo has a version
history and a changelog generated from commits — no manual version edits.

**Deviation log:**

- **release.yml release-please job + config + manifest = jig parity.** Job
  uses `googleapis/release-please-action@v4` on `push: branches: [main]` +
  `workflow_dispatch`, `permissions: contents: write, pull-requests: write`,
  exposing `release_created` / `tag_name` / `version`. The config is
  byte-identical to jig's (`release-type: simple`, `include-v-in-tag: true`,
  `include-component-in-tag: false`, `extra-files` bumping
  `.claude-plugin/plugin.json` `$.version`, jig's `changelog-sections`). The
  manifest is seeded at `{ ".": "0.1.0" }` (servo's current version).
- **Why the live items are main-only.** release-please reads `main`'s
  conventional-commit history and opens/maintains a release PR *against main*.
  On a feature branch there is nothing for it to do, so AC4/AC5 and "observe a
  release PR" can only be exercised after this work merges to `main`. This is
  the inherent shape of the tool, acknowledged by the DoD's "first real merge
  or workflow_dispatch" wording.
- **First-bump robustness pre-secured in 010-04.** Because release-please will
  bump `plugin.json` on the first release, version-pinned docs/tests would
  redden the *release PR's own* CI. 010-04 de-pinned them and proved (via a
  simulated bump) the tree survives — so the first release PR will be green.
- **`GITHUB_TOKEN` suffices; no cross-workflow trigger gap.** The `package`
  job (010-03) lives in the *same* `release.yml` run as release-please
  (`needs:`), so it executes in the same invocation when a release is created
  — not via a separate workflow that `GITHUB_TOKEN` would fail to trigger.
