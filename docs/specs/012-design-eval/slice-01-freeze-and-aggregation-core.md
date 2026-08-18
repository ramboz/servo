---
status: IN_PROGRESS
dependencies: [adr-0005]
last_verified: 2026-08-18
---

## Slice 012-01 — freeze-and-aggregation-core

**Goal:** Implement the honesty core of `score_design_fidelity` in
`skills/design-eval/score.py`: the frozen-definition hash, the freeze
validator, the confidence-lower-bound aggregator, and the `env_error`-never-a-
silent-zero rule. This is the slice that makes [ADR-0005](../../decisions/adr-0005-eval-oracle-component.md)'s
contract real for the first non-deterministic eval kind.

**DoR:**
- ✅ **ADR-0005 (Accepted) fixes the contract** — frozen `score_<name>`,
  hashed definition, lower-bound scoring, plateau noise floor, and
  `env_error` never collapsing to `0.0`.
- ✅ **ADR-0009 (Accepted) chose the dedicated-recipe path** over routing
  design fidelity through spec-oracle's `residual_judgment` bridge.
- ✅ **Spike evidence exists** — see [spike-findings.md](spike-findings.md)
  for the five de-risked problems (device chrome, deterministic state,
  app↔ref state match, composed mockups, rubric scope).

**Acceptance criteria** (spec ACs 2, 3, 4):
1. `definition_hash(config)` pins rubric, reference dataset, judge model +
   decoding, `n`, `k`, `δ`, threshold, and the screen set into one sha256.
2. `artifact_hashes(config, base_dir)` hashes the on-disk reference PNGs so a
   swapped reference is detectable independently of the config text.
3. `validate_freeze(config, base_dir)` refuses **stale** (rc 2) when either
   hash set no longer matches the frozen record.
4. `aggregate_lower_bound(samples, k)` returns `mean − k·stderr` per screen,
   so a wobbling judge scores high only when confident across samples.
5. Missing `ANTHROPIC_API_KEY`, unreachable judge, capture failure, or an
   unparseable reply raise `EnvError` → rc 2, never a `0.0`.

**DoD:**
- [x] `definition_hash` / `artifact_hashes` / `validate_freeze` /
      `aggregate_lower_bound` implemented in `score.py`.
- [x] 15 unit tests green — `AggregationTests` (4), `FreezeTests` (8),
      `ScoreHonestyTests` (3).
- [x] Shipped in a tagged release (present from the `design-eval` skill's
      first release through 0.8.0).
- [ ] Compliance + craft review verdicts recorded under `reviews/`.
- [ ] Reconciliation verdict + deviation log + reconciliation sweep recorded.

### Retro-reconciliation note (2026-08-18)

This slice was **implemented and shipped before this spec was ever run through
jig's file-per-slice lifecycle** — spec 012 predates the per-slice DONE-gate
machinery and carried its slice plan as an inline `## Slices (SPIDR)` table in
`spec.md`. This file retro-records the slice so `status-board` can see it. The
code is real and green; the **review evidence genuinely does not exist**, which
is why this sits at `IN_PROGRESS` rather than `DONE`.

**Post-hoc scope change (not a deviation by this slice):** slice
[020-01](../020-content-fidelity-eval/slice-01-extract-shared-harness.md)
later extracted these primitives into `skills/_common/fidelity_eval.py` under
[ADR-0024](../../decisions/adr-0024-extract-frozen-eval-harness.md).
`score.py` now reaches them through `_load_fidelity_eval()`; the public
contract and this slice's tests were deliberately left unchanged, and served
as 020-01's regression backstop.
