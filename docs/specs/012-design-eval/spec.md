---
status: DRAFT
dependencies: [002, 003]
last_verified: 2026-06-12
---

# Spec 012 — design-eval (UI design-fidelity eval recipe)

> Ship `/servo:design-eval`: a guided skill that turns "does the built UI match
> the design mockup?" into a **frozen eval component** — the non-deterministic
> sibling of servo's deterministic component templates. It captures app-vs-
> reference screenshots, judges fidelity with a pinned vision model (n-sampled,
> confidence-lower-bound), freezes the definition, and installs a
> `score_design_fidelity` component into the project's `oracle.sh` so the
> agent-loop can iterate a UI toward its mockup and the quality-gate can attest
> the result.

## Why this spec

[ADR-0005](../../decisions/adr-0005-eval-oracle-component.md) settled the
*contract* for a non-deterministic eval (frozen `score_<name>`, hashed
definition, lower-bound scoring, plateau noise floor, `env_error` never a silent
zero). [Spec 008 (eval-authoring)](../008-eval-authoring/spec.md) records the
*spec-oracle bridge* path (residual_judgment AC → eval) — still parked, because
it needs a spec-text AC to classify.

**Design fidelity is the first real non-deterministic AC — and it doesn't fit
the spec-text path.** "Match the mockup" is a *visual* comparison against a
reference image, not a sentence to classify into a check family. It also recurs
for *every* design-mockup→UI project (only the screens, rubric, and references
vary). That makes it the natural first consumer of ADR-0005's contract, via a
**dedicated recipe** rather than the spec-oracle bridge — recorded in
[ADR-0009](../../decisions/adr-0009-design-fidelity-eval-recipe.md). food-log is
the first concrete consumer (its slice 002-01 must be built to `design_v1.0`).

See [spike-findings.md](spike-findings.md) for the throwaway-spike evidence that
de-risked the five hard problems (device chrome, deterministic state, app↔ref
state match, composed mockups, rubric scope).

## Ownership (the point of the dedicated skill)

- **servo owns the mechanism** — capture (`capture.mjs`), judge + aggregation +
  freeze validation (`score.py`), install/freeze authoring (`design_eval.py`),
  and the runtime contract. Built once, reused by every UI project.
- **the project owns the policy** — the screen dataset, the rubric, the pinned
  judge model, `n`/`k`/`δ`/threshold, and the frozen `config.json` + reference
  PNGs. (Honesty: servo scores, it does not prove; key/judge/browser failure is
  `env_error`, never a `0.0`.)

## Acceptance criteria

1. **Drops into the existing contract.** `score_design_fidelity` is an ordinary
   `score_<name>` component echoing `[0,1]` / rc 2; `oracle.sh`, `gate.py`, and
   the 0/1/2 contract are unchanged.
2. **Frozen + hashed definition.** Rubric, reference dataset, judge model +
   decoding, `n`, `k`, `δ`, threshold, and the screen set are pinned and
   sha256-hashed; a change refuses as **stale** (rc 2) until re-frozen.
3. **Confidence lower-bound scoring.** Per screen, judge `n`× and contribute
   `mean − k·stderr`, so a wobbling judge only scores high when confident across
   samples (ADR-0005 clause 3); composite is the weighted average across screens.
4. **Fail-closed honesty.** Missing `ANTHROPIC_API_KEY`, unreachable judge,
   browser/capture failure, or an unparseable reply → `env_error` (rc 2), never
   a silent `0.0`. Each run appends sampled + aggregated scores + hashes to
   `ledger.jsonl`.
5. **Reproducible capture.** References crop device chrome; per-screen `setup`
   seeds deterministic state (the app is now-dependent) so the same inputs
   produce the same screenshot.
6. **Pairs with the plateau noise floor.** Documented to run under
   `--plateau-noise-floor δ` (a companion [003](../003-agent-loop/) `loop.py`
   change per ADR-0005 clause 4, held for a separate PR).

## Slices (SPIDR)

| Slice | Scope | Status |
|---|---|---|
| 012-01 | **Freeze + aggregation core** — `score.py`: `validate_freeze` / `definition_hash` / `aggregate_lower_bound`; stale + env_error honesty | BUILT + tested (16 tests) |
| 012-02 | **Authoring CLI + install** — `design_eval.py` init/freeze/install/uninstall; oracle.sh SEED splice + COMPONENTS + manifest (mirrors `oracle_overlay`) | BUILT + tested |
| 012-03 | **Capture + judge runtime** — `capture.mjs` (Playwright references w/ chrome-crop + seeded app shots); `score.py` vision judge (Anthropic Messages API, pinned model) | BUILT (runtime; exercised live in the loop, not unit-tested) |
| 012-04 | **Guided skill surface** — `SKILL.md` flow + `templates/config.example.json` | BUILT |
| 012-05 | **First consumer wiring** — food-log: author `config.json` + per-screen setups, capture refs, freeze, install, run | PENDING (project work) |

> **Honest status note.** The mechanism (01–04) is implemented and unit-tested
> under Python 3.12, but this spec has not been through the full jig
> review-evidence ceremony this session (dogfooding is partial — the formal
> review/reconcile pass is reserved for the food-log slice in the loop phase).
> ADR-0005 advances toward Accepted now that it has a built consumer.

## Non-goals

- Routing design fidelity through spec-oracle's `residual_judgment` (that is
  spec 008's path; design fidelity is image-vs-image, not spec-text).
- A general multi-kind eval-authoring framework. The reusable freeze/aggregate
  primitives currently live in `design-eval/score.py`; extracting them to a
  shared module is an ADR-0003 rule-of-three step for the **second** eval kind.
- Proving a score is correct or human-reviewed (out of scope per ADR-0005).
