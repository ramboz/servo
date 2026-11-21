---
status: DRAFT
skill: eval-authoring
use_cases: []
---

<!-- jig self-defining vocabulary (soft, forward-only): expand each acronym on first use and link the term to docs/memory/glossary.md (or jig's lexicon). See docs/workflow.md "Self-defining vocabulary". -->

# Spec 048: Judge regression set

> Implements [ADR-0053](../../decisions/adr-0053-judge-regression-rescore.md)
> (Proposed). Investigation record: jig
> [R-002](https://github.com/ramboz/jig/blob/main/docs/research/R-002-claude-code-verification-assessment.md),
> item 12 ("Review the reviewers").
> **Status: recorded, not yet built** — reserved alongside the ADR so the
> decision has a home for its build; the ADR must be Accepted before 048-01
> moves past DRAFT.

## Overview

servo can already ask "does this eval's judge agree with a human?" — spec
008-06's advisory `eval_authoring.py audit`. It cannot ask "did changing the
judge make it worse?": the audit reads whatever the latest scoring run produced,
its labels are an unfrozen side file, and its record does not say which judge
definition it measured. A judge model, decoding, rubric or policy change forces
a re-freeze, but nothing re-checks the judge against cases with known answers.
The loop's own judge (`agents/judge.md`) is never evaluated at all.

This spec gives each frozen eval a **regression set** — frozen candidate
artifacts with human labels, split into tuning and test — and a re-score that
runs the eval's judge over it (048-01); makes a judge-definition change carry a
fresh re-score into its re-freeze, without blocking on the numbers (048-02); and
measures the loop judge the same way (048-03). Everything stays advisory on the
composite, inside the refinement-todo deferral "Judge-audit → composite gating"
("the MVP makes judge-trust *visible*, not *enforced*").

Current state (probed 2026-11-21, working tree at `3e92dfc`):

- `audit_target` (`skills/eval-authoring/eval_authoring.py:1698-1777`) reads the
  latest ledger scoring run or `--scores` (`:1493-1560`), never calls a judge,
  and writes a `kind: judge_audit` record without a definition hash
  (`:1751-1772`). Scoring-run detection requires a `cases` list (`:1545`), so
  design-eval ledgers (`screens`) need `--scores`.
- Judge, samples and threshold are in `definition_hash`
  (`skills/_common/fidelity_eval.py:245-259`); the three freeze paths never
  consult an audit (`eval_authoring.py:1290-1320`, `design_eval.py:237-296`,
  `content_fidelity.py:115-142`).
- Retained candidates differ by kind: design-eval ledger rows name the exact
  `shot` each screen was judged on (`skills/design-eval/score.py:1271-1274`);
  eval-authoring native rows carry a `candidate_snapshot` with its sha256
  (`skills/eval-authoring/score.py:642-645`); content-fidelity rows retain no
  candidate text (`skills/content-fidelity/score.py:340-357`).
- Each kind has a per-candidate judge entry point with its own signature:
  `design-eval/score.py:762`, `content-fidelity/score.py:177`,
  `eval-authoring/score.py:260`.

**Relationship to spec 039 (DRAFT).** 048 does not subsume
[spec 039](../039-variance-gated-eval-judging/spec.md). 039's assumption A1 is
"unmeasured; slice 039-01's judge-audit replay (008-06's `judge_audit` records)
is the measurement", and 039-01's DoR asks for "a judge-audit replay of at least
one real eval (cheap vs frontier on the same cases)". That replay is two 048-01
re-scores of one frozen set, one per candidate judge definition. 039 keeps its
two-tier judge and should list 048-01 as a dependency when it activates (not
edited here).

**Relationship to spec 028-03.** The 0.7998-vs-0.80 field report
(`docs/refinement-todo.md`, "design-eval field report") produced 028-03's
independent re-enumeration of the divergence catalogue — an authoring-time
check that the policy is honest. A regression set is the measurement-time
complement: after any policy or model change, does the judge still fail a
candidate like that one?

**Sibling.** jig [ADR-0071](https://github.com/ramboz/jig/blob/main/docs/decisions/adr-0071-reviewer-recall-eval.md) /
[spec 126](https://github.com/ramboz/jig/blob/main/docs/specs/126-reviewer-recall-eval/spec.md)
measure jig's reviewer against jig's bug history. 048-03 applies the same method
to servo's loop judge; no shared code.

**Non-goals.** No composite gating or auto-demotion (the deferral stands); no
blocking on metric values; no automatic labeling; no CI-required billed runs; no
change to `definition_hash` or the frozen `hashes`.

## Assumptions

<!-- Spec 064-02 / ADR-0020 — grounding-by-probe (risk-gated). -->

- **Probed — a regression set can sit outside the freeze.** `definition_hash`
  reads judge, samples, threshold, cases and kind extras only
  (`fidelity_eval.py:245-259`), and `validate_freeze` checks only the paths
  listed in `hashes` (`:275-299`). Files under `<eval>/regression/` that are not
  listed there cannot stale the eval.
- **Probed — audit records cannot be mistaken for scoring runs.**
  `load_judged_scores` skips any record with a `kind` (`eval_authoring.py:1544-1545`),
  so regression records (also `kind: judge_audit`) stay out of the existing
  audit's input.
- **Probed — approval bookkeeping is already stored outside the hash.**
  design-eval stamps `approval_provenance` / `approved_by` on the config at
  freeze (`design_eval.py:286-289`) without hashing them; a regression stamp can
  follow the same pattern.
- **Probed — loop-judge verdicts are not persisted in run state.** They appear in
  the per-iteration stdout JSON (`skills/agent-loop/loop.py:4933-4938`) but not
  in `state.json`'s `oracle_score_history` (`:4910-4917`). Loop-judge cases are
  therefore authored or harvested from captured run logs.
- **Unverified — labels will exist.** No real eval has run an audit end to end
  (the thresholds are "expected to be re-tuned once a real judge audit has run",
  `eval_authoring.py:1474-1478`). ADR-0053's first kill criterion watches this.
- **Unverified — re-score noise is small enough.** Two re-scores of one
  definition differ; 048-01 reports both to make that visible (AC6).

## Decomposition

SPIDR: **Data** (the frozen labeled set and the re-score over it), then
**Rules** (when a re-freeze needs a fresh re-score), then **Paths** (the loop
judge, a different judge with a different output). No spike: the audit, freeze
and judge entry points it extends were probed above.

- **048-01 (Data)** — build a regression set per eval from labeled scoring runs
  and explicit historical cases; `audit --regression` re-scores the current
  definition over it and records metrics bound to a definition hash, a judge
  fingerprint and a set hash.
- **048-02 (Rules)** — a re-freeze whose judge fingerprint changed needs a
  matching regression record, or an explicit acknowledgement recorded as
  unaudited. Metrics are stamped, never blocking.
- **048-03 (Paths)** — `agents/judge.md` scored against labeled defect cases and
  clean controls, recall per stage, staleness flagged when the prompt or
  `models.judge` changes.

**Anti-horizontal-phasing.** 048-01 alone lets an author compare two judge
definitions on known answers; 048-02 makes that comparison arrive with every
judge change; 048-03 covers the judge the loop actually consults each
iteration. Each is usable on its own.

## Slices

- [048-01 — regression-set-and-rescore](slice-01-regression-set-and-rescore.md) — frozen labeled set per eval (tuning/test), `audit --regression`, per-stage and control metrics, records bound to definition + fingerprint + set.
- [048-02 — refreeze-needs-fresh-regression](slice-02-refreeze-needs-fresh-regression.md) — judge-fingerprint change at re-freeze requires a matching regression record or a recorded unaudited acknowledgement; advisory on the composite.
- [048-03 — loop-judge-recall](slice-03-loop-judge-recall.md) — `agents/judge.md` evaluated against labeled cases with per-stage recall and over-flagging controls; stale when its prompt or model changes.
