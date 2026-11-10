---
slice: 038-03 — plateau escalation ladder
pass: compliance
verdict: needs-changes
reviewer: jig:reviewer
reviewed_at: 2026-11-10T21:59:04Z
prompt_source: review.py (compliance) docs/specs/038-per-node-model-tiering/spec.md 038-03 <deliverables>
---

VERDICT: needs-changes

REASONING:
Round 1. AC1-AC9 implemented on main paths (worked example 4/7/11, guard arithmetic, fresh session per rung, judge untouched, Escalation prompt, recording, resume/clamp, goal note, heartbeat forwarding/refusal/quarantine). One real bug: a ladder-less --models resume after an escalation leaves the stale rung, which can silently disable the plateau brake. Several tests pass at HEAD by construction.

SPECIFIC ISSUES:
- [impl] Ladder-less resume keeps a stale escalation_rung; _rung_plateau returns False forever when escalation_history_start is null (High).
- [impl] Resume-without-ladder test checks summary keys only (High).
- [impl] Bad-ladder flag test and validator test pass at HEAD; heartbeat refusal tests assert rc only (Medium).
- [impl] Breadcrumb/doc says verdict_schema_mismatch covers timeouts/rate limits (Medium).
- [impl] Heartbeat breadcrumb fold disagrees with loop.py on inherit (Medium).
