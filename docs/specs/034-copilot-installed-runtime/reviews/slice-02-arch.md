---
slice: 034-02 - capability-refusal
pass: arch
verdict: pass
reviewer: jig:reviewer
reviewed_at: 2026-10-12T16:56:30Z
prompt_source: review.py arch-review docs/specs/034-copilot-installed-runtime/spec.md 034-02 skills/agent-loop/loop.py skills/agent-loop/test_copilot_capability.py skills/agent-loop/test_loop.py --richer-skill arch-review
substrate: not-shown
applied_skill: none
---

VERDICT: pass

REASONING:
Shared early refusal preserves oracle authority and prevents unsupported paid
dispatch/permission escalation without a backend framework. Version2 output
makes unavailable accounting explicit, while additive Claude v1 identity
preserves legacy compatibility without migration. Soundness, boundaries and
leanness support pass.

SPECIFIC ISSUES:
- [strength][impl] Public refusal precedes readiness, plan, Routine, detachment;
  direct run_loop also refuses.
- [strength][impl] Conflicting backend/host and nativev2 reject before bypassable
  schema/version checks. Legacy unmarked state retains bounded interpretation.
- [nit][impl] Hook prose falsely claimed re-driving next turn exactly as Claude.
  Corrected to static fixture mapping, unproved native continuation.

RECONCILIATION NOTES:
No blocking open questions or other deviation. Preserve legacy-origin limitation
and prototype-only adapter status. Unfinished native evaluation outside review.

Source: independent jig:reviewer guard-architecture actual envelope.
