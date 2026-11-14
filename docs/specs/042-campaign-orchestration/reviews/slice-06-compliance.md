---
slice: 042-06 — wave integration-review brief
pass: compliance
verdict: pass
reviewer: general-purpose
reviewed_at: 2026-11-13T23:04:24Z
prompt_source: review.py implementation docs/specs/042-campaign-orchestration/spec.md 042-06 skills/heartbeat/campaign.py skills/heartbeat/test_campaign.py
---

VERDICT: pass (round 1)

All four ACs of slice 042-06 are met by `campaign review` and its tests, and all
Review-tagged tests pass against the pinned venv. `cmd_review` emits exactly ONE
host-agnostic cross-wave brief over the recorded items (wave = `_latest_outcomes`,
which correctly excludes coordinator-decision entries), carrying each item's
outcome, diff range, worktree and changed-file name-status as SCOPE while
deliberately omitting diff bodies; it is structurally read-only (only
`rev-parse` / `diff --name-status` / `ls-files --others`) and loads neither loop.py
nor heartbeat.py. The tests are meaningful and non-vacuous: the scope-not-summary
guard asserts file NAMES appear while `SECRET_*` diff bodies do not; the read-only
guard byte-snapshots campaign state plus target/worktree git state; the no-reviewer
guard points the module env hooks at nonexistent paths and still exits 0. The three
vendored host copies of campaign.py are byte-identical to the canonical; test files
are source-only by repo convention.

SPECIFIC ISSUES (all non-blocking, folded into reconciliation):
- `base..base` reads as "no changes" when a worker's changes are uncommitted
  (cosmetic; the name-status list + the `git diff <base>` HOWTO still carry them).
- `--output` to a path whose parent dir does not exist raised an uncaught error
  rather than the module's fail-closed rc=2 discipline.

RECONCILIATION NOTES:
- AC1 "collects the diffs" is implemented as "collect diff SCOPE, not diff content",
  resolving AC1 against AC3's "without servo summarising"; documented in-code and in
  the deviation log.
- No `## Tasks` gaps; ADR-0049 A3 cited; DoD waives arch review (emits a brief,
  changes no contract); no new TODO/FIXME; dependency-free invariant preserved; no
  principle violations.
