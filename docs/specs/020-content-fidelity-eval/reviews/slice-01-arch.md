---
slice: 020-01 — extract-shared-harness
pass: arch
verdict: pass
reviewer: jig:reviewer
reviewed_at: 2026-07-04T03:22:28Z
prompt_source: review.py arch-review docs/specs/020-content-fidelity-eval/spec.md 020-01 ...
---

VERDICT: pass (round 2, after a blocker fix)

Round 1 blocker: definition_hash hardcoded "viewport" directly in the shared,
supposedly modality-agnostic module -- contradicted ADR-0024/slice 020-01's
explicit generalization requirement. Fixed via a generic extra_fields
parameter; verified the shared module now contains zero design-eval-specific
field names (only a docstring example mentions "viewport"). Double-load fix
(design_eval.py's `_fe = _score._fe`) verified sound -- exec_module is
synchronous so no partial-init race, and it's a documented same-skill
internal convention, not fragile coupling.

Non-blocking nits: docs/architecture.md and the slice's deviation log don't
yet reflect these fixes -- expected pre-reconciliation, flagged for that pass.
