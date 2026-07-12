---
status: DONE
dependencies: [008-02, adr-0005, adr-0024]
last_verified: 2026-07-12
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

### Deviation log (after reconciliation)

Original ACs preserved above.

- **`dataset` subcommand + per-case shape.** `{id, category ∈ {happy_path |
  edge_case | skip_case}, scenario, input, expected_output?: {description,
  constraints?[]}, baseline?}`, stored in `config.json`'s `cases` array (the same
  frozen artifact `rubric` wrote). `expected_output`'s *presence* distinguishes a
  ground-truthed case from a rubric-only judged case (AC5). `baseline` is the
  008-02 carry-forward for the comparative archetype (shape-only here).
- **Constraint DSL.** `<field> <op> <value>` with `op ∈ {==, >=, <=}`. `==`
  compares as a **string** (no float coercion — so `version == 3.10` is preserved);
  `>=`/`<=` require a **numeric literal**, validated at `parse_constraint` /
  `validate_case` time (an un-evaluable inequality fails at authoring, not at score
  time). `==` is deliberately stringly-typed — see the 008-04 carry-forward.
- **Min-size floor.** Provisional **≥12** cases; under-floor **warns** (non-fatal,
  exit 0) and **never autofills** — scaffolding copies spec `## Examples` /
  `## Edge cases` bullets verbatim (never invents scenario/input/label) or, absent
  those sections, writes one labeled `EDIT ME` placeholder per taxonomy category.
- **Non-destructive re-run.** `dataset` scaffolds only when `cases` is empty; a
  later run validates + re-reports and never overwrites human-grown cases (a frozen
  config survives a re-run untouched).
- **Composite `score()` landed here (driven by AC6), not 008-04.** AC6 requires a
  "mixed labeled + rubric-only dataset scoring end-to-end" test, which needs a
  composite scorer. `score.py::score()` now composes the dataset: n-sample
  lower-bound per non-`skip_case` case (skip excluded from the denominator),
  weighted mean, `EnvError` (never silent 0.0) on missing samples / no candidate.
  **Composition rule (design decision):** a failed hard constraint multiplies that
  case's judged lower bound by `0.0` (a rubric-only case is a no-op `1.0` gate).
  `score()` appends a per-run record to `ledger.jsonl` via the shared harness even
  for a still-`draft` config (its `definition_hash` field resolves to `null` until
  008-04 freezes), mirroring content-fidelity.
- **Freeze coverage.** `_CASE_PIN_FIELDS = (category, scenario, input,
  expected_output, baseline)` pinned BY VALUE, so any case edit trips `StaleError`
  once frozen. `_REFERENCE_FILE_FIELDS = ()` — no referenced-fixture-file support
  (deferred; extension recipe documented in `score.py`).

**Carry-forward to 008-04 (flagged by both review passes):**

- **Guard the per-case `weight`.** `score()` reads `float(case.get("weight", 1.0))`
  but `weight` is not in AC2's shape and is unvalidated — a hand-edited non-numeric
  weight raises a bare `ValueError`, not the clean `EnvError` the module guarantees.
  008-04 (which wires the live scoring path) must guard the `weight` parse. (The
  `total_w <= 0` path *is* already guarded with a clean `EnvError` — it is only
  untested, listed under the coverage follow-ups below.) Today `score()` runs only
  on authoring-path-validated configs + fake tests.
- **`==` is stringly-typed.** Once 008-04 extracts numeric `actual_values`, a JSON
  `3` vs `3.0` compared with `==` stringifies divergently. Documented as intentional;
  008-04's actual-value extraction should make numeric-equality semantics explicit.
- **Cross-module DSL reuse.** `score.py` imports `parse_constraint`/
  `evaluate_constraint` from `eval_authoring.py` (same-skill-dir load, not the
  forbidden cross-skill import). If 008-04 copies `score.py` standalone into a
  target's `.servo/<eval>/` (the install step), it must also vendor those DSL
  functions there.
- **Composite composition rule** (failed constraint → case score 0.0) is a design
  decision the spec left open (AC2 says only "alongside the judged score"); 008-04 /
  spec-006 should inherit it deliberately.
- **Test-coverage follow-ups** (non-blocking): mixed per-case weights; the
  composite-level constraints-without-actuals `EnvError`; the `total_w <= 0` guard.

### Reconciliation sweep

- **`docs/architecture.md`** — `no-op`. Still a self-contained skill on the ADR-0024
  harness; no module-boundary/public-contract change (no `arch_review`). The
  composite `score()` is the per-skill scorer wrapper, not a harness change.
- **Load-bearing decision / ADR trigger** — `no-op`. The case taxonomy, constraint
  DSL, and constraint-gate composition rule are derivations of ADR-0005's
  dataset-is-a-hashed-artifact framing + the slice ACs, not new load-bearing choices
  with rejected alternatives warranting an ADR. Recorded as design decisions above.
- **`.claude-plugin/install-contract.json`** — `deferred`. Still no SKILL.md; suite
  + install-surface checks green; registration + the score.py-standalone-copy
  concern land at 008-04 / close-out.
- **`docs/refinement-todo.md`** — `no-op`. The carry-forwards are next-slice work
  with a concrete owner (008-04) recorded above, not open-ended debt.
- **Status board** — `deferred`. Regenerated after `DONE`.
