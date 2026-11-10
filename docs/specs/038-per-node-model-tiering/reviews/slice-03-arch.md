---
slice: 038-03 — plateau escalation ladder
pass: arch
verdict: pass
reviewer: jig:reviewer (arch-review)
reviewed_at: 2026-11-10T22:49:15Z
prompt_source: review.py arch-review docs/specs/038-per-node-model-tiering/spec.md 038-03 <deliverables> (round 3 delta)
substrate: non-interactive
---

VERDICT: pass

REASONING:
Round 3 (delta check of the final polish). The driver choice now lives in the node per ADR-0047 D3-A: auto (omitted/explicit/plan) + non-empty ladder routes to the loop driver for every trigger; explicit --driver goal and --background keep the AC7 note. The heartbeat is forward-only again (no --driver, no shape peek, no sizing constant). The judge-turn breadcrumb and the ladder-less resume (keeps escalation_events) resolve the round-2 notes.

SPECIFIC ISSUES:
- [nit][impl] Resuming a laddered run under auto on a goal host ignores the persisted ladder (fails closed goal_resume_unsupported) — documented: resume with --driver loop; general gap tracked in refinement-todo.
- [nit][impl] architecture.md routing matrix lacked the ladder exception — footnote added.
- [strength][impl] Routing knowledge in the node; forward-only heartbeat contract with a guard test; plateau brake cannot be silenced and the per-rung record survives.

RECONCILIATION NOTES:
- Deviation: auto + ladder routing extends 003-07 routing; --explain-routing does not reflect it (documented).
