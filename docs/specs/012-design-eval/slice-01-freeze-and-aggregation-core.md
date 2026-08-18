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
1. `definition_hash(config)` pins the judge model + decoding, `n`, `k`, `δ`,
   threshold, `viewport`, and the screen set (`id`/`reference`/`setup`/`weight`)
   into one sha256. (It does **not** hash the rubric — see AC2.)
2. `artifact_hashes(config, base_dir)` hashes the inline rubric text **and**
   every per-screen file (reference PNGs, setup scripts), so a swapped
   reference or an edited rubric is detectable independently of the config's
   scalar fields. Together AC1+AC2 cover the whole frozen definition, and
   `validate_freeze` re-checks both sets.
3. `validate_freeze(config, base_dir)` refuses **stale** (rc 2) when either
   hash set no longer matches the frozen record.
4. `aggregate_lower_bound(samples, k)` returns `mean − k·stderr` per screen,
   so a wobbling judge scores high only when confident across samples.
5. Missing `ANTHROPIC_API_KEY`, unreachable judge, capture failure, or an
   unparseable reply raise `EnvError` → rc 2, never a `0.0`.

**DoD:**
- [x] `definition_hash` / `artifact_hashes` / `validate_freeze` /
      `aggregate_lower_bound` implemented in `score.py`.
- [x] 20 unit tests green — `AggregationTests` (4), `FreezeTests` (8),
      `ScoreHonestyTests` (3), `CaptureAppHonestyTests` (3),
      `MalformedDefinitionHonestyTests` (2).
- [x] Shipped in a tagged release — landed in **0.3.0** (CHANGELOG.md, PR #8)
      and present through 0.8.0.
- [x] Compliance + craft review verdicts recorded under `reviews/`.
- [x] Reconciliation verdict + deviation log + reconciliation sweep recorded.

### Retro-reconciliation note (2026-08-18)

This slice was **implemented and shipped before this spec was ever run through
jig's file-per-slice lifecycle** — spec 012 predates the per-slice DONE-gate
machinery and carried its slice plan as an inline `## Slices (SPIDR)` table in
`spec.md`. This file retro-records the slice so `status-board` can see it.

The review ceremony has since been run (2026-08-18): compliance returned
`needs-changes` on AC1's wording — `definition_hash` was documented as hashing
the rubric, which it does not — and flagged `capture_app`'s three `EnvError`
branches as implemented-but-untested. Both are fixed above: the ACs now
describe the code, and `CaptureAppHonestyTests` covers the capture failure
paths. Verdicts are recorded under `reviews/`.

**Post-hoc scope change (not a deviation by this slice):** slice
[020-01](../020-content-fidelity-eval/slice-01-extract-shared-harness.md)
later extracted these primitives into `skills/_common/fidelity_eval.py` under
[ADR-0024](../../decisions/adr-0024-extract-frozen-eval-harness.md).
`score.py` now reaches them through `_load_fidelity_eval()`; the public
contract and this slice's tests were deliberately left unchanged, and served
as 020-01's regression backstop.

### Deviation log

- **Retro-lifecycle, not a build deviation.** The code shipped (0.3.0) before
  the review ceremony existed; this slice was reconstructed from the shipped
  implementation and reviewed in place on 2026-08-18. No code behavior changed
  in 012-01 during reconciliation — only the AC wording (AC1/AC2 rubric-hashing
  attribution) was corrected and `CaptureAppHonestyTests` +
  `MalformedDefinitionHonestyTests` were added.
- **`capture_app` failure path & malformed-definition path** were untested at
  review time (compliance finding); both are now covered. The `main()` handler
  gained an `(OSError, ValueError, KeyError, TypeError)` catch so a malformed
  config surfaces as `design-eval: env_error — …` rather than a traceback.

### Reconciliation sweep

| Artifact | Disposition |
|---|---|
| `skills/_common/fidelity_eval.py` (hash/aggregate/validate) | Verified against AC1–4; primitives extracted here by 020-01 (ADR-0024), contract unchanged. |
| `skills/design-eval/score.py` (thin wrappers + `main()`) | Verified; `main()` traceback-honesty gap fixed. |
| `test_design_eval.py` (Aggregation/Freeze/ScoreHonesty/CaptureAppHonesty/MalformedDefinition) | 20 tests green; golden sha256 pin backs 020-01. |
| Reviews (`reviews/slice-01-{compliance,craft}.md`) | compliance re-pass after AC reword; craft pass (shared with slices 02–04). |
