---
slice: 038-03 — plateau escalation ladder
pass: arch
verdict: pass
reviewer: jig:reviewer
reviewed_at: 2026-11-10T22:28:13Z
prompt_source: review.py (arch) docs/specs/038-per-node-model-tiering/spec.md 038-03 <deliverables> (round 2)
substrate: non-interactive
---

VERDICT: pass

REASONING:
Round 2. Both blockers fixed in the right place and pinned by tests: escalation resets every session-keyed field (session id, cost snapshot, context ratio) in both copies; _rung_plateau requires a ladder and ladder-less resume cleans state. Duplicated fold removed (rung config travels in the ADR-0039 terminal_breadcrumb); duplicate baseline key dropped.

SPECIFIC ISSUES:
- [nit][spec] Heartbeat pins --driver loop for ladders (overrides auto routing / plan driver) — record it; owner question: should loop.py auto prefer the loop driver when a ladder is configured (node-owned, trigger-agnostic, retires _models_have_ladder)?
- [nit][impl] heartbeat _run_loop docstring stale.
- [strength][impl] One-place session reset on escalation; two-level brake fix; rung failure detail via the existing breadcrumb channel.

RECONCILIATION NOTES:
- Ladder-less resume also pops escalation_events (measurement record) — keep events, drop only rung/window keys.
- _rung_failure_breadcrumb names the runner config even on a judge failure.
