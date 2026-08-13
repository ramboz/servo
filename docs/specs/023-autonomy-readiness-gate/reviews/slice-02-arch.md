---
slice: 023-02 — loop.py readiness preflight (the two unattended surfaces)
pass: arch
verdict: pass
reviewer: arch-review
reviewed_at: 2026-08-12T19:28:09Z
prompt_source: review.py arch-review docs/specs/023-autonomy-readiness-gate/spec.md 023-02 --richer-skill arch-review
substrate: non-interactive
---

VERDICT: pass

REASONING:
The slice wires the readiness gate at the correct architectural seam: `loop.py` consumes
023-01's `check` verb by subprocess (`sys.executable readiness.py check …`) rather than
importing the sibling or re-deriving `_goal_id`'s sha256 — honoring the arch note in
`readiness.py:_goal_id` and the "no servo→sibling Python import" boundary (subprocess +
filesystem only). The heartbeat exemption is enforced by construction at the loop.py layer
(neither flag → no gated surface → no-op) and asserted behaviorally per ADR-0018, not by
absence-in-`heartbeat.py`. Fail-closed posture (rc1→unapproved; rc≠0/spawn-fail/timeout→
check-unavailable, both rc2) matches ADR-0029. Lean — one subprocess, two predicates, one
refusal helper reusing `_refuse_plan`'s shape; no premature abstraction.

STRENGTHS:
- `_readiness_check_rc` subprocesses `check` instead of re-deriving the hash; FileNotFound/
  Timeout fold to rc=2 (fail-closed) — single source of truth for the artifact path.
- Gate placed after flag-shape validation but before emit handler / detached-child / plan /
  routing — refuses on premise before any host-probe/routing work; detached child (routed via
  `--_detached-run-id`, never `--background`) is exempt, avoiding a double-gate.
- Distinct `readiness_unapproved` vs `readiness_check_unavailable` terminal reasons give a
  forensic reader "human hasn't approved" vs "the check itself broke" — good observability.

SPECIFIC ISSUES:
- [nit][impl] loop.py:1138-1147 vs 1125 — `_READINESS_GATED_SURFACES` (the AC4 pin) and the
  `_readiness_gated_surface` mapping are parallel literals, not one deriving from the other.
  The tuple-assertion test is a tripwire on the tuple's value, but a hypothetical third
  surface added only to argparse + the function (not the tuple) would gate correctly yet leave
  the tuple stale with the test still green — so the tuple doesn't strictly *force* coverage of
  new surfaces. Deriving the function from the tuple (or asserting every gated dest maps
  through it) would make the guarantee airtight. Low risk given only two surfaces today.
- [nit][impl] loop.py:1158-1180 — the two surfaces now hard-depend on the sibling
  autonomy-readiness skill; a partial install makes `readiness.py check` non-zero, so both
  surfaces always refuse with the generic `readiness_check_unavailable`. Correct fail-closed
  posture (bypass seam is the escape hatch), but the message doesn't name "readiness skill not
  installed" as a distinct cause — a slightly opaque breadcrumb on a fresh partial install.

RECONCILIATION NOTES:
Both nits are defense-in-depth polish, not blockers — deviation log, don't hold REVIEWED.
The AC4 tuple/function decoupling is the more substantive; worth a one-line refinement-todo
if not addressed inline. Separately (spec-authorship, out of this slice's scope): spec.md
Goal 5 / reuse-seam cite "ADR-0011" for the subprocess+filesystem boundary, but servo's
ADR-0011 is host-native-phase-hints; the boundary the code honors is "no servo→sibling Python
import," which ADR-0029's Verification section states correctly. Citation drift inherited from
023-01/spec framing, not introduced here.
