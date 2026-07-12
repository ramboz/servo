---
status: DONE
dependencies: [008-01, adr-0005, adr-0019, adr-0026]
last_verified: 2026-07-12
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

### Deviation log (after reconciliation)

Original ACs preserved above.

- **Generic scorer core added (`skills/eval-authoring/score.py`).** Modeled on
  `content-fidelity/score.py`, a thin wrapper over the ADR-0024 harness. This slice
  ships the judge path only: `_prompt` (rubric → prompt), `_judge_api`/`_judge_cli`
  transport dispatch, and a single `_parse_judge_reply` (better than the sibling's
  inline duplication) that requires a numeric `score`, clamps to [0,1], and raises
  `EnvError` on missing/non-numeric/unparseable/unreachable replies — **never a
  silent 0.0** (AC2, ADR-0005). Composite / n-sample / gather / freeze / ledger /
  oracle.sh-splice are a clean, documented seam deferred to 008-04.
- **Structured judge schema is richer than the sibling's.** The prompt asks for
  `{score, reasoning, strengths, weaknesses}` (AC2) vs content-fidelity's
  `{score, reasoning}`; only `score` is load-bearing, the rest are captured for the
  008-06 audit's human-visibility.
- **`config.json` schema (harness-shape, AC5).** `{schema_version, approval_status,
  archetype, source_ac, judge, samples, threshold, rubric, cases: []}` — the five
  harness-pinned keys are byte-identical to what `fidelity_eval.definition_hash`/
  `validate_freeze` consume (proven for `definition_hash` via a per-archetype
  round-trip test; `validate_freeze` exercise is 008-04's freeze concern — it needs
  `approval_status: approved` + `approved_content_hash`); the extras are ignored by
  the hash. `cases` stays empty (008-03's job).
- **Doc-nit fixes (reconciliation).** Updated the module header to name 008-01 +
  008-02; corrected the `DEFAULT_JUDGE` comment to state temperature is pinned to
  0.0 (lower than content-fidelity's 0.6) deliberately, rather than "mirroring" it;
  corrected `rubric_target`'s docstring to state it gates on `classification ==
  eval-able` only (the per-AC human-approval gate is 008-04's freeze, not a
  `confirmed`-flag check here).

**Carry-forward to 008-03 / 008-04 (flagged by craft review):**

- **Judge signature must widen for the comparative archetype.** `judge(candidate,
  config)` / `_prompt(candidate, config)` is candidate-only, but the `comparative`
  archetype frames PROPOSED-vs-BASELINE and the case shape pins a `reference`.
  008-03 (case shape) + 008-04 (scoring) must widen the signature to carry the
  reference/baseline. Nothing scores in 008-02 so it is not a bug yet.
- **`_slug(ac_id)` can collide** for distinct AC ids (`AC-1` / `AC.1` → `ac_1`),
  which would silently overwrite a prior eval dir and matters at `score_<name>`
  compile time. 008-04 (which owns the emitted component name) should disambiguate.
- **rubric.md / config.json dual source of truth.** `rubric.md` currently embeds
  the rubric text with a "keep in sync" instruction, but only `config.json`'s
  `rubric` is hashed/frozen. 008-04 (which owns approve/freeze) should make
  `config.json` the single source and render `rubric.md` as a generated view.

### Reconciliation sweep

- **`docs/architecture.md`** — `no-op`. Still a self-contained skill on the
  existing ADR-0024 harness; no module-boundary/public-contract change (no
  `arch_review`). `score.py` is a new sibling scorer, parallel to (not shared with)
  content-fidelity's, honoring the "not refactoring the presets" non-goal.
- **Load-bearing decision / ADR trigger** — `no-op`. Archetype set, richer judge
  schema, and 0.0 temperature are derivations of ADR-0005's clause-2 rubric-freeze
  and AC2, not new load-bearing choices with rejected alternatives.
- **`.claude-plugin/install-contract.json`** — `deferred`. Still no SKILL.md; suite
  + install-surface checks green without it; registration lands at close-out.
- **`docs/refinement-todo.md`** — `no-op`. The three carry-forwards are next-slice
  work with concrete owners (008-03/04) in this deviation log, not open-ended debt.
- **Status board** — `deferred`. Regenerated after `DONE`.
- **`_judge_cli` untested** — `deferred`. Parity with content-fidelity (which also
  leaves its cli path untested); revisited when a real cli-transport consumer
  appears.
