---
status: READY_FOR_IMPLEMENTATION
dependencies: [008-02, adr-0005, adr-0024]
last_verified:
---

## Slice 008-03 — reference-set

**Goal:** Scaffold and help grow the statistical **reference set** — the dataset
of inputs (and expected behaviours/labels where the eval is ground-truthed) that
008-02's rubric scores over — seeded from the spec's own examples and the slice's
edge cases, with minimum-viable-size guidance. A project-owned artifact, not plugin
state; the author owns the truth, the skill never fabricates ground truth. This is
~80% of the real work and the easiest thing to get wrong.

### Acceptance criteria

- **AC1** Scaffold a project-owned dataset file (local file = source of truth, in
  the project's git), seeded from the spec's examples + the slice's listed edge cases.
- **AC2** Per-case shape:
  `{id, category ∈ {happy_path | edge_case | skip_case}, scenario, input, expected_output{description, constraints[]?}}`
  (borrowed taxonomy), with a small string-constraint DSL (`==`, `>=`, `<=`) for
  cheap deterministic sub-checks alongside the judged score.
- **AC3** Minimum-viable-size guidance is surfaced with a stated default floor
  (provisional **≥12 cases**, tuned against the first real eval), but
  the tool **never invents cases or labels** to reach it — an under-sized dataset
  warns, it does not autofill (spec 008 non-goal: no fabricated ground truth).
- **AC4** The dataset is the hashed artifact ADR-0005 freezes, via the shared
  `validate_freeze`/`definition_hash` in `fidelity_eval.py` (ADR-0024) — a change to
  the dataset refuses as stale.
- **AC5** Both ground-truthed cases (labels/constraints) and rubric-only judged
  cases are supported in one dataset.
- **AC6** Tests cover: scaffolding from spec examples; an under-floor dataset warning
  without autofill; the dataset hashing/freezing through the shared harness; a mixed
  labeled + rubric-only dataset scoring end-to-end.

> The dataset is the hard part; the skill assists collection and enforces honesty
> (no invented truth), but the author supplies the cases.
