---
status: DRAFT
skill:
use_cases: []
---

# Spec 028: design-eval policy honesty (structured scoring policy)

> Realizes [ADR-0033](../../decisions/adr-0033-design-eval-structured-scoring-policy.md).
> Motivated by the v0.9.0 `/servo:design-eval` field report: an agent authored a
> free-text rubric backwards from a desired pass (excluding ~9 real divergences),
> then wrapped it in freeze + hash + n-sampling to look rigorous — scoring a
> non-matching UI at 0.7998/0.80.

## Overview

Replace design-eval's single free-text `rubric` string with a **structured
scoring policy** that separates the divergence catalogue from the scoring policy,
makes every exclusion a discrete `{id, reason}` item, and routes both the
exclusion list and the catalogue to a reviewer **distinct from the authoring
agent** before a freeze can claim the "prevention" property. Per ADR-0033 the
anti-gaming guarantee is a 2×2: an *exclusion* self-evidences on the frozen record
(auditability unconditional), but an *omission* (a thin catalogue) evidences
nothing and degrades to *nothing* without an independent **re-enumerating**
reviewer — so the adversarial case rests on that reviewer, not on surfacing alone.

Current state (probed 2026-08-27):
- The scoring policy is one opaque string: `templates/config.example.json:9`; it
  is injected verbatim into the judge prompt (`score.py` `_judge_cli:562`,
  `_judge_api:607`).
- Freeze hashes the rubric as opaque text (`fidelity_eval.artifact_hashes` →
  `sha256_text`, checked verbatim in `validate_freeze`); it is **not** part of the
  field-level `definition_hash` (`fidelity_eval.definition_hash` excludes it).
- `freeze()` (`design_eval.py:115`) stamps `approval_status: approved` after
  hashing; it inspects nothing about the rubric's content.
- Phase-0 (shipped `fix(design-eval)`, 2026-08-27) added loud stderr advisories
  for fake-scores and near-threshold ties, and softened the SKILL.md
  "bake-the-ignore-list-into-the-rubric" tip — mitigations, not this fix.

Non-goals: capture (ADRs 0031/0032), the reachability transports (spec 029 /
ADRs 0034–0035), and the deterministic oracle families are untouched. This spec
changes only the vision-judged per-screen *policy* and its freeze/review flow.

## Assumptions

- The vision judge scores a **named single dimension** against the reference at
  least as reliably as it scores a fused prose rubric. Per-dimension prompts are
  narrower, which should help — but this is unverified and load-bearing for the
  `dimensions` decomposition (ADR-0033 Kill criteria). **028-01 probes it before
  committing** the decomposition; if it regresses, 028-01 falls back to a single
  scored question plus the structured `ignore`-list (the anti-gaming core survives
  without the decomposition).
- ~One current frozen design-eval consumer exists in-repo, so a forced v1→v2
  re-author is low-blast-radius. **028-01 enumerates the installs** (`.servo/
  design-eval/config.json` under any target) before choosing force-re-author vs
  auto-migrate; the claim of "~one" is not yet an exhaustive enumeration.
- An independent reviewer subagent can re-enumerate divergences against a
  reference well enough to catch a thin catalogue a motivated author shipped —
  the load-bearing seam for the omission path (ADR-0033 §3/OQ5–6). **028-03 is
  where this is demonstrated**, not assumed; if it cannot add signal over unaided
  authoring, 028-03 degrades to "human-owned catalogue, surfaced at freeze."

## Decomposition

SPIDR — split by **Rules** (the scoring/exclusion policy) then **Path** (the
enumerate-first review flow). No Spike: ADR-0033 already did the framing, and each
open question is answerable inside a vertical slice (028-01 probes per-dimension
judging + the install enumeration as part of building the schema; 028-03
demonstrates the re-enumerator as part of building the catalogue mode).

- **028-01 (Rules + Data)** — the structured policy itself: `dimensions` +
  `ignore:[{id,reason}]`, `schema_version` 1→2, freeze hashing of the structure,
  judge-prompt assembled from the structure, and the v1→v2 migration disposition.
  Vertical: an author writes a structured policy, freezes it, and scores a screen
  with per-dimension judging + an explicit ignore-list — end to end.
- **028-02 (Interface + Rules)** — freeze-time exclusion surfacing to an approver
  *distinct from the authoring agent*, and the record of whether a freeze was
  independently reviewed or self-approved (the auditability-vs-prevention marker).
- **028-03 (Path)** — enumerate-first catalogue mode with an **independent
  re-enumerating reviewer**: produce an itemised divergence list, require every
  item to be scored or excluded, and gate the "prevention" property on the
  distinct re-enumerator (the omission-path seam).

## Slices

- [028-01 — structured-policy](slice-01-structured-policy.md)
- [028-02 — freeze-surfacing](slice-02-freeze-surfacing.md)
- [028-03 — catalogue-reenumerator](slice-03-catalogue-reenumerator.md)
