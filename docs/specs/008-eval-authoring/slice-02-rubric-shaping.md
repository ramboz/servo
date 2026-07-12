---
status: DRAFT
dependencies: [008-01, adr-0005, adr-0019, adr-0026]
last_verified:
---

## Slice 008-02 — rubric-shaping

**Goal:** Interactively turn one eval-able AC (008-01's output) into a concrete
rubric — scoring criteria, a scale, and the judge prompt — the artifact whose hash
[ADR-0005](../../decisions/adr-0005-eval-oracle-component.md) clause 2 freezes.
Servo-guided per ADR-0019; the human owns the rubric's content, the skill supplies
structure and templates (borrowed from the surveyed prior art, generalized).

### Acceptance criteria

- **AC1** A guided flow converts an eval-able AC into a rubric with: named scoring
  criteria, an explicit scale, and a judge prompt.
- **AC2** The judge prompt targets a **structured output**
  `{score: float in [0.0, 1.0], reasoning: str, strengths: [], weaknesses: []}`
  in JSON, sampled at low temperature, and degrades a malformed/unreachable judge
  reply to `env_error` — **never a silent `0.0`** (ADR-0005).
- **AC3** Three prompt **archetypes** are offered as editable starting templates:
  single-dimension, multi-criteria (weighted), and comparative (proposed-vs-baseline).
- **AC4** The rubric is a project-owned, inspectable artifact; the tool proposes,
  the human edits and approves before it is used (spec 008 goal 6).
- **AC5** The rubric artifact is in the exact shape the shared harness
  (`skills/_common/fidelity_eval.py`, ADR-0024) hashes and freezes — so 008-04 can
  emit it and spec-006 can freeze it without reshaping.
- **AC6** Tests cover: each archetype producing a valid rubric; the structured-output
  contract enforced; a malformed judge reply surfacing `env_error`, not `0.0`.

> The rubric here is generic — no modality-specific capture or baked prompt
> (ADR-0026); the human authors the criteria wording, the skill scaffolds the shape.
