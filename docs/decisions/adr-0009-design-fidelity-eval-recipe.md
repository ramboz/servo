---
status: Accepted
date: 2026-06-12
deciders: ramboz
supersedes:
superseded-by:
---

# ADR-0009: Design-fidelity as a first-class eval recipe (`/servo:design-eval`)

## Context

[ADR-0005](adr-0005-eval-oracle-component.md) settled *under what contract* a
non-deterministic eval may enter servo's oracle: a frozen `score_<name>`
component with a hashed definition, confidence-lower-bound scoring, a plateau
noise floor, and `env_error`-never-a-silent-zero honesty. It was recorded ahead
of its first consumer ("integrate on signal").

[Spec 008 (eval-authoring)](../specs/008-eval-authoring/spec.md) is the *bridge*
ADR-0005 anticipated for one path: promote a spec's `residual_judgment` AC into
a frozen eval via `/servo:spec-oracle`. It is parked because it needs a
**spec-text** AC to classify.

A first real non-deterministic AC has now appeared, and it does **not** fit that
path: **"does the built UI faithfully match the design mockup?"** This is a
*visual* comparison against a reference image, not a sentence to classify into a
check family. Two properties make it decisive:

- **It recurs for every design-mockup→UI project.** Only the screens, the
  rubric, and the reference images vary; the mechanism (render reference →
  screenshot app at a seeded state → vision-judge fidelity n× → lower-bound →
  freeze) is identical. Hand-rolling it per project is the same "re-solder the
  wire every time" scar servo's templates exist to remove.
- **It is the non-deterministic analogue of servo's deterministic component
  templates** (`templates/components/{pytest,eslint,…}.sh.fragment`) — same
  "template + guided authoring + freeze" shape, with a screenshot+vision harness
  instead of a test runner.

food-log is the first concrete consumer (its slice 002-01 must be built to
`design_v1.0`), and a throwaway spike de-risked the five hard problems (device
chrome, deterministic state, app↔reference state match, composed mockups, rubric
scope — see [spec 012's spike-findings](../specs/012-design-eval/spike-findings.md)).

## Decision

Ship **`/servo:design-eval`** ([spec 012](../specs/012-design-eval/spec.md)) as a
**dedicated, first-class skill** implementing ADR-0005's frozen-eval contract for
the UI design-fidelity case — a sibling of `spec-oracle`/`scaffold-init`, not a
sub-mode of them.

- **servo owns the mechanism** — `capture.mjs` (Playwright references with
  chrome-crop + seeded app screenshots), `score.py` (freeze validation, vision
  judge via the Anthropic Messages API with a pinned model + decoding, n-sample
  lower-bound aggregation, ledger), and `design_eval.py` (init/freeze/install,
  reusing the oracle.sh SEED-splice convention of `oracle_overlay`).
- **the project owns the policy** — the screen dataset, rubric, judge model,
  `n`/`k`/`δ`/threshold, and the frozen `config.json` + reference PNGs.
- It rides the existing `oracle.sh` composite + `gate.py` 0/1/2 contract
  unchanged; the only loop change is ADR-0005 clause 4's plateau noise floor,
  a companion change held for a separate PR.

## Alternatives considered

- **Hand-roll the eval per project (minimal).** Rejected: design fidelity is a
  recurring, identical mechanism; per-project hand-rolling is the scar templates
  remove. (This was the explicit "minimal upstream" option, declined.)
- **Route through spec 008 / spec-oracle's `residual_judgment`.** Deferred:
  design fidelity is image-vs-image, not a classifiable spec-text AC; forcing it
  through the spec-text bridge is awkward and premature. design-eval and spec 008
  are two paths to ADR-0005's one contract; converging them (design-fidelity as
  a *kind* within a general eval-authoring framework) is a rule-of-three step for
  the second eval kind.
- **A general eval-authoring framework first, design-eval as a plugin.**
  Rejected on ADR-0003 grounds: build the concrete first instance, extract the
  shared `validate_freeze` / `aggregate_lower_bound` / `definition_hash`
  primitives (currently in `design-eval/score.py`) only when a second eval kind
  demands them.
- **jig grows the eval runner.** Rejected on scope (ADR-0005 / jig ADR-0019):
  jig attests; servo and the project's scorer run.

## Consequences

- **ADR-0005 gets its first real consumer** — it advances from "design intent"
  toward Accepted, exercised by a genuine non-deterministic AC.
- A UI project can now make "matches the design" *drive* the agent-loop and
  *gate* the quality-gate, with the same honesty posture as the deterministic
  oracle.
- Two eval-authoring paths now exist (design-eval recipe; spec-008 spec-oracle
  bridge). They share ADR-0005's contract but not yet code; the shared
  primitives are a pending extraction.
- New external dependency surface for adopters: a project must supply Playwright
  (a devDependency) and an `ANTHROPIC_API_KEY` for live scoring. Both degrade
  honestly to `env_error` when absent.
- Cost: `n × |screens|` judge calls per scored run, bounded by the frozen
  definition and the loop's cost ceiling.

## Relationship to other decisions

- **[ADR-0005](adr-0005-eval-oracle-component.md)** — the frozen-eval contract
  this recipe implements (clauses 1–7); clause 4's plateau-δ is a companion
  `loop.py` change (held for a separate PR).
- **[ADR-0002](adr-0002-gate-caller-contract.md)** — the 0/1/2 composite contract
  the component rides unchanged.
- **Spec 008 (eval-authoring)** — the sibling spec-oracle-bridge path; convergence
  deferred to the second eval kind.

## Amendments

- **2026-07-03.** The "second eval kind" this ADR's Alternatives section
  deferred extraction to has arrived (GitHub issue #16, content-fidelity).
  See [ADR-0024](adr-0024-extract-frozen-eval-harness.md), which extracts the
  shared freeze/aggregate/ledger/install primitives named here into
  `skills/_common/fidelity_eval.py`. This record's own text is unchanged —
  design-eval's public contract (config shape, component name, CLI) does not
  change.
