---
status: Proposed
dependencies: []
last_verified: 2026-11-21
frame_review: true
---

# ADR-0053: Judge definition changes are re-scored against a frozen labeled set

## Status

Proposed (2026-11-21). **Recorded, not yet built** — implemented by
[spec 048](../specs/048-judge-regression-set/spec.md); this ADR must be Accepted
before 048-01 moves past DRAFT. Investigation record: jig
[R-002](https://github.com/ramboz/jig/blob/main/docs/research/R-002-claude-code-verification-assessment.md),
item 12 ("Review the reviewers").

## Context

The Claude Code team grades its graders: historical cases with one-sentence
answer keys, merged and stable changes as an over-flagging control, a tuning set
kept apart from a fixed test set, recall measured per pipeline stage, and every
change to a reviewer's prompt, tools or model re-scored (R-002 item 12).

servo has the first piece and none of the rest (probed 2026-11-21, working tree
at `3e92dfc`):

- **An advisory judge-trust audit exists.** Spec 008-06's
  `eval_authoring.py audit` (`skills/eval-authoring/eval_authoring.py:1698-1777`)
  takes the judged case scores from the *latest scoring run* in the eval's
  ledger, or a `--scores` file (`:1493-1560`), joins them with an ad-hoc
  `--labels` file, and computes fail-precision, pass-miss-rate and, above a
  20-label floor, score-vs-human drift (`:1617-1681`). It recommends `auto` or
  `confirmed-only` against thresholds the code calls "starting numbers, not
  derived ones" (`:1473-1484`), appends a `kind: judge_audit` ledger record, and
  provably changes nothing else (008-06 AC4).
- **That audit measures a run, not a definition.** It never calls the judge, its
  labels are not frozen, and its record carries no definition hash
  (`:1751-1772`), so nobody can tell which judge definition it measured. It also
  only reads ledgers whose runs carry a `cases` list (`:1545-1546`);
  design-eval's ledger records `screens` (`skills/design-eval/score.py:1267`), so
  design-eval needs `--scores`.
- **A judge change forces re-freeze, not re-audit.** The judge block is part of
  `definition_hash` (`skills/_common/fidelity_eval.py:245-259`) and the rubric is
  in the frozen `hashes`, so changing either makes the eval refuse as stale until
  re-frozen (`:275-299`). None of the three freeze paths
  (`eval_authoring.py:1290-1320`, `skills/design-eval/design_eval.py:237-296`,
  `skills/content-fidelity/content_fidelity.py:115-142`) consults an audit.
- **The loop's judge is never evaluated.** `agents/judge.md` has surface tests
  only (`skills/agent-loop/test_loop.py:4285-4340`); a prompt edit or a
  `models.judge` change (spec 038) ships unmeasured.

Two records bound the answer:

- **The composite-gating deferral.** `docs/refinement-todo.md`, "Judge-audit →
  composite gating (auto-demote an untrusted judge)": auto-demoting "would touch
  the ADR-0005 frozen-eval gate contract, so it is deliberately out of the MVP
  (the MVP makes judge-trust *visible*, not *enforced*)." Its resolution trigger
  is a real eval whose audit surfaces an untrustworthy judge.
- **The field case.** A frozen, hashed design eval scored a UI with nine real
  divergences at 0.7998 against a 0.80 bar (`docs/refinement-todo.md`, "design-eval
  field report"; [ADR-0033](adr-0033-design-eval-structured-scoring-policy.md)).
  Spec 028-03 answered it at authoring time with an independent re-enumeration
  of the divergence catalogue. Nothing yet checks, after a policy or model
  change, that the judge still fails a candidate like that one.

[Spec 039](../specs/039-variance-gated-eval-judging/spec.md) (DRAFT) rests on
an unmeasured assumption (A1) whose measurement it calls a "judge-audit replay":
cheap and frontier judges scored on the same cases.

## Decision Options Considered

### Option A: Status quo — re-freeze on change, audit when someone thinks to
- **Pros:** no new artifacts; the audit already makes judge trust visible.
- **Cons:** the audit is unbound to a definition and unrepeatable (labels are not
  frozen, the judge is not re-run), so a model or rubric change ships without
  evidence it still fails known-bad candidates.

### Option B: A frozen labeled regression set per eval, re-scored on every judge-definition change; advisory on the composite (chosen)
- **Pros:** the same frozen cases score every candidate definition, so changes
  are comparable; the post's controls (answer keys, over-flagging controls,
  tuning/test split, per-stage numbers) fit the existing audit metrics; stays
  inside the composite-gating deferral; reuses the audit record and the freeze
  path rather than adding a gate.
- **Cons:** someone must label cases and keep frozen candidate artifacts; each
  re-score costs `n × |test cases|` judge calls; a freeze-time freshness check is
  one more step on re-freeze.

### Option C: Option B plus enforcement — refuse re-freeze, or demote the component at score time, when metrics miss the thresholds
- **Pros:** closes the false-pass-via-untrusted-judge hole the ADR-0027
  frame-critique named.
- **Cons:** resolves the deferral before its trigger has fired, on thresholds the
  code itself calls provisional; touches the ADR-0005 gate contract.

### Option D: Continuous live auditing — sample every scoring run for human labels
- **Pros:** labels stay current with the real candidate distribution.
- **Cons:** needs a human inside an unattended loop; still cannot say whether a
  *definition change* made the judge worse, because each run scores different
  candidates.

### Option E: A second model grades the judge on every score
- **Pros:** fully automatic.
- **Cons:** doubles judge spend; the post found a second reviewer "often a worse
  approach than tuning the primary"; who grades the grader is unanswered.

## Recommended Decision

**Option B**, with these constraints. Mechanism and thresholds are spec 048's.

1. **A regression set is frozen, labeled evidence, kept apart from the eval
   definition.** Each case pairs a *frozen candidate artifact* (the text or
   screenshot the judge scores — never re-gathered, so generator variance cannot
   leak in) with a human label (pass/fail, optional score), a provenance (a
   `judge_audit` record, an incident, or an accepted-state control) and a split
   (`tuning` or `test`). The set has its own content hash and sits outside
   `definition_hash` and the frozen `hashes`, so growing it never stales an eval.
2. **Re-scoring runs the eval's own judge over the set** with the definition as
   written (frozen or not), reports the existing audit metrics on the **test**
   split plus a control over-flag rate and the pass-miss rate per stage (single
   samples vs the aggregated lower bound), and appends a `judge_audit` record
   that names the definition hash, the judge fingerprint and the set hash it
   measured.
3. **Freshness, not a pass mark, at re-freeze.** When an eval has a regression
   set and its *judge fingerprint* changes (judge model, decoding and transport;
   samples; threshold; rubric or the prompt-bearing policy fields), freeze needs
   a regression record for the new fingerprint against the current set — or an
   explicit acknowledgement, recorded on the approval as unaudited (the
   `self_approved` pattern of design-eval 028-02). The metrics are shown and
   stamped; they never block. An eval without a set freezes exactly as today.
4. **Score time is untouched.** No composite, `oracle.sh` or `gate.py` change; the
   composite-gating deferral stands. The regression records are the evidence its
   trigger asks for.
5. **The loop's judge gets the same treatment, advisory.** `agents/judge.md` is
   scored against labeled cases — defects with one-sentence answer keys, plus
   clean controls — with recall per stage (the finding in `reasoning`, then the
   verdict). A prompt or `models.judge` change leaves the last result marked
   stale until re-run. ADR-0005 clause 1's distinction holds: the loop judge is
   measured, not made an oracle component.

**Relationship to existing ADRs — none superseded.**
- **[ADR-0005](adr-0005-eval-oracle-component.md):** clause 2 (freeze) gains an
  approval-time freshness check, not a new definition field; clause 7 (ledger)
  gains regression records. Clauses 1 and 3–6 unchanged.
- **[ADR-0027](adr-0027-goal-to-eval-assisted-authoring.md):** its frame-critique
  produced the deferral this ADR leaves in place.
- **ADR-0033:** design-eval's `dimensions` and `ignore` build the judge
  instruction, so they belong in its judge fingerprint. A regression set is the
  measurement-time complement to 028-03's authoring-time re-enumeration.
- **[ADR-0036](adr-0036-frozen-evals-satisfy-suitability-signal.md):** unchanged;
  whether `reviewed` provenance should also require a fresh regression record is
  an open question.
- **[ADR-0003](adr-0003-fresh-subagent-roster.md) /
  [ADR-0047](adr-0047-per-node-model-tiering-and-escalation-ladder.md):** the
  roster and per-node models are unchanged; their changes become re-run triggers.

**Spec 039.** 048 does not subsume it. 039-01's DoR replay — cheap and frontier
judges on the same cases — is two 048-01 re-scores of the same frozen set, one
per candidate judge definition, compared case by case. 039 keeps its two-tier
judge; it should take 048-01 as a dependency when activated.

**jig sibling.** jig [ADR-0071](https://github.com/ramboz/jig/blob/main/docs/decisions/adr-0071-reviewer-recall-eval.md) /
[spec 126](https://github.com/ramboz/jig/blob/main/docs/specs/126-reviewer-recall-eval/spec.md)
measure jig's own reviewer against jig's bug history. Same method, different
subject; servo shares no code with it.

## Consequences

**Becomes easier:**
- A judge model, decoding, rubric or policy change arrives with numbers: did it
  start passing a known-bad candidate, or failing an accepted one?
- The composite-gating deferral can be decided on recorded evidence when its
  trigger fires, rather than on the first ad-hoc audit.
- Spec 039's A1 becomes measurable without a separate replay tool.
- A loop-judge prompt edit stops shipping blind.

**Becomes harder:**
- Authors must label cases and keep candidate artifacts (screenshots, generated
  text) under the eval directory.
- Re-scoring spends model calls; re-freeze gains a step for evals that have a set.
- Judge fingerprints must be defined per eval kind and kept current as kinds add
  prompt-bearing fields.

## Assumptions

- **Labels can be had.** At least some real evals will accumulate enough labeled
  cases (the drift floor is 20, `eval_authoring.py:1479`) for the metrics to be
  more than `n/a`. Unverified; no real eval has run an audit end to end
  (the thresholds are "expected to be re-tuned once a real judge audit has run",
  `:1474-1478`).
- **Re-score noise is smaller than the change it must detect.** A judge is
  stochastic; two re-scores of one definition differ. The `n`-sample lower bound
  damps this, but by how much on a regression set is unmeasured.
- **Frozen candidates stay representative** of what the loop produces later.
- **Each eval kind exposes a per-candidate judge call** a re-scorer can drive:
  `judge()` exists in design-eval (`score.py:762`), content-fidelity
  (`score.py:177`) and eval-authoring (`score.py:260`), each with a different
  signature. Verified to exist; the adapter shape is spec 048's.

## Kill criteria

- After a reasonable period, no real eval holds a regression set large enough
  for non-`n/a` metrics. The machinery measures nothing; retire it to the
  existing advisory audit.
- Re-scoring the *same* definition twice moves the metrics as much as the
  definition changes do. The numbers cannot tell a better judge from a worse one.
- Most re-freezes take the unaudited acknowledgement. The check is friction
  without information; drop it and keep the on-demand re-score.

## Open questions

- Minimum test-split size, and label ownership (author, a distinct reviewer as in
  028-03, or either)?
- Should ADR-0036's `reviewed` provenance require a fresh regression record?
- Who pays for loop-judge re-runs, and should servo's CI ever require one?
  (R-002 asks the same of jig ADR-0071.)
- Should the loop-judge case format align with jig spec 126's, so one labeling
  practice serves both?
