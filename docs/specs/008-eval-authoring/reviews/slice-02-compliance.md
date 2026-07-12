---
slice: 008-02 — rubric-shaping
pass: compliance
verdict: pass
reviewer: jig:reviewer
reviewed_at: 2026-07-12T14:51:15Z
prompt_source: review.py implementation ... 008-02
---

VERDICT: pass

All six ACs of slice 008-02 (rubric-shaping) met with meaningful tests. AC1: the
`rubric` subcommand converts an eval-able AC (from 008-01's triage) into a rubric
with named criteria + scale + judge prompt. AC2 (solid): `_parse_judge_reply`
requires a numeric `score`, clamps to [0,1], and raises EnvError on
missing/non-numeric/unparseable/unreachable replies — every failure path asserted
to be EnvError, never a silent 0.0. AC3: three editable archetypes
(single_dimension / multi_criteria / comparative). AC4: project-owned, colocated
config.json + rubric.md; human gate explicit. AC5 (proven): config round-trips
through fidelity_eval.definition_hash for every archetype with no reshaping. AC6
tests cover archetypes / env_error / clamp / round-trip.

Non-blocking nits → reconciliation: (1) `rubric_target` docstring overstates a
`confirmed`-flag invariant it doesn't enforce (freeze at 008-04 is the real gate);
(2) `_judge_cli` lacks direct tests (parity with content-fidelity).
