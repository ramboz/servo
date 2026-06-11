---
status: DONE
dependencies: []
last_verified: 2026-06-11
---

## Slice 010-04 — contributing-and-docs

**Goal:** Document the merge + release conventions and update the install
docs to reflect automated releases; reconcile 007-05's manual-recipe note.
End-to-end value: the release process is written down and matches what CI
actually does.

**DoR:**

- 010-01..03 landed (the flow the docs describe actually exists).

**Acceptance Criteria:**

1. **CONTRIBUTING.md.** A `CONTRIBUTING.md` documents: squash-merge,
   conventional-commit PR titles, the prefix → version-bump table
   (`feat` → minor, `fix`/`perf` → patch, `feat!`/`BREAKING CHANGE` →
   major, `chore`/`docs`/`refactor`/`test`/`ci`/`build` → no release), and
   the release sequence (merge work → release-please opens a release PR →
   merge the release PR → tag + GitHub release + uploaded asset).
2. **README updated.** The "Installing servo" / release section reflects
   automated releases: the GitHub release + asset is the primary install
   path; the manual `build_release_zip.py` recipe is documented as the
   local / fallback path, not the release mechanism.
3. **007-05 reconciled.** The earlier "manual recipe only / no
   release-please" deviation is noted as superseded by spec 010 (a pointer
   in 007-05's deviation log or this slice's, plus the README change).
4. **Docs guard green.** `scripts/test_docs_install.py` stays green — no
   stale paths, and the asset name still matches the real builder output.

**DoD:**

- [x] All ACs pass; docs guard green. _AC1–AC4 met. `CONTRIBUTING.md` covers
      squash-merge + conventional titles + the prefix→bump table + the release
      sequence; README reframed (release asset primary, manual build fallback);
      007-05 reconciled. `scripts/test_docs_install.py` → 9 passed (incl. the
      rewritten bump-robust artifact-name guard)._
- [x] `CONTRIBUTING.md` reviewed for accuracy against the shipped
      `pr-title.yml` / `release.yml`. _Independent reviewer cross-checked the
      bump table + type set + release sequence against the shipped workflows —
      consistent._
- [x] Deviation log produced under this slice. _Below._
- [x] Independent review pass completed before DONE. _Independent reviewer,
      2026-06-11 — **PASS, no blockers**, and independently re-ran the
      simulated-bump proof below._

**Anti-horizontal-phasing check:** After this slice, the release process is
written down and matches what CI does — not tribal knowledge.

**Deviation log:**

- **CONTRIBUTING.md (AC1).** New file: squash-merge + the `<type>(<scope>):
  <subject>` rule (jig type set, required scope, lowercase/no-period subject),
  the `0.x` prefix→bump table (`feat`→minor, `fix`/`perf`→patch,
  `feat!`/`BREAKING CHANGE`→major, `chore`/`docs`/`refactor`/`test`/`ci`/
  `build`→no release), and the 4-step release sequence (merge work →
  release-please opens a release PR → merge it → tag + release + uploaded
  asset), plus the local pre-PR gate commands.
- **README reframed (AC2).** The `### Release recipe` section now leads with
  **automated releases**: the primary install artifact is the
  `servo-v<version>.zip` asset on the latest GitHub release; the manual
  `build_release_zip.py` recipe is explicitly the local/fallback path, "not how
  releases are published," and notes `plugin.json`'s version is release-managed.
- **007-05 reconciled (AC3).** A dated **SUPERSEDED** note was added to
  007-05's deviation log pointing at spec 010 + ADR-0007.
- **Discovered + fixed: version-pinning that would self-break the release
  pipeline (scope extension, documented).** The 007-05 docs guard
  (`test_documented_zip_command_matches_real_output_name`) and two
  `test_verify_install.py` assertions pinned the *literal* `0.1.0` while reading
  the **release-managed** `plugin.json`. release-please bumps `plugin.json` on
  every release **without** touching README/tests, so the first bump would have
  reddened the *release PR's own* `ci.yml` (full suite + install-surfaces both
  run on `pull_request`) — silently breaking the pipeline this spec ships.
  Fixes, all behavior-preserving:
  - README: every `servo-v0.1.0.zip` → `servo-v<version>.zip` placeholder.
  - Docs guard rewritten → `test_documented_zip_artifact_name_is_version_neutral`:
    asserts the `servo-v<version>.zip` *shape* is documented **and** that no
    concrete `\d+\.\d+\.\d+` is pinned (so staleness can't be reintroduced).
  - `test_verify_install.py`: a module-level `PLUGIN_VERSION` read from
    `plugin.json` replaces the two literal `"0.1.0"` assertions, so they assert
    "verify_install reports the manifest version" rather than a frozen string.
  - **Proven** by simulating a bump (`plugin.json` → `9.9.9`): the docs +
    verify guards stayed green (37 passed) and the builder produced + smoke-
    passed `servo-v9.9.9.zip`; `plugin.json` restored to `0.1.0`. Independently
    re-run by the reviewer with the same result.
  This is strictly necessary for 010's goal (a release that doesn't break CI),
  so it was folded into this docs slice rather than deferred.
- **Docs guard stayed green (AC4).** `scripts/test_docs_install.py` → 9 passed;
  the rewritten guard preserves the original intent (catch a wrong/invented
  artifact name) while surviving release bumps. Confirmed **on the runner** in
  PR #2's CI (run 27378113787: `test (3.11)`/`test (3.12)`/`install-surfaces`
  all green), so this slice is fully verified without a main-merge dependency.
