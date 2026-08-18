---
status: DONE
dependencies: [002, 003]
last_verified: 2026-08-18
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
>
> A host `evaluate` phase hint (see
> [Host-native phase hints](../../architecture.md#host-native-phase-hints-spec-013),
> [ADR-0011](../../decisions/adr-0011-host-native-phase-hints.md)) may help a
> human shape a rubric or screen set before this runs, but the fidelity score
> always comes from the frozen `score_design_fidelity` component — never a
> host transcript.

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

Recorded file-per-slice (see the note below for why this arrived late):

- **[012-01 — freeze-and-aggregation-core](slice-01-freeze-and-aggregation-core.md)**
  — `score.py`: `definition_hash` / `artifact_hashes` / `validate_freeze` /
  `aggregate_lower_bound`; stale + `env_error` honesty. 20 tests.
- **[012-02 — authoring-cli-and-install](slice-02-authoring-cli-and-install.md)**
  — `design_eval.py` init/capture/freeze/install/uninstall; `oracle.sh` SEED
  splice + `COMPONENTS` + manifest (mirrors `oracle_overlay`). 19 tests.
- **[012-03 — capture-and-judge-runtime](slice-03-capture-and-judge-runtime.md)**
  — `capture.mjs` + `capture_lib.mjs` (chrome-cropped references, seeded app
  shots) + the pinned vision judge on both `api` and `cli` transports. 24 tests.
- **[012-04 — guided-skill-surface](slice-04-guided-skill-surface.md)**
  — `SKILL.md` flow + `templates/config.example.json`. 25 surface tests.
- **[012-05 — first-consumer-wiring](slice-05-first-consumer-wiring.md)**
  — **DEFERRED**; the consuming project (food-log) is a separate repository.

> **Status note (rewritten 2026-08-18, after the review ceremony).** The
> mechanism (012-01..04) shipped in **0.3.0** and every release through
> **0.8.0** — it is also the code slice
> [020-01](../020-content-fidelity-eval/slice-01-extract-shared-harness.md)
> extracted the shared frozen-eval harness *out of*. But spec 012 predated the
> per-slice DONE-gate machinery and, until this reconciliation, carried its
> slice plan as an inline table `status-board` could not see, so the board
> indexed a shipped skill as an unstarted draft.
>
> The ceremony has now been run against the shipped code: two independent
> compliance reviewers and one craft reviewer, all of which returned
> **`needs-changes`** in round 1. They found ACs that described behaviour the
> code did not have (`definition_hash` was documented as hashing the rubric;
> `capture_app` was credited with the `setup`-seeding that lives in
> `capture.mjs`; bounded retry was claimed for a `cli` transport that has none),
> untested shipped paths (the whole `cli` transport, `capture_app`'s failure
> branches, `capture_refs`), and a doc that under-listed the vendored runtime
> badly enough to send a reader to a broken target. All were fixed, and round 2
> passed every slice. design-eval went from **23 to 78 tests**.
>
> The honest residual is narrow and disclosed rather than closed by silence:
> `capture.mjs`'s **browser body** is still hand-verified (it cannot run without
> a browser servo does not ship), and two robustness follow-ups — the silently
> optional per-screen `setup`, and the `1600×1600` reference-render constant —
> are recorded in `docs/refinement-todo.md` with resolution triggers.

## Non-goals

- Routing design fidelity through spec-oracle's `residual_judgment` (that is
  spec 008's path; design fidelity is image-vs-image, not spec-text).
- A general multi-kind eval-authoring framework. The reusable freeze/aggregate
  primitives currently live in `design-eval/score.py`; extracting them to a
  shared module is an ADR-0003 rule-of-three step for the **second** eval kind.
- Proving a score is correct or human-reviewed (out of scope per ADR-0005).
