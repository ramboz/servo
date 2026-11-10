---
slice: 038-02 — role model placement
pass: arch
verdict: pass
reviewer: jig:reviewer (arch-review)
reviewed_at: 2026-11-10T21:02:24Z
prompt_source: review.py arch-review docs/specs/038-per-node-model-tiering/spec.md 038-02 <deliverables> --richer-skill arch-review
substrate: shown
applied_skill: arch-review
shown_candidates: [arch-review:high-confidence, access:speculative, adr-workflow:speculative, agent-development:speculative, analyze:speculative, bug-fix:speculative, build-dashboard:speculative, build-mcp-app:speculative, build-mcp-server:speculative, build-mcpb:speculative, cardputer-buddy:speculative, clarify:speculative, claude-automation-recommender:speculative, claude-md-improver:speculative, code-health:speculative, command-development:speculative, configure:speculative, contracts:speculative, cowork-plugin-customizer:speculative, create-cowork-plugin:speculative, create-viz:speculative, data-context-extractor:speculative, data-visualization:speculative, example-command:speculative, example-skill:speculative, explain:speculative, explore-data:speculative, frontend-design:speculative, hook-development:speculative, independent-review:speculative, m5-onboard:speculative, math-olympiad:speculative, mcp-integration:speculative, memory-sync:speculative, migrate:speculative, orient:speculative, playground:speculative, plugin-settings:speculative, plugin-structure:speculative, pr-review:speculative, project-artifact:speculative, reframe:speculative, scaffold-init:speculative, scout-autotune:speculative, scout-bench-create:speculative, scout-memory-init:speculative, scout-pr-review:speculative, scout-scrum-master:speculative, security-review:speculative, session-report:speculative, skill-creator:speculative, skill-development:speculative, slice-land:speculative, spec-workflow:speculative, sql-queries:speculative, statistical-analysis:speculative, tdd-loop:speculative, validate-data:speculative, vision-elicitation:speculative, write-query:speculative, writing-hookify-rules:speculative]
---

VERDICT: pass

REASONING:
Boundaries hold: no jig dependency; placement only in launcher argv; agents/*.md model-neutral; Copilot still refused upstream; plan schema_version and clamp code untouched; state models additive with setdefault backfill (ADR-0004). Design follows ADR-0047 D1-A (one validator, block-level precedence) and D2-A (narrow split predicate); default path pinned byte-identical; planner hash backward compatible against a pinned digest. Leanness findings are small.

SPECIFIC ISSUES:
- [nit][impl] escalation acceptance body is 038-03 work built early — log as deviation.
- [nit][impl] _NULL_REQUESTED is dead code.
- [nit][impl] Planner docstrings / plan_edit_detected message describe only budget/driver.
- [nit][impl] context_fill_ratio alternates between runner and fresh judge sessions under the split — document.
- [nit][spec] Hyphen-token advisor heuristic can mark the executor's entry when the model is inherited.
- [strength][impl] One split predicate; resume replacement after all refusals; models hashed only when present; leading-'-' guard.

RECONCILIATION NOTES:
- Copilot branch of _invoke_claude drops role_args (unreachable today; spec 041 must honour or refuse it).
- ADR-0016 plan-shape example is behind (budget_hash, models) — pointer only with owner approval.
