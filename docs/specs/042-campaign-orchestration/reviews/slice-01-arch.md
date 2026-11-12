---
slice: 042-01 — plan and ledger
pass: arch
verdict: pass
reviewer: general-purpose
reviewed_at: 2026-11-12T20:50:04Z
prompt_source: review.py arch-review docs/specs/042-campaign-orchestration/spec.md 042-01 skills/heartbeat/campaign.py skills/heartbeat/test_campaign.py skills/heartbeat/SKILL.md --richer-skill none
substrate: shown
applied_skill: none
shown_candidates: [arch-review:high-confidence, access:speculative, adr-workflow:speculative, aem-author-load-rca:speculative, agent-development:speculative, analyze:speculative, breakdown-diagnosis:speculative, breakdown-to-next-report:speculative, bug-fix:speculative, build-dashboard:speculative, build-mcp-app:speculative, build-mcp-server:speculative, build-mcpb:speculative, capture:speculative, cardputer-buddy:speculative, challenge:speculative, clarify:speculative, claude-automation-recommender:speculative, claude-md-improver:speculative, claude-security:speculative, climb:speculative, cmr:speculative, code-health:speculative, command-development:speculative, configure:speculative, content-fidelity:speculative, contracts:speculative, cowork-plugin-customizer:speculative, create-cowork-plugin:speculative, create-viz:speculative, custom-connector:speculative, customer-inquiry-intake:speculative, cutline:speculative, daily-production-report:speculative, data-consolidate:speculative, data-context-extractor:speculative, data-visualization:speculative, design-eval:speculative, design-space-explore:speculative, eval-authoring:speculative, example-command:speculative, example-skill:speculative, explain:speculative, explore-data:speculative, faq:speculative, frame:speculative, frontend-design:speculative, get-content-scrape:speculative, hackathon:speculative, handoff:speculative, hook-development:speculative, independent-review:speculative, inspection-to-capa:speculative, local-dev:speculative, m5-onboard:speculative, math-olympiad:speculative, maturity:speculative, mcp-integration:speculative, memory-sync:speculative, migrate:speculative, migrate-to-copilot:speculative, morning-plant-pulse:speculative, name:speculative, ncr-writeup:speculative, office-hours:speculative, onboarding:speculative, orient:speculative, patterns:speculative, playground:speculative, plugin-settings:speculative, plugin-structure:speculative, pr-review:speculative, project-artifact:speculative, quote-build:speculative, receipts:speculative, reframe:speculative, release-check:speculative, release-slate:speculative, rfq-to-quote:speculative, root-cause-capa:speculative, routines:speculative, run-preflight:speculative, scaffold-init:speculative, scope-audit:speculative, scout:speculative, scout-autotune:speculative, scout-bench-create:speculative, scout-memory-init:speculative, scout-pr-review:speculative, scout-scrum-master:speculative, security-review:speculative, servo:agent-loop:speculative, servo:autonomy-readiness:speculative, servo:edd-suitability:speculative, servo:execution-planner:speculative, servo:heartbeat:speculative, servo:oracle-hook:speculative, servo:quality-gate:speculative, servo:scaffold-init:speculative, servo:spec-oracle:speculative, session-report:speculative, shape-release:speculative, siege:speculative, skill-creator:speculative, skill-development:speculative, slice-land:speculative, solo:speculative, spec-workflow:speculative, sql-queries:speculative, statistical-analysis:speculative, steward:speculative, supplier-escape-to-alternate-source:speculative, supplier-quote-request:speculative, tdd-loop:speculative, test-pr-in-dev:speculative, trade-study-report:speculative, validate-data:speculative, vision-elicitation:speculative, webpage-replica:speculative, write-query:speculative, writing-hookify-rules:speculative]
---

VERDICT: pass (round 2; round 1 was needs-changes on one documentation blocker)

Round 1: the four declared arch decisions are all sound — (a) the dynamic
`spec_from_file_location` load of loop.py's 038 `_validate_models` (servo's established
idiom; satisfies AC1's exact-validator/exact-messages where mirroring would drift; path
stable across source + 3 host layouts); (b) the mirrored, deliberately BLOCKING ledger lock
(vs the inbox's non-blocking — a record must not be dropped); (c) the versioned plan/ledger
schema + cost-unit seam; (d) `.servo/campaigns/` boundaries + the third dispatch surface.
Sole blocker: docs/architecture.md's "Runtime artifacts" map omitted `.servo/campaigns/`
and the plan/ledger data contract, plus the "third dispatch surface" ADR-0049 itself
promised.

Round 2 (pass): blocker resolved — an accurate, complete `.servo/campaigns/<id>/` bullet
documents the plan.json (schema_version:1) + ledger contract, tier/derived self_reported,
the blocking LOCK_EX vs the inbox's non-blocking lock, fail-closed init, the cost-unit rule,
`enforced_cost_usd` excluding self_reported, and the dynamic validator load, and it names
"servo's third dispatch surface, after heartbeat dispatch and run (ADR-0049 Consequences)";
the DoD gap is tracked in the reconciliation sweep. All four nits fixed (docstring leanness
reworded; `SERVO_CAMPAIGN_LOOP_PY` override; `_read_ledger` guard; substring-message noted).
OQ2 implemented — `--tier` gated to {servo, advisory} while `wrapped` stays in TIERS /
`_TIER_SELF_REPORTED` / `_status_summary` so 042-04's verifier can write a counted wrapped
entry. New strength: the `_cost_unit_error` fix keys on reliable signals (null ⇒ credit,
positive ⇒ USD, 0.0 accepted either way), fixing a latent host-agnostic-0.0 bug.

Deferred to the 042 parity-release / refinement-todo (non-blocking): OQ1 (promote the 038
validator to a declared shared surface, e.g. skills/_common/, rather than reaching into
loop.py's private function — test-guarded in the meantime); OQ3 (O(n) full-file atomic
rewrite per append — deliberate ADR-0004 crash-atomicity trade-off, negligible for a
bounded plan). Nothing blocks REVIEWED.

Reviewer: general-purpose subagent (read-only; arch-review, --richer-skill none), two rounds.
