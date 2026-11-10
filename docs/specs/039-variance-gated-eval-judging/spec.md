---
status: DRAFT
skill: eval-authoring
use_cases: []
---

# Spec 039: Variance-gated eval judging

> **Status: DRAFT, scope capture.** Follow-up to
> [spec 038](../038-per-node-model-tiering/spec.md). No implementation until a
> consumer shows judge cost matters (see Activation trigger).

## Overview

Frozen eval components (ADR-0005; the shared harness in
`skills/_common/fidelity_eval.py`) score each case by calling one pinned judge
`n` times. They then aggregate with the conservative lower bound
`mean − k·stderr` (`aggregate_lower_bound`, `fidelity_eval.py:306-317`). The
default judge is `claude-sonnet-4-6` with `n=4, k=1.0, δ=0.03`
(`DEFAULT_JUDGE` / `DEFAULT_SAMPLES`, `skills/eval-authoring/eval_authoring.py:571-574`).

Every sample of every case pays that model's price, including cases where the
samples agree. The spread servo already computes (`stderr`) is a cheap, local
signal of when one judge is unsure. This spec makes it the trigger for a
two-tier judge:

1. Score each case with a **cheap first judge**.
2. When its samples are tight (stderr below a frozen gate), accept the
   lower-bound score.
3. When they are wide, **re-judge that case with a frontier judge** and use the
   frontier score.

That follows Anthropic's guidance that gating a second model "needs a cheap
signal". Here the signal is the variance servo already measures.

## Constraints this must respect

- **Freeze integrity (ADR-0005, 006-04).** Both judges, the gate value and the
  re-judge rule are part of the frozen definition. `definition_hash`
  (`fidelity_eval.py:245-259`) already hashes `judge` + `samples`, so adding a
  `judge.second` / `samples.rejudge_stderr` changes the hash and forces
  re-freeze. An old frozen eval keeps its single-judge meaning byte-for-byte.
- **Oracle authority.** The eval stays one oracle component scored by `gate.py`;
  the gate never sees which judge produced a score, except through the ledger.
- **Never a silent zero.** A frontier re-judge failure is an `EnvError` (rc 2),
  as today. It never falls back to the cheap score.
- **Honest ledger.** Each ledger row records which judge(s) ran, their samples,
  and whether the gate fired. That gives the eval-level counterpart of spec
  038's per-iteration accounting.

## Assumptions

- **A1:** a cheap judge's spread correlates with disagreement against the
  frontier judge, so that low-spread cases are where the cheap score is
  trustworthy. Unmeasured; slice 039-01's judge-audit replay (008-06's
  `judge_audit` records) is the measurement.
- **A2:** the cheap judge's `n` samples cost less than one frontier sample set
  for the target rubric. This holds at Haiku 5.5 list prices for prompts
  ≤100K tokens. Design-eval screenshots may exceed that, where Haiku's price
  rises 5×. Measure per eval.

## Activation trigger

Activate when either holds:

- eval-judge spend shows up as a material share of a real run's cost, visible
  through 038-01 accounting plus eval ledgers;
- an author asks for a cheaper default judge.

## Slices

- [039-01 — two-tier judge](slice-01-two-tier-judge.md) (DRAFT sketch)
