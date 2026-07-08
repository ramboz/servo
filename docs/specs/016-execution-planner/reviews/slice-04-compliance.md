---
slice: 016-04 — skill-surface
pass: compliance
verdict: pass
reviewer: jig:reviewer (independent subagent, Opus)
reviewed_at: 2026-07-08T21:21:52Z
prompt_source: review.py implementation docs/specs/016-execution-planner/spec.md 016-04 <deliverables>
---

VERDICT: pass

All four ACs met; tests exercise them meaningfully, not superficially.
- AC1 (skill surface): SKILL.md ships `name: servo:execution-planner`, the fire
  triggers, the four Do-NOT-fire sibling delegations, the sibling-helper table
  (016-01/02/03), the Q&A block, and the "where it sits" pointer to
  `loop.py --plan` + ADR-0016. `SkillSurfaceTriggerTests` covers it.
- AC2 (refusal table): `RefusalTableTests` derives the reason set from
  `execution_plan.py` source via regex (`_defined_reasons()`), asserting each of
  the 8 `EnvError` reasons appears in SKILL.md — a future undocumented reason
  genuinely fails; the hardcoded `KNOWN_REASONS` is a secondary tripwire on the
  regex itself.
- AC3 (`--json`): `OutputModeTests` covers the human default, the exact success
  envelope keys, and the refusal-under-`--json` path (exit 2 + stderr reason + no
  envelope + no torn artifact). The change is purely additive — the `EnvError`
  handler runs before the `args.json` branch, so the env-error contract is
  identical in all modes.
- AC4 (install posture): `InstallPostureTests` asserts `execution-planner` is
  absent from `required.skills` (confirmed — contract lists only
  scaffold-init/quality-gate/agent-loop/oracle-hook/heartbeat) and the
  not-vendored posture note is present, matching the 015-04 host-tool precedent.

Cross-cutting: no design-principle violation (deterministic helper,
refuse-on-missing-prerequisite honored, `--json` carries no judgment). Approach
aligned; ADR-0016/0004/0018 cited; no new ADR or tech-debt deferral.

No blocking issues.

Reconciliation notes (for the deviation log):
- Module docstring Usage line omitted `--json` (now fixed in-pass).
- Envelope `schema_version` reuses the plan `SCHEMA_VERSION` (1); couples the
  envelope's versioning to the plan schema — note for a future envelope-only bump.
