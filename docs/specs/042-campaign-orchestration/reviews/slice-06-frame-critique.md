---
slice: 042-06 — wave integration-review brief
pass: frame-critique
verdict: pass
reviewer: general-purpose
reviewed_at: 2026-11-13T23:04:24Z
prompt_source: review.py frame-critique docs/specs/042-campaign-orchestration/spec.md 042-06 (R1 needs-changes -> R2 pass)
---

VERDICT: pass (round 2)

Round 1 (needs-changes) raised one [blocker] on assumption A3 as realized — "an
emitted scope-only brief lets a fresh reviewer find cross-item integration
problems" — in two parts: (a) host-driven worktrees were unlocatable (the worktree
was hardcoded to the `<campaign_dir>/worktrees/<item>` servo-driven convention,
while a host-driven worker runs in a host-chosen worktree never persisted), so the
ADR's MOTIVATING host-driven Copilot case got a diff-less brief; (b) the brief
over-claimed its one cross-item signal — same-path overlap cannot surface cross-file
API/contract drift (producer/consumer in disjoint files). Also: A3 was the only
ADR-0049 assumption (A1–A5) without a kill criterion.

Round 2 (pass): both sub-blockers are concretely closed and verified against the
files, not merely asserted.
- (a) RESOLVED: `cmd_record` persists the worker's `--worktree` on the ledger entry
  (`entry["worktree"]`) and `_review_item_scope` resolves that persisted host-chosen
  path before the servo-driven convention; base sha comes from the loop's
  `state.json start_head`. `test_host_driven_item_located_via_persisted_record_worktree`
  proves a worktree OUTSIDE the convention path is located and its diff carried.
- (b) RESOLVED: `_REVIEW_HOWTO` and the module "SCOPE, NOT SUMMARY" comment now state
  the changed-file list surfaces same-path overlap ONLY and NOT cross-file API/contract
  drift (reviewer must read the diffs). `test_brief_does_not_overclaim_the_file_list_signal`.
- A3 kill criterion added to ADR-0049 `## Kill criteria` (emitted-brief vs
  raw-worktrees trial + a degenerate "cannot carry the diffs at all" clause).

The frame no longer asserts A3 is true: it is explicitly unverified, the slice ships
deferred out of the parity release, and A3 is now falsifiable — the correct posture
for an unverified load-bearing assumption. The frame survives the strongest attack.
Non-blocking residuals (host owns the host-driven worktree lifecycle; an advisory
item has no recorded base sha) are disclosed in the slice `## Scope` and the ADR,
so they are known residuals, not flaws.
