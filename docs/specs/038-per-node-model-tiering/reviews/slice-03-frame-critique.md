---
slice: 038-03 — plateau escalation ladder
pass: frame-critique
verdict: needs-changes
reviewer: jig:reviewer
reviewed_at: 2026-11-10T19:38:34Z
prompt_source: review.py frame-critique docs/specs/038-per-node-model-tiering/spec.md 038-03
---

VERDICT: needs-changes

REASONING:
Round 1. Rungs sharing unchanged budgets do not run to exhaustion: under heartbeat defaults (5 iters, window 3) oracle_plateau becomes unreachable with any ladder, stuck findings end max_iterations_reached/cost_ceiling_reached -> `tried`, silently disabling ADR-0030 quarantine.

SPECIFIC ISSUES:
- [spec] Guard escalation on remaining iterations and/or quarantine escalated-but-not-passed runs.
- [spec] Rung windows count iterations, not runner attempts (judge iterations re-score the same tree); the top rung can be declared plateaued after one runner attempt. Align the rung window to start on a runner iteration.
