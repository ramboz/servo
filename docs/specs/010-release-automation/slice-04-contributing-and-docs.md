---
status: DRAFT
dependencies: []
last_verified:
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

- [ ] All ACs pass; docs guard green.
- [ ] `CONTRIBUTING.md` reviewed for accuracy against the shipped
      `pr-title.yml` / `release.yml`.
- [ ] Deviation log produced under this slice.
- [ ] Independent review pass completed before DONE.

**Anti-horizontal-phasing check:** After this slice, the release process is
written down and matches what CI does — not tribal knowledge.
