---
adr: 0047
pass: frame-critique
verdict: needs-changes
reviewer: jig:reviewer
reviewed_at: 2026-11-10T19:38:19Z
prompt_source: review.py frame-critique docs/decisions/adr-0047-per-node-model-tiering-and-escalation-ladder.md
---

VERDICT: needs-changes

REASONING:
Round 1. Load-bearing assumption: a stuck laddered run still terminates `oracle_plateau`, so ADR-0030 quarantine keeps working. Rungs share max_iterations/cost_ceiling and sizing is unenforced, so under defaults (5 iters, window 3) an escalated run ends max_iterations_reached -> `tried` (sticky, no quarantine record).

SPECIFIC ISSUES:
- [spec] Ladder cut short by a brake silently bypasses quarantine; kill-criterion denominator ("laddered plateaus") is biased. Fix: guard escalation on remaining budget and/or quarantine escalated-not-passed runs; denominator = runs that escalated.
- [spec] Vendor evidence (A1) is about fresh re-runs; effort rungs resumed the stuck session. Record or force fresh sessions per rung.
- [spec] "clamp-never-loosen" misquotes ADR-0016 (code implements clamp-never-disable).
