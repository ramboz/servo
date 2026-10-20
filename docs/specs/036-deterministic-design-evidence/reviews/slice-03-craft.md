---
slice: 036-03 - static-source-contract-app
pass: craft
verdict: needs-changes
reviewer: jig:reviewer / 036-03-final-craft (fresh context, richer pr-review)
reviewed_at: 2026-10-20T17:44:12Z
prompt_source: review.py pr-review; files/036-03-visibility2-final-craft-prompt.txt; exact integration base2cd
substrate: shown
applied_skill: pr-review
shown_candidates: [pr-review:high-confidence, scout-pr-review:high-confidence, access:speculative, agent-development:speculative, arch-review:speculative, build-mcp-app:speculative, build-mcp-server:speculative, build-mcpb:speculative, cardputer-buddy:speculative, claude-automation-recommender:speculative, claude-md-improver:speculative, command-development:speculative, configure:speculative, example-command:speculative, example-skill:speculative, frontend-design:speculative, hook-development:speculative, m5-onboard:speculative, math-olympiad:speculative, mcp-integration:speculative, playground:speculative, plugin-settings:speculative, plugin-structure:speculative, project-artifact:speculative, scout-autotune:speculative, scout-bench-create:speculative, scout-memory-init:speculative, scout-scrum-master:speculative, session-report:speculative, skill-creator:speculative, skill-development:speculative, writing-hookify-rules:speculative]
---

VERDICT: needs-changes

REASONING:
The listed 036-03 deliverables and narrow Bug006 repair preserve the separation between source authority, APP observations and pure readback. However, the visibility walker still confuses suppression of an element's contents with absence of its own painted box, producing false required failures. The browser tests cover ancestor suppression but miss this self-applied case; no experiments, gates or readers were executed.

SPECIFIC ISSUES:
- [blocker][impl] skills/design-eval/static_contract.py:212-213 — `_PAINT` starts its walk at `el` and treats its own `contentVisibility==='hidden'` as complete absence. That property skips contents while leaving the element's background and border painted. An empty, explicitly sized 8×8 coloured marker can therefore receive four false FAILs. Distinguish self from ancestor suppression and add browser regressions for both.
- [nit][impl] skills/design-eval/test_static_contract.py:358 — The pure-readback test mocks policy validation, driver sealing, current binding and `_existing`. It verifies forwarding, but would still pass if `_existing` lost its ownership and closure checks. Add a temporary-filesystem test exercising those checks directly; retained offline evidence does not provide that recurring regression guard.
- [strength][impl] skills/design-eval/static_contract.py:342 — Atomic, per-required-ID settlement retains raw sample history and lets independently stable contradictions survive beside changing properties. The mixed-instability browser test exercises that distinction meaningfully.

RECONCILIATION NOTES:
Keep the change scoped to the requested `2cd33a4a08dea72a961662e24b5f11da5e7bdeb0` integration boundary. Record the self-versus-ancestor visibility correction and pure-reader coverage gap without changing SOURCE goals, family grammar or tolerances. Preserve historical invalid-hidden outcomes, the declared contents-opacity UNKNOWN boundary, and Jig's format-only NONCLEARING result; none establishes full-UI, font-face or backend truth.
