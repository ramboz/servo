---
slice: 042-01 — plan and ledger
pass: craft
verdict: pass
reviewer: general-purpose
reviewed_at: 2026-11-12T20:50:04Z
prompt_source: review.py pr-review docs/specs/042-campaign-orchestration/spec.md 042-01 skills/heartbeat/campaign.py skills/heartbeat/test_campaign.py skills/heartbeat/SKILL.md --richer-skill none
substrate: shown
applied_skill: none
shown_candidates: [independent-review:high-confidence, scout-pr-review:high-confidence, servo:agent-loop:high-confidence, servo:autonomy-readiness:high-confidence, servo:quality-gate:high-confidence, access:speculative, adr-workflow:speculative, aem-author-load-rca:speculative, agent-development:speculative, analyze:speculative, arch-review:speculative, breakdown-diagnosis:speculative, breakdown-to-next-report:speculative, bug-fix:speculative, build-dashboard:speculative, build-mcp-app:speculative, build-mcp-server:speculative, build-mcpb:speculative, capture:speculative, cardputer-buddy:speculative, challenge:speculative, clarify:speculative, claude-automation-recommender:speculative, claude-md-improver:speculative, claude-security:speculative, climb:speculative, cmr:speculative, code-health:speculative, command-development:speculative, configure:speculative, content-fidelity:speculative, contracts:speculative, cowork-plugin-customizer:speculative, create-cowork-plugin:speculative, create-viz:speculative, custom-connector:speculative, customer-inquiry-intake:speculative, cutline:speculative, daily-production-report:speculative, data-consolidate:speculative, data-context-extractor:speculative, data-visualization:speculative, design-eval:speculative, design-space-explore:speculative, eval-authoring:speculative, example-command:speculative, example-skill:speculative, explain:speculative, explore-data:speculative, faq:speculative, frame:speculative, frontend-design:speculative, get-content-scrape:speculative, hackathon:speculative, handoff:speculative, hook-development:speculative, inspection-to-capa:speculative, local-dev:speculative, m5-onboard:speculative, math-olympiad:speculative, maturity:speculative, mcp-integration:speculative, memory-sync:speculative, migrate:speculative, migrate-to-copilot:speculative, morning-plant-pulse:speculative, name:speculative, ncr-writeup:speculative, office-hours:speculative, onboarding:speculative, orient:speculative, patterns:speculative, playground:speculative, plugin-settings:speculative, plugin-structure:speculative, pr-review:speculative, project-artifact:speculative, quote-build:speculative, receipts:speculative, reframe:speculative, release-check:speculative, release-slate:speculative, rfq-to-quote:speculative, root-cause-capa:speculative, routines:speculative, run-preflight:speculative, scaffold-init:speculative, scope-audit:speculative, scout:speculative, scout-autotune:speculative, scout-bench-create:speculative, scout-memory-init:speculative, scout-scrum-master:speculative, security-review:speculative, servo:edd-suitability:speculative, servo:execution-planner:speculative, servo:heartbeat:speculative, servo:oracle-hook:speculative, servo:scaffold-init:speculative, servo:spec-oracle:speculative, session-report:speculative, shape-release:speculative, siege:speculative, skill-creator:speculative, skill-development:speculative, slice-land:speculative, solo:speculative, spec-workflow:speculative, sql-queries:speculative, statistical-analysis:speculative, steward:speculative, supplier-escape-to-alternate-source:speculative, supplier-quote-request:speculative, tdd-loop:speculative, test-pr-in-dev:speculative, trade-study-report:speculative, validate-data:speculative, vision-elicitation:speculative, webpage-replica:speculative, write-query:speculative, writing-hookify-rules:speculative]
---

VERDICT: pass

High-craft deliverables: fail-closed validation ordered strictly before any filesystem
mutation; a genuinely dependency-free design (loop.py's `_validate_models` loaded via
importlib, lock/atomic-write discipline mirrored not imported); and pure helpers cleanly
separated from the IO subcommands so they are unit-tested directly. 59 tests (15 subtests)
green under /tmp/servo-venv. The lock + os.replace discipline faithfully mirrors
heartbeat.py with a deliberate, well-documented divergence (blocking LOCK_EX vs heartbeat's
non-blocking, because a record is unique data that must not be dropped). No blockers.

Nits (deviation-log material; all addressed in round 2):
- `OUTCOME_SCHEMA_VERSION`/`OUTCOME_RESULTS` hand-copied from loop.py with no parity guard,
  asymmetric with the dynamically-loaded `models` validator — real forward-drift risk. Now
  pinned by `test_outcome_constants_track_loop`.
- the validator-parity test was near-vacuous (compares loop's fn to itself); meaningful
  parity is carried by the end-to-end stderr match + the escalation-ladder test.
- `_read_ledger` json.loads unguarded → a corrupt line crashed read-only `status`; now
  fails closed rc=2.
- overloaded `budget_unit is None` sentinel (cosmetic; unreachable from an init-validated
  plan).
Strengths: derived `self_reported` (an advisory worker can't launder cost into enforced
spend), fail-closed-before-write with `exist_ok=False`, the AST-based dependency-free test,
the documented blocking-lock rationale, `_is_number` excluding bool.

Reviewer: general-purpose subagent (read-only; pr-review baseline, --richer-skill none).
