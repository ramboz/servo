---
slice: 036-01 - bound-card-evidence
pass: craft
verdict: needs-changes
reviewer: general-purpose/card-craft
reviewed_at: 2026-10-15T23:47:00Z
prompt_source: review.py pr-review docs/specs/036-deterministic-design-evidence/spec.md 036-01 --richer-skill pr-review (craft-prompt.txt in closeout session)
substrate: shown
applied_skill: pr-review
shown_candidates: [pr-review:high-confidence, scout-pr-review:high-confidence, access:speculative, agent-development:speculative, arch-review:speculative, build-mcp-app:speculative, build-mcp-server:speculative, build-mcpb:speculative, cardputer-buddy:speculative, claude-automation-recommender:speculative, claude-md-improver:speculative, command-development:speculative, configure:speculative, example-command:speculative, example-skill:speculative, frontend-design:speculative, hook-development:speculative, m5-onboard:speculative, math-olympiad:speculative, mcp-integration:speculative, playground:speculative, plugin-settings:speculative, plugin-structure:speculative, project-artifact:speculative, scout-autotune:speculative, scout-bench-create:speculative, scout-memory-init:speculative, scout-scrum-master:speculative, session-report:speculative, skill-creator:speculative, skill-development:speculative, writing-hookify-rules:speculative]
---

VERDICT: needs-changes

REASONING:
The confirmed title-clipping blocker remains open on this unchanged candidate. Scoped source and proof inspection, including rehashing all 678 indexed files, found no additional high-confidence material blocker. Existing passing controls do not clear the clipping failure.

SPECIFIC ISSUES:
- [blocker][impl] skills/design-eval/card_capture.py:64-88 — B1. Ancestor overflow clipping is ignored. Wrapping the title in `<div style="height:0;overflow:hidden">` still reports `visible` and `textVisible` true. The supplied pinned-browser red confirms this. Account for ancestor clipping and add the corresponding regression before accepting visible-title comparisons.
- [strength][impl] skills/quality-gate/required_runtime.py:740-745 — The driver snapshot actually read for execution is checked against its approved full-file digest.
- [strength][impl] skills/quality-gate/required_runtime.py:704-722 — Preserved genuine runs demonstrate independent required veto and overall quality authority.

RECONCILIATION NOTES:
No style-only nits. Preserve the sealed-source proof as historical after correction; changed executable bytes require fresh bounded proof and required reviews. No tests, evaluator executions, judge calls, edits or GitHub writes were performed.
