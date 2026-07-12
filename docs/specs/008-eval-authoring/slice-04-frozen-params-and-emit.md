---
status: READY_FOR_REVIEW
dependencies: [008-01, 008-02, 008-03, adr-0005, adr-0024]
last_verified:
---

## Slice 008-04 — frozen-params-and-emit

**Goal:** Set the frozen `n` / `δ` / threshold / judge model+params with sane
defaults and plain-language trade-off guidance
([ADR-0005](../../decisions/adr-0005-eval-oracle-component.md): too-wide `δ` never
passes, too-narrow flaps), then emit the eval definition in the exact shape
`/servo:spec-oracle`'s eval-family extension compiles into a frozen `score_<name>`.
Closes the authoring path: this skill authors, spec-006 compiles+freezes, `gate.py`
runs.

### Acceptance criteria

- **AC1** A guided step sets `n`, `δ`, threshold, and judge model+params, each with
  a sane provisional default — inherited from the shipped fidelity presets
  (design-eval / content-fidelity `config.json`) as the starting point, tuned per
  eval — and a one-line plain-language trade-off note (the ADR-0005 knobs).
- **AC2** Emits the eval definition in the exact shape spec-006's eval-family compile
  step consumes → a frozen `score_<name>` per ADR-0005.
- **AC3** The emitted component is built on `skills/_common/fidelity_eval.py`
  (ADR-0024) for freeze/hash/n-sample/lower-bound/ledger/install-splice — **no
  parallel harness**; only the authoring-specific wrapper is new.
- **AC4** Authoring stops at an **approved, compilable definition**. This slice does
  not freeze or run — spec-006 compiles + freezes (ADR-0022 against parsed ACs,
  ADR-0023 co-located artifacts); `gate.py` runs.
- **AC5** A change to the rubric / dataset / model / `n` / `δ` / threshold refuses as
  stale via the shared `validate_freeze` (inherited, not re-implemented).
- **AC6** Tests cover: defaults applied when the author accepts them; the emitted
  definition compiling through spec-006 into a `score_<name>` that `gate.py` runs
  under the ADR-0002 exit contract; a param change triggering `spec_oracle_stale`.

> This is the seam to the existing machinery: everything downstream of the emitted
> definition is the ADR-0005 contract on the ADR-0024 harness, unchanged.
