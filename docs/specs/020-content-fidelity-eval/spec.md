---
status: DONE
dependencies: [adr-0024]
last_verified: 2026-07-03
---

# Spec 020 — content-fidelity-eval

> Generalize servo's frozen-eval harness so a second, non-visual eval kind can
> reuse it: extract the already-modality-agnostic freeze/hash/aggregate/ledger/
> install-splice machinery out of `design-eval` into a shared module
> (`skills/_common/fidelity_eval.py`), then ship `/servo:content-fidelity` — a
> sibling skill that turns "does this generated text match the intended rubric
> or spec?" into a frozen `score_content_fidelity` oracle component, judged by
> a pinned text model instead of a vision model. Implements
> [ADR-0024](../../decisions/adr-0024-extract-frozen-eval-harness.md).

## Why this spec

[GitHub issue #16](https://github.com/ramboz/servo/issues/16) asks whether
`design-eval`'s recipe (freeze + n-sample + lower-bound + `score_<name>`
component) should generalize beyond visual fidelity. [ADR-0009](../../decisions/adr-0009-design-fidelity-eval-recipe.md)
already anticipated this exact trigger in its Alternatives-considered
section — defer extracting the shared primitives "until a second eval kind
demands them" — and [ADR-0024](../../decisions/adr-0024-extract-frozen-eval-harness.md)
records that the trigger has now fired.

This spec is the implementation. It does two things, in order: extract the
harness with **no behavior change to design-eval** (slice 020-01), then build
the second consumer on top of it (slice 020-02). Extraction lands first and
alone so design-eval's existing test suite is the regression backstop for the
refactor before any new surface is added.

## Ownership (unchanged principle, now shared)

- **servo owns the mechanism** — for both eval kinds: freeze validation,
  hashing, n-sample lower-bound aggregation, the ledger, and the oracle.sh
  install/uninstall/manifest splice (`skills/_common/fidelity_eval.py`), plus
  each kind's own capture + judge runtime.
- **the project owns the policy** — the dataset (screens or cases), the
  rubric, the pinned judge model, `n`/`k`/`δ`/threshold, and the frozen
  `config.json` + reference artifacts. Honesty is unchanged: servo scores, it
  does not prove; a missing key / unreachable judge / unparseable reply is
  `env_error`, never a silent `0.0`.

## Acceptance criteria

1. **Extraction is behavior-preserving.** `design-eval`'s public contract
   (`config.json` shape, the `score_design_fidelity` component name, CLI
   subcommands, `oracle.sh` fragment) is byte-for-byte unchanged after the
   extraction; its existing test suite passes with the same assertions,
   now exercising the shared module through a thin wrapper.
2. **Shared module carries the modality-agnostic contract.** `validate_freeze`,
   `definition_hash`, `artifact_hashes`, `aggregate_lower_bound`, the ledger
   writer, `_extract_json`, and the HTTP-retry wrapper live in
   `skills/_common/fidelity_eval.py`, generalized to take field lists / a
   case-array key as parameters rather than hardcoding design-eval's
   `screens`/`viewport` shape. The oracle.sh SEED-splice + `COMPONENTS` +
   `.servo/install.json` registration helpers move too, parameterized by
   component name and fragment body instead of hardcoded to
   `score_design_fidelity`.
3. **`content-fidelity` drops into the existing oracle contract.**
   `score_content_fidelity` is an ordinary `score_<name>` component echoing
   `[0,1]` / rc 2 via the shared module; `oracle.sh`, `gate.py`, and the 0/1/2
   contract are unchanged (ADR-0005 clause 1).
4. **Frozen + hashed definition (content-fidelity).** Rubric, reference
   dataset (the target-vs-rubric cases), judge model + decoding, `n`, `k`,
   `δ`, threshold, and the case set are pinned and sha256-hashed via the
   shared `validate_freeze`; a change refuses as **stale** (rc 2) until
   re-frozen (ADR-0005 clause 2).
5. **Confidence lower-bound scoring (content-fidelity).** Per case, judge
   `n`× and contribute `mean − k·stderr` via the shared
   `aggregate_lower_bound`; composite is the weighted average across cases
   (ADR-0005 clause 3).
6. **Fail-closed honesty (content-fidelity).** Missing judge credentials,
   unreachable judge, artifact-gathering failure, or an unparseable reply →
   `env_error` (rc 2), never a silent `0.0`. Each run appends sampled +
   aggregated scores + hashes to `ledger.jsonl` via the shared ledger writer
   (ADR-0005 clause 5, clause 7).
7. **Guided skill surface.** `/servo:content-fidelity` ships a `SKILL.md` flow
   (init → author `config.json` → freeze → install → run) plus an authoring
   CLI mirroring `design_eval.py`'s init/freeze/install/uninstall shape, and a
   `templates/config.example.json` skeleton scoped to text (rubric/spec
   reference + text-model judge, no viewport/screenshot fields).

## Vertical slices

- **020-01 — extract the shared frozen-eval harness:** move the
  modality-agnostic primitives (AC2) out of `skills/design-eval/score.py` and
  `design_eval.py` into `skills/_common/fidelity_eval.py`; `design-eval`
  imports from it. No new skill surface; this slice is pure refactor,
  verified by design-eval's unmodified test suite (AC1).
- **020-02 — content-fidelity skill:** new `skills/content-fidelity/` (SKILL.md
  + authoring CLI + text-judge runtime + capture-the-artifact-under-test step)
  built on the shared module from 020-01 (AC3-7).

## Non-goals

- Changing `design-eval`'s public contract, config schema, or component name
  (AC1 pins this).
- A general multi-kind eval-*authoring* UI/wizard beyond the two skills'
  existing guided-CLI shape — this spec generalizes the *runtime harness*,
  not eval authoring UX (that's spec 008's separate, still-parked path).
- Routing content fidelity through spec-oracle's `residual_judgment` (spec
  008's bridge) — content fidelity is a fixed rubric-vs-generated-text
  comparison, not a spec-text AC to classify, same reasoning ADR-0009 applied
  to the visual case.
- Picking the one true "artifact under test" gathering mechanism for every
  future text-generation project — 020-02 ships one reasonable default
  (read a file the target's generator already wrote, or the project supplies
  a `generate.<ext>` script) and documents it as project-configurable, not a
  hardcoded framework integration.
- Proving a score is correct or human-reviewed (out of scope per ADR-0005,
  unchanged from design-eval).
