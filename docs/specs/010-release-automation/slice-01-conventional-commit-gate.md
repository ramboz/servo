---
status: DONE
dependencies: []
last_verified: 2026-06-11
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
  → **DECIDED: jig parity exactly.** `pr-title.yml` uses that type set,
  `requireScope: true`, `subjectPattern: ^[a-z].*[^.]$`.
- Squash-merge is (or will be set as) the repo's merge mode, so the PR title
  becomes the `main` commit subject. → **CONFIRMED already configured:**
  `gh api repos/ramboz/servo` reports `allow_squash_merge: true` with
  `allow_merge_commit: false` and `allow_rebase_merge: false`, and
  `squash_merge_commit_title: PR_TITLE` — so the squashed `main` subject *is*
  the (validated) PR title. No settings change needed.

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

- [x] All ACs pass (verified against a sample PR or the action's logs).
      _AC1–AC3 met in-artifact (independent review + YAML parse). **AC4 proven
      live on PR #2** (the PR that introduces `pr-title.yml`): the conforming
      title `feat(release): …` **passed** the check (runs 27378113585 /
      27378201932), and a deliberately bad title `Update stuff.` **failed** it
      (run 27378162745, then the good title was restored)._
- [x] Squash-merge confirmed as the repo merge mode and recorded
      (branch-protection enforcement is out-of-band / server-side). _`gh api
      repos/ramboz/servo`: `allow_squash_merge: true`, `allow_merge_commit:
      false`, `allow_rebase_merge: false`, `squash_merge_commit_title:
      PR_TITLE` — squash is the only mode and the squashed subject is the PR
      title. No required-check branch protection is set (out-of-band, per
      ADR-0007)._
- [x] Deviation log produced under this slice. _Below._
- [x] Independent review pass completed before DONE. _Independent reviewer
      subagent, 2026-06-11 — **PASS, no blockers.** Confirmed pr-title.yml is a
      faithful jig mirror (ruleset identical; differs only by comment header +
      `on:` quoting) and squash-merge is live._

**Anti-horizontal-phasing check:** After this slice, every PR title is
release-please-readable before it can merge — the precondition for 010-02.

**Deviation log:**

- **pr-title.yml = jig parity.** `amannn/action-semantic-pull-request@v5` on
  `pull_request` (opened/edited/synchronize/reopened), `permissions:
  pull-requests: read`, the jig type set, `requireScope: true`,
  `subjectPattern: ^[a-z].*[^.]$` + the lowercase/no-period error message.
  The only diffs from jig's file are a servo context-header comment and the
  `"on":` quoting (servo house style, see `ci.yml`).
- **Squash-merge was already configured** (not changed by this slice) — see
  the DoD note. So the 010-02 precondition (PR title → `main` subject) already
  holds.
- **AC4 self-proof (live on PR #2).** Rather than a throwaway sample PR, the
  gate was proven on this spec's own PR: the conforming title passed (runs
  27378113585 / 27378201932); editing the title to `Update stuff.` made the
  `PR Title` check **fail** (run 27378162745); the good title was then restored
  (release-please reads it on merge). Both branches of AC4 demonstrated.
- **Branch protection not added.** The workflow enforces title *shape*; making
  the check *required* for merge is server-side branch protection, explicitly
  out-of-band per ADR-0007 — not in this slice.
