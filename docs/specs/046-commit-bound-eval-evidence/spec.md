---
status: DRAFT
skill: quality-gate
use_cases: []
---

<!-- jig self-defining vocabulary (soft, forward-only): expand each acronym on first use and link the term to docs/memory/glossary.md (or jig's lexicon). See docs/workflow.md "Self-defining vocabulary". -->

# Spec 046: Commit-bound evaluation evidence

> Investigation record:
> [R-002](https://github.com/ramboz/jig/blob/main/docs/research/R-002-claude-code-verification-assessment.md).
> **Status: recorded, not yet built** — reserved alongside the jig decision it
> serves so the servo half has a home for its build. No servo ADR: the
> cross-repo decision is
> [jig ADR-0069](https://github.com/ramboz/jig/blob/main/docs/decisions/adr-0069-commit-bound-verification-evidence.md)
> (Proposed; jig's half is
> [jig spec 124](https://github.com/ramboz/jig/blob/main/docs/specs/124-commit-bound-verification-evidence/spec.md);
> neither merged yet). Servo's changes stay inside existing contracts: additive
> gate payload fields (ADR-0002 clause 2) and additive `state.json` keys
> (ADR-0004). 046-01 should not move past DRAFT before jig ADR-0069 is Accepted,
> so the vocabulary below matches the accepted text.

## Overview

"A passing review on an out-of-date commit means nothing." The Claude Code team
stamps every commit with how it was verified, including "none", so unverified
commits can be queried.

**What servo already binds.** Since 042-04, `state.json` records the loop's
`start_head` (`skills/agent-loop/loop.py:4501`) and, at halt, a content
fingerprint — `{algo, head, tracked_diff, untracked}`: the `HEAD` sha plus
digests of the uncommitted tracked diff and of untracked file contents
(`loop.py:2288-2320`, written at `:3916` and `:5504`). Campaign's verified-wrapped
tier recomputes it with the same function. So R-002's "run state carries no
evaluated commit" holds per *evaluation*, not per run.

**What is not bound.** Each individual evaluation:

- `oracle_score_history` entries carry composite, threshold and status but no
  tree (`loop.py:4910-4918`);
- the gate's JSON goes to stdout only on the ordinary path
  (`skills/quality-gate/gate.py:372`, `:482`) — `gate.py` writes no record
  unless required-policy mode is on (`.servo/gate-runs/<run_id>/gate.json`,
  `skills/quality-gate/required_runtime.py:556-567`);
- spec-oracle ledger rows carry `ts` and, in required mode, `run_id`
  (`skills/spec-oracle/checks.py:1069-1080`);
- eval scoring records carry `at` and `definition_hash`
  (`skills/eval-authoring/score.py:626-650`; design-eval's record adds
  `capture_provider`, `skills/design-eval/score.py:1245-1280`).

The loop never commits (`agents/runner.md:92`), so a commit sha alone cannot say
what was judged. The fingerprint can, and it already exists.

**What this spec does.**

- **046-01** stamps every evaluation record — the gate payload, each loop history
  entry, spec-oracle ledger rows, eval scoring records — with the
  `evaluated_tree` fingerprint, or an explicit `null` with a reason. One
  implementation, shared with 042-04.
- **046-02** makes `gate.py` append a record for **every** outcome, including
  not-evaluable ones, and adds a read-only `gate.py evidence <target>` that
  answers whether the latest evidence still describes the current tree:
  `current`, `stale`, or `none`.

**Vocabulary alignment with jig ADR-0069.** jig owns the commit stamp (a
`Verified-by:` trailer whose values include `none`). Servo defines no trailer.
It provides the inputs a stamp can cite: an `evaluated_tree` on every
evaluation, and an `evidence` verb whose `current` + `pass` result is what a
"verified by servo oracle" value would mean, and whose `none` / `stale` map to
jig's `none`. 046-02 documents that mapping in `docs/architecture.md`; jig spec
124 decides how it is consumed.

**Non-goals.**
- The trailer, the commit gate and its off / observe / enforce modes — jig
  ADR-0069 / ADR-0070, jig specs 124 / 125.
- Making the loop commit its fix. `docs/refinement-todo.md:484` ("Does the
  dispatched loop commit its fix?") stays open; this spec makes the
  working-tree answer verifiable (a later commit of exactly the evaluated
  changes reads `current`, 046-02 AC3) without deciding it.
- Retention or compaction of the ledgers. `docs/refinement-todo.md:1156`
  ("HARVEST & COMPACT… the `heartbeat`/dispatch spine and `.servo/runs/` grow
  append-only") gains one more append-only file in `.servo/gate-ledger.jsonl`;
  that entry's resolution trigger covers it.
- Freeze anchoring — [spec 045](../045-base-anchored-freeze/spec.md). 046
  records 045's `freeze_anchor` when present and defines nothing about it.
- Binding `judge_audit` records (`skills/eval-authoring/eval_authoring.py:1751-1775`)
  to a judge definition — that belongs to
  [spec 048](../048-judge-regression-set/spec.md).

## Assumptions

<!-- Spec 064-02 / ADR-0020 — grounding-by-probe (risk-gated). -->

- **Probed 2026-11-21 (git 2.43, scratch repo):** after committing exactly the
  evaluated tracked changes, `git diff <H> <C> --full-index` has the same digest
  as the pre-commit `git diff HEAD --full-index`. A commit of exactly what was
  evaluated can therefore be recognised as `current`. Files that were untracked
  at evaluation time become additions in the commit and do not satisfy this
  rule; they read `stale` (the safe direction). Partial staging reads `stale`
  for the same reason.
- **Probed 2026-11-21 (code read):** the spec-oracle `ledger.jsonl` and
  required-mode `runs/` directory live in the tracked spec directory
  (`docs/architecture.md:262`; `required_runtime.py:594`), and the shared
  exclusion predicate filters only `.servo/`, caches and coverage files
  (`loop.py:342-347`, `:2100-2120`). A gate run's own ledger append therefore
  changes the fingerprint today. 046-01 AC3 fixes this.
- **Unverified:** whether target repos commit or ignore the spec-oracle
  `ledger.jsonl`. Either way it has to be excluded, so the answer does not change
  the design.
- **Not enforced:** the tree is quiet during an evaluation. The loop scores
  after the runner exits (`agents/runner.md:26`) and the Stop hook scores on
  stop, so this holds in servo's own flows; a concurrent external edit would make
  the stamp describe the pre-evaluation tree.
- **Evidence is local.** `.servo/` is git-ignored (`docs/architecture.md:438`),
  so the gate ledger does not travel with the repo. Durable, shared evidence is
  jig's commit stamp, not servo's ledger.

## Decomposition

SPIDR (Spike / Paths / Interfaces / Data / Rules — see the jig glossary):

- **Spike:** none needed. The post-commit equivalence was probed (Assumptions).
- **Data** (the first split): reuse the 042-04 fingerprint as the evaluation
  identity rather than invent a second one. 046-01 is "every record carries it".
- **Interfaces:** the gate payload, `state.json` history and component ledgers
  (046-01); a gate-owned ledger and a read-only evidence verb (046-02).
- **Paths:** pass / below threshold / env-error (not evaluable); clean vs dirty
  tree; non-git target; component invoked outside the gate.
- **Rules:** freshness is exact match, or exactly-committed, or path-scoped on
  clean evidence; everything else is `stale`; no record is `none`.

**Anti-horizontal-phasing.** 046-01 alone lets anyone reading a ledger, a loop
state or a gate payload tell which tree a score belongs to. 046-02 alone turns
that into an answer a person or a jig commit gate can ask for: is this pass about
the tree in front of me?

## Slices

- [046-01 — evaluated-tree-stamp](slice-01-evaluated-tree-stamp.md) — gate payload, loop history, spec-oracle and eval ledgers carry the evaluated tree (042-04 fingerprint, one implementation); servo's own evidence writes excluded from it.
- [046-02 — gate-ledger-and-staleness](slice-02-gate-ledger-and-staleness.md) — `gate.py` records every outcome including not-evaluable; read-only `gate.py evidence` reports `current` / `stale` / `none`.
