---
slice: 038-03 — plateau escalation ladder
pass: craft
verdict: pass
reviewer: jig:reviewer
reviewed_at: 2026-11-10T22:28:13Z
prompt_source: review.py (craft) docs/specs/038-per-node-model-tiering/spec.md 038-03 <deliverables> (round 2)
substrate: non-interactive
---

VERDICT: pass

REASONING:
Round 2. Round-1 blocker fixed at two levels (stale keys dropped; check depends on a configured ladder) with tests that fail on the old code (resume lands exactly at 9; ladder-less resume ends oracle_plateau). Guard arithmetic and window start unchanged and correct at every boundary.

SPECIFIC ISSUES:
- [nit][impl] _outcome_details renders rung 0 of M while SKILL.md says "for an escalated outcome".
- [nit][spec] architecture.md omits the ladder driver pin.
- [nit][impl] test comment at the mid-window resume test says "later" where one regression fires earlier.
- [strength][impl] Two-level ladder-less fix; mid-window resume test pins exactly iteration 9; context-ratio reset test; single source of truth for the rung config.
