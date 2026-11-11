---
slice: 038-02 — role model placement
pass: compliance
verdict: pass
reviewer: jig:reviewer
reviewed_at: 2026-11-10T21:02:24Z
prompt_source: review.py implementation docs/specs/038-per-node-model-tiering/spec.md 038-02 <deliverables>
---

VERDICT: pass

REASONING:
All eight ACs satisfied: fullmatch validator refuses before any run dir/state (fresh, resume, goal); role args between --max-budget-usd and --settings; judge split gates --resume and the session/snapshot update (cost_basis reported, no breadcrumb); resume, goal and background forwarding, requested, advisor second signal and the planner hash (pinned legacy digest) all covered by tests that go red without the feature.

SPECIFIC ISSUES:
- [impl] AC7 exclusion uses "equals or hyphen-token names" the requested model (plan.md wording) — deviation-log.
- [impl] Planner docstrings and plan_edit_detected message still say budget/driver only.
- [impl] Legacy hash-less plan with a hand-added models block is overwritten; models: null hashes as absent but loop refuses it.
- [impl] Persisted state models trusted on resume without re-validation.
- [impl] SKILL.md Options / refusal tables lack --models / models_invalid.
- [impl] Two vacuous tests (no returncode/len assertions); one misnamed planner test.

RECONCILIATION NOTES:
- AC2 structured reason is on the stdout summary (016-03 convention); AC1 lstrip leniency; AC5 plan+resume are mutually exclusive (only --models replaces on resume); allow_escalation built ahead for 038-03; models persisted in goal state; --emit-routine-prompt drops --models silently; inherited-model advisor caveat (spec A1).
