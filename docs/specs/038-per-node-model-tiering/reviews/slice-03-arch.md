---
slice: 038-03 — plateau escalation ladder
pass: arch
verdict: needs-changes
reviewer: jig:reviewer
reviewed_at: 2026-11-10T21:59:05Z
prompt_source: review.py (arch) docs/specs/038-per-node-model-tiering/spec.md 038-03 <deliverables>
substrate: non-interactive
---

VERDICT: needs-changes

REASONING:
Round 1. Placement matches ADR-0047 (ladder in loop.py, trigger-agnostic; heartbeat only forwards and files; rung 0 byte-identical; rungs inside existing caps; judge and oracle untouched; same ADR-0030 record). Two compositions with existing brakes are wrong.

SPECIFIC ISSUES:
- [blocker][spec] Escalation leaves last_context_fill_ratio of the discarded session -> immediate context_full instead of a fresh rung.
- [blocker][impl] Ladder-less resume leaves a stale rung that disables the plateau brake (contradicts D4 / ADR-0016 clamp-never-disable).
- [nit][impl] Heartbeat re-implements the rung fold; prefer loop.py putting the rung config into terminal_breadcrumb.
- [nit][spec] ADR-0030 has no pointer to the widened trigger (owner question).
- [strength][impl] Rung 0 is literally the old check; models_invalid reuses the (None, reason) refusal shape; additive keys only with a ladder.

RECONCILIATION NOTES:
- escalation_baseline_composite duplicates escalation_events[-1]; ADR-0010 amendment should say "overrides" not "raises"; heartbeat drops loop stderr so an unsized ladder is silently inert; a never-editing runner still climbs the ladder (future guard).
