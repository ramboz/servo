---
status: DRAFT
dependencies: []
last_verified:
---

## Slice 010-01 — conventional-commit-gate

**Goal:** Enforce conventional-commit PR titles so squash-merged commit
subjects on `main` are machine-readable by release-please. End-to-end
value: every PR's title is validated before it can merge — the precondition
010-02 builds on.

**DoR:**

- Agreement on allowed types + whether scope is required. _(Recommended:
  jig parity — `feat, fix, perf, docs, chore, refactor, test, build, ci`;
  `requireScope: true`; subject lowercase, no trailing period.)_
- Squash-merge is (or will be set as) the repo's merge mode, so the PR title
  becomes the `main` commit subject.

**Acceptance Criteria:**

1. **PR-title workflow.** `.github/workflows/pr-title.yml` runs
   `amannn/action-semantic-pull-request@v5` on `pull_request`
   (`opened`, `edited`, `synchronize`, `reopened`) with
   `permissions: pull-requests: read`.
2. **Allowed types.** The configured type set matches the agreed list
   (recommended: `feat, fix, perf, docs, chore, refactor, test, build,
   ci`).
3. **Scope + subject rules.** Scope is required (`requireScope: true`) and
   the subject must start lowercase and not end with a period
   (`subjectPattern: ^[a-z].*[^.]$`) — jig parity.
4. **Non-conforming titles fail.** A PR titled e.g. `Update stuff.` fails
   the check; `feat(agent-loop): add resume guard` passes.

**DoD:**

- [ ] All ACs pass (verified against a sample PR or the action's logs).
- [ ] Squash-merge confirmed as the repo merge mode and recorded
      (branch-protection enforcement is out-of-band / server-side).
- [ ] Deviation log produced under this slice.
- [ ] Independent review pass completed before DONE.

**Anti-horizontal-phasing check:** After this slice, every PR title is
release-please-readable before it can merge — the precondition for 010-02.
