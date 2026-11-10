---
slice: 038-03 — plateau escalation ladder
pass: craft
verdict: needs-changes
reviewer: jig:reviewer
reviewed_at: 2026-11-10T21:59:05Z
prompt_source: review.py (craft) docs/specs/038-per-node-model-tiering/spec.md 038-03 <deliverables>
substrate: non-interactive
---

VERDICT: needs-changes

REASONING:
Round 1. Ladder mechanics sound for fresh runs (guard and window arithmetic verified at every boundary; escalation is the last statement so no brake is skipped; no-ladder path unchanged). Blocker: _rung_plateau reads persisted rung state when the resumed block has no ladder, disabling the plateau brake in a reachable case.

SPECIFIC ISSUES:
- [blocker][impl] Ladder-less resume disables the plateau brake.
- [nit][spec] Stale context-fill ratio after escalation can halt context_full before the rung runs.
- [nit][spec] Heartbeat never passes --driver; auto routes to the goal driver on capable hosts, making the ladder inert silently.
- [nit][impl] Heartbeat inherit fold mismatch; _outcome_details omits escalation_rung; non-isolating tests (failure-line assertion, escalation[0] message, mid-window resume); misnamed heartbeat test; unused _best_at.
- [strength][impl] Boundary-pinned guard tests; escalation placed after every brake; negative no-ladder shape guard.
