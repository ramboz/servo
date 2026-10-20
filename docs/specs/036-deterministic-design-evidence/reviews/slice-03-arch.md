---
slice: 036-03 - static-source-contract-app
pass: arch
verdict: pass
reviewer: jig:reviewer / 036-03-final-architecture (fresh context, richer arch-review)
reviewed_at: 2026-10-20T23:24:14Z
prompt_source: review.py arch-review; files/036-03-visibility3-arch-prompt.txt; exact integration base2cd/code445e69ef/docsef62ee3
substrate: shown
applied_skill: arch-review
shown_candidates: [arch-review:high-confidence, access:speculative, agent-development:speculative, build-mcp-app:speculative, build-mcp-server:speculative, build-mcpb:speculative, cardputer-buddy:speculative, claude-automation-recommender:speculative, claude-md-improver:speculative, command-development:speculative, configure:speculative, example-command:speculative, example-skill:speculative, frontend-design:speculative, hook-development:speculative, m5-onboard:speculative, math-olympiad:speculative, mcp-integration:speculative, playground:speculative, plugin-settings:speculative, plugin-structure:speculative, pr-review:speculative, project-artifact:speculative, scout-autotune:speculative, scout-bench-create:speculative, scout-memory-init:speculative, scout-pr-review:speculative, scout-scrum-master:speculative, session-report:speculative, skill-creator:speculative, skill-development:speculative, writing-hookify-rules:speculative]
---

VERDICT: pass

REASONING:
Architecture-only pass against stacked base `2cd33a4a08dea72a961662e24b5f11da5e7bdeb0`, current code `445e69ef` and docs `ef62ee3`, applying the technical, reliability, contract-evolution and trust-boundary rubric to accepted ADR-0045 and the unchanged `static-app-contract.md`. The implementation preserves source authority, separately versioned APP interpretation and existing command/refusal/required-policy/output seams without adding a controller or scoring framework. Snapshot/runtime/output closure and separate pure verdict/currentness readers fit the declared same-trust local model. This read-only source/artifact review neither reruns compliance/craft nor establishes current `/3` APP authority, empirical proof or release clearance.

SPECIFIC ISSUES:
- [strength][impl] `skills/design-eval/static_contract.py:560` — Source consumption uses pinned identity-only `inspect()`; APP policy validation separately preserves source constraints and the explicit normalizer map.
- [strength][impl] `skills/design-eval/static_snapshot.py:124` — Verification binds source inputs, copy recipe, outputs and independently inventoried delivery; acquisition checks actual loaded bodies rather than trusting a URL or build label.
- [strength][impl] `skills/design-eval/static_contract.py:544` — Visibility `/3` and explicit content-visibility semantics enter policy identity. Exact normalizer/helper validation prevents silently applying this correction under unchanged `/2` approval.
- [strength][impl] `skills/design-eval/static_contract.py:1071` — Currentness readback checks ownership, inventories and selected delivery while preserving the producer verdict. The generic output-reference consumer remains independent of APP comparison semantics.
- [nit][impl] `skills/design-eval/test_static_contract.py:375` — Retain the recorded nonblocking regression gap: mocking `_existing` proves forwarding/no-rescore plumbing, but does not protect actual ownership/closure validation. The offline mutation audit supplies bounded evidence, not recurring test coverage.

RECONCILIATION NOTES:
Record the `/2`→`/3` own-box/contents distinction without rewriting ADR-0045, SOURCE/C0, output schema or historical outcomes. Keep the `/2` execution suspension explicit; fresh `/3` policies, installed definitions/grade hashes, separate execution release and affected APP proof remain pending, alongside craft and lifecycle/publication gates. Preserve backend/pixel/actual-face/full-app residuals. Existing Jig's actual format refusal precedes semantic validation and establishes no positive 0.2 bridge or Jig DONE.
