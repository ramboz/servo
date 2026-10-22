---
slice: 036-03 - static-source-contract-app
pass: craft
verdict: pass
reviewer: jig:reviewer / 036-03-visibility3-full-craft (fresh context, richer pr-review)
reviewed_at: 2026-10-21T01:01:01Z
prompt_source: review.py pr-review; original exact prompt archived privately before publication cleanup
substrate: shown
applied_skill: pr-review
shown_candidates: [pr-review:high-confidence, scout-pr-review:high-confidence, access:speculative, agent-development:speculative, arch-review:speculative, build-mcp-app:speculative, build-mcp-server:speculative, build-mcpb:speculative, cardputer-buddy:speculative, claude-automation-recommender:speculative, claude-md-improver:speculative, command-development:speculative, configure:speculative, example-command:speculative, example-skill:speculative, frontend-design:speculative, hook-development:speculative, m5-onboard:speculative, math-olympiad:speculative, mcp-integration:speculative, playground:speculative, plugin-settings:speculative, plugin-structure:speculative, project-artifact:speculative, scout-autotune:speculative, scout-bench-create:speculative, scout-memory-init:speculative, scout-scrum-master:speculative, session-report:speculative, skill-creator:speculative, skill-development:speculative, writing-hookify-rules:speculative]
---

VERDICT: pass

REASONING:
Against the specified `2cd33a4a…` integration boundary, I found no remaining craft blocker. The qualified test snapshot has a low 0.19 test/code LOC ratio, but the reviewed browser assertions meaningfully discriminate behavior. This was source/retained-evidence review only, without command execution or AC-compliance re-evaluation.

SPECIFIC ISSUES:
- [nit][impl] skills/design-eval/test_static_contract.py:358 — Still open: mocking `_existing` leaves actual ownership and output-closure checks without a recurring direct regression here. Retain the nonblocking temporary-filesystem test follow-up; the offline mutation audit does not fix this gap.
- [strength][impl] skills/design-eval/static_contract.py:213 — The correction excludes self-applied content suppression only from the box clause. The actual text-parent guard at line 262 remains intact, preserving hidden-text discrimination.
- [strength][impl] skills/design-eval/test_static_browser.py:21 — Native visibility, geometry and PNG assertions distinguish own-box retention from ancestor suppression. Independent display/opacity failures and transform UNKNOWN remain covered.
- [strength][impl] skills/quality-gate/required_runtime.py:903 — Reusing existing pin validation preserves original refusal causes and exactly-once inventory without introducing deduplication machinery. The regression at skills/spec-oracle/test_required_gate.py:195 exercises mutations and restored success.

RECONCILIATION NOTES:
Record the resolved blocker and still-open nit. Keep contents-opacity UNKNOWN
and the limits on universal CSS, pixels, actual faces, full UI, backend and
hostile-page claims. This craft PASS grants no release, lifecycle-completion
or merge authority.

## Publication cleanup (2026-10-22)

Application-specific proof discussion was removed at the owner's request.
Exact original review/prompt bytes remain archived privately. The retained
verdict and generic code findings are historical, not a fresh review or
approval of this edited export; old selected identities are not rebound.
