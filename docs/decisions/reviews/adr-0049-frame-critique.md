---
adr: 0049
pass: frame-critique
verdict: needs-changes
reviewer: jig:reviewer
reviewed_at: 2026-11-10T22:33:58Z
prompt_source: review.py frame-critique docs/decisions/adr-0049-campaign-orchestration.md (round 3)
---

VERDICT: needs-changes

REASONING:
Round 3. Round-2 findings fixed; the frame (Option A, three tiers, ordering) survives. One load-bearing claim exposed: the named verification mechanism (a hash of _tree_snapshot, a git-status porcelain set) does not check what the ADR claims — it misses post-halt edits to already-modified files and fails compliant workers who commit.

SPECIFIC ISSUES:
- [spec] Fingerprint must cover content + base (HEAD at halt + diff hash + untracked contents); record-before-commit ordering; re-render outcome fields from loop state by run_id; drop "no git operations".
- [spec] OQ3: servo-driven Claude first is a baseline, not the motivating case — say so.
- [spec] Minor: spec 042 lists A1-A4 (missing A5); Cons line omits wrapped verification; assumption order.
