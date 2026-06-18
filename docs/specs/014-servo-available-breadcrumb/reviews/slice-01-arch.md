---
slice: 014-01 - breadcrumb marker writers
pass: arch
verdict: pass
reviewer: explorer subagent Avicenna
reviewed_at: 2026-06-18T20:24:35Z
prompt_source: review.py arch-review docs/specs/014-servo-available-breadcrumb/spec.md 014-01 <deliverables>
---

VERDICT: pass

REASONING:
The breadcrumb contract is documented in an accepted ADR, reconciled into the architecture/README/refinement trail, and implemented as an advisory user-state hint rather than a new target-local authority. The writer paths refresh only after their primary operation succeeds and keep marker failures best-effort, preserving existing install/scaffold boundaries. No architecture-blocking boundary, contract, or layering issue surfaced.

SPECIFIC ISSUES:
- [nit] skills/scaffold-init/scaffold.py / scripts/scaffold_runtime.py / scripts/verify_install.py — The marker path/payload/atomic-write logic is duplicated across three writers; acceptable for self-contained install surfaces, but a future schema/path bump must update all three copies together.
- [strength] docs/decisions/adr-0013-servo-available-breadcrumb.md — The ADR explicitly keeps the marker best-effort and advisory, avoiding install/scaffold failure coupling.
- [strength] docs/architecture.md — The architecture places the breadcrumb under runtime install/scaffold surfaces while preserving .servo/ as target-local project authority.
- [strength] scripts/verify_install.py — Plugin verification writes the marker only after successful verification with a known version, avoiding false-positive availability from failed roots.

RECONCILIATION NOTES:
Record the duplicated writer helper as a non-blocking maintainability note. The slice preserves the servo/jig filesystem-only boundary and best-effort posture.
