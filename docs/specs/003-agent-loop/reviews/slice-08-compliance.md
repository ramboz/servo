---
slice: 003-08 — detach-and-schedule
pass: compliance
verdict: pass
reviewer: general-purpose
reviewed_at: 2026-06-13T18:35:57Z
prompt_source: review.py implementation docs/specs/003-agent-loop/spec.md 003-08 <deliverables>
---

VERDICT: pass

REASONING:
All five ACs for slice 003-08 are genuinely met (not merely test-passing). OS-level
detachment (start_new_session), the Routine-ready emitter with a portable gate command,
the gate.py-authority contract (inherited fail-closed from 003-06), the pre-detach
dirty-tree brake, and the four-row execution matrix are each implemented and documented
in SKILL.md + docs/architecture.md. Tests are substantive (real detached child + bounded
state.json poll; emit shape + no-absolute-interpreter + self-satisfy guards). 20 new
cases pass; agent-loop suite green; ruff clean. The open question was soundly resolved
toward the OS-level background-process pattern (no headless --background on claude -p;
/background is interactive-only).

SPECIFIC ISSUES:
(none)

RECONCILIATION NOTES:
- --background routes as the goal driver and refuses on an unsupported host (vs AC1's
  literal "using /background where the host supports it") — intentional consequence of
  resolving the open question toward an OS-level detach of the goal driver; documented;
  recorded in the deviation log.
- Formally close the slice's open question in the deviation log (resolved -> OS-level
  background-process pattern, /background is interactive-only).
- Parent + detached child both run preflight/vendor: the parent surfaces refusals
  synchronously, the child re-runs with --allow-dirty against the parent-accepted tree
  (shared run dir) — intentional belt-and-suspenders; noted in the deviation log.
