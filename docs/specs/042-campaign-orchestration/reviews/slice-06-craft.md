---
slice: 042-06 — wave integration-review brief
pass: craft
verdict: pass
reviewer: general-purpose
reviewed_at: 2026-11-13T23:04:24Z
prompt_source: review.py pr-review docs/specs/042-campaign-orchestration/spec.md 042-06 skills/heartbeat/campaign.py skills/heartbeat/test_campaign.py --richer-skill none --non-interactive
substrate: non-interactive
---

VERDICT: pass (round 1)

The implementation matches the slice's stated scope exactly — a strictly read-only
`campaign review <id>` that emits ONE cross-wave brief giving each recorded item's
outcome, diff range (base..HEAD) and changed-file names as SCOPE (never diff
body/content), spawns no reviewer, and does only read-only git. It reuses sibling
idioms cleanly: `cmd_review`'s load-plan/read-ledger prologue mirrors `cmd_status`
(same `_fail` messages, same JSONDecodeError handling); the UNTRUSTED-DATA framing
reuses the `_build_brief` / `_build_item_prompt` BEGIN/END posture; `_git_capture`
mirrors `_git_head_sha`'s local read-only subprocess rather than heartbeat's
stdout-less `_git`, honoring the documented dependency-free invariant. It is Python
3.9-safe (`from __future__ import annotations`; all new generics quoted per file
convention; no runtime-evaluated `X | None`; None defaults). Tests run against a
REAL git repo with real worktrees and real diffs and cover the ACs well:
`_snapshot_campaign_state` + ReviewReadOnlyTests give a rigorous AC2/AC4 proof;
ReviewScopeNotSummaryTests proves content is not leaked via secret-marker absence;
ReviewInjectionTests pins untrusted-title containment; ReviewNoReviewerTests
structurally guards the no-loop/no-heartbeat invariant.

SPECIFIC ISSUES (non-blocking, folded into reconciliation):
- `test_base_resolves_from_wrapped_brief_when_state_lacks_start_head` was vacuous
  for its stated purpose (asserted only `self.base in out`, which the "worktree
  HEAD" line satisfies regardless of the fallback); strengthen to commit so
  HEAD != base and assert the `base sha:` line. (issue #124 instance 2)
- `cmd_review` `--output` write was unguarded (uncaught FileNotFoundError on a
  missing parent dir); make it fail closed via `_fail`.

RECONCILIATION NOTES: both nits should land in the deviation log, not block REVIEWED.
Dependency-free invariant and its documentation are sound.
