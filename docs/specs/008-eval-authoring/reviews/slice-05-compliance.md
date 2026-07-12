---
slice: 008-05 — goal-to-criteria
pass: compliance
verdict: pass
reviewer: jig:reviewer
reviewed_at: 2026-07-12T17:32:21Z
prompt_source: review.py implementation ... 008-05 (re-review)
---

VERDICT: pass

Compliance re-review after fixes. All seven ACs met, governed by ADR-0027. AC1:
`from-goal` expands into tagged+rationaled ACs (fresh claude -p, mock in tests).
AC2: a separate fresh claude -p reviewer (goal + AC list only, no CoT leak),
jig-independent-review-if-present else the shipped eval-frame-review.md — servo not
hard-depending on jig. AC3 (strengthened): every AC starts approval_status=proposed
(never auto-approved); from-goal now REFUSES to clobber a curated criteria.md/json
without --force; require_all_approved is wired via the new `criteria-check`
subcommand. AC4: emitted artifact round-trips through oracle_plan.extract_acs
unchanged. AC5: criteria-split surfaces evaluable-vs-residual (not a full verdict,
ADR-0018). AC6: opt-in; never touches gate.py/oracle.sh. AC7 checklist covered with
a real PATH-injected mock-claude (0 python mocks).

Nit → reconciliation: AC4's "tagged list" renders as a plain `## Acceptance criteria`
list + a companion tag table (deliberate — inline tags would break the extract_acs
round-trip); tag info still present.
