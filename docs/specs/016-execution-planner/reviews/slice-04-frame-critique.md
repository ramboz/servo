---
slice: 016-04 — skill-surface
pass: frame-critique
verdict: pass
reviewer: jig:reviewer (independent subagent, Opus)
reviewed_at: 2026-07-08T21:05:32Z
prompt_source: review.py frame-critique docs/specs/016-execution-planner/spec.md 016-04 <slice>
---

VERDICT: pass

Adversarial pre-implementation frame-critique of 016-04's load-bearing
assumptions (frame_review derived true from the `## Assumptions` section).

Highest-risk assumption A1 — that `execution-planner` should NOT get a
`required.skills` entry, reversing the pre-SPIDR goal ("+ the install-contract
entry (007)"). Independently confirmed grounded, not asserted:
- `install-contract.json` `required.skills` is exactly `{scaffold-init,
  quality-gate, agent-loop, oracle-hook, heartbeat}`; `spec-oracle`,
  `edd-suitability`, `design-eval`, `content-fidelity` are all absent.
- The 015-04 follow-up reverted vendoring `edd-suitability` for the cited
  reason ("no vendored runtime skill invokes it").
- No runtime skill invokes the compiler: `loop.py --plan` reads `plan.json`
  from disk (`plan_path.read_text()` → `json.loads`), never shells to
  `execution_plan.py`. Per ADR-0018 the heartbeat is spec-less → never
  compiles/consumes a plan.
- Kill criterion tested repo-wide and came back negative.

Secondary (non-blocking): A2 is true partly because `verify_install_surfaces.sh`
has no "verify-present-but-don't-vendor" tier (a pre-existing, accepted
limitation) — `/servo:execution-planner` discoverability rests on Claude Code
plugin `skills/*/SKILL.md` discovery, identical to the `edd-suitability`
posture. A3 grounded (human default line + closed {0,2} exit contract confirmed
in execution_plan.py:374-413; the eight refusal reasons all appear verbatim).

Deviation-log items flagged by the reviewer for later capture: (1) dropped
`required.skills` entry vs the original goal; (2) skill name `/servo:execution-plan`
→ `/servo:execution-planner`; (3) ADR-0018 removal of heartbeat plan-reuse.

The frame survives the strongest attack.
