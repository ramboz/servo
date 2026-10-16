---
slice: 036-01 - bound-card-evidence
pass: arch
verdict: needs-changes
reviewer: general-purpose/card-architecture
reviewed_at: 2026-10-15T23:47:00Z
prompt_source: review.py arch-review docs/specs/036-deterministic-design-evidence/spec.md 036-01 --richer-skill arch-review (arch-prompt.txt in closeout session)
substrate: shown
applied_skill: arch-review
shown_candidates: [arch-review:high-confidence, access:speculative, agent-development:speculative, build-mcp-app:speculative, build-mcp-server:speculative, build-mcpb:speculative, cardputer-buddy:speculative, claude-automation-recommender:speculative, claude-md-improver:speculative, command-development:speculative, configure:speculative, example-command:speculative, example-skill:speculative, frontend-design:speculative, hook-development:speculative, m5-onboard:speculative, math-olympiad:speculative, mcp-integration:speculative, playground:speculative, plugin-settings:speculative, plugin-structure:speculative, pr-review:speculative, project-artifact:speculative, scout-autotune:speculative, scout-bench-create:speculative, scout-memory-init:speculative, scout-pr-review:speculative, scout-scrum-master:speculative, session-report:speculative, skill-creator:speculative, skill-development:speculative, writing-hookify-rules:speculative]
---

VERDICT: needs-changes

REASONING:
No additional architecture-shaped blocker found. Module boundaries and overall-gate authority are coherent, but the witnessed visibility defect remains unresolved.

SPECIFIC ISSUES:
- [blocker][impl] skills/design-eval/card_capture.py:64-88 — Existing ancestor-overflow defect supplies false visibility facts to comparisons. The pinned browser red remains blocking.
- [strength][impl] skills/quality-gate/required_runtime.py:740-745 — Validates the actually read full oracle, including quality SEED.
- [strength][impl] skills/quality-gate/gate_consumer.py:139-149 — Reuses complete output-closure validation without re-grading.

RECONCILIATION NOTES:
Inspected all three actual outcomes and selected proof bindings. Preserve their source epoch; correction requires affected proof and reviews. No writes, tests or judges.
