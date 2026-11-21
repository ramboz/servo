---
status: DRAFT
dependencies: [adr-0053]
last_verified: 2026-11-21
arch_review: true
---

<!-- jig self-defining vocabulary (soft, forward-only): expand each acronym on
     first use and link the term to docs/memory/glossary.md (or jig's lexicon).
     See docs/workflow.md "Self-defining vocabulary". -->

<!-- jig grounding (spec 064-02 / ADR-0020): ground factual claims about
     runnable surfaces by probe first (run it / read source) or a citation,
     else mark them as assumptions in the spec's `## Assumptions` section —
     never assert an unverified claim as fact. -->

## Slice 048-01 — regression-set-and-rescore

**Goal:** Each frozen eval can hold a regression set — frozen candidate
artifacts with human labels, split into `tuning` and `test` — and
`eval_authoring.py audit --regression` re-runs the eval's own judge over it,
reporting the existing audit metrics plus an over-flagging control and a
per-stage miss rate, in a ledger record bound to the definition, judge
fingerprint and set it measured.

**DoR:**
- ✅ [ADR-0053](../../decisions/adr-0053-judge-regression-rescore.md) Accepted.
- ✅ Re-probed at implementation time: `audit_target` and its metric helpers
  (`eval_authoring.py:1581-1777`), the three kinds' `judge()` signatures, and
  each kind's ledger fields for retained candidates (spec Overview).
- ✅ The judge fingerprint's field list per kind is agreed at arch-review: judge
  model, decoding and transport; samples (`n`, `k`, `delta`); threshold; the
  rubric hash; and the kind's prompt-bearing fields (design-eval: `dimensions`,
  `ignore` — SKILL.md says the judge instruction is assembled from them).
  Case lists are excluded.

**Acceptance Criteria:**

1. **Add a historical case.** `eval_authoring.py regression add <eval> --case
   <id> --candidate <file> --label pass|fail [--score S] [--split test|tuning]
   --source <ref>` copies the candidate under `<eval>/regression/` and records
   the case in `<eval>/regression/regression.json`. `--source` names an incident,
   a ledger run, or `control` (an accepted, stable state — the over-flagging
   control). A missing candidate, an unknown label or split, or a duplicate id
   is an `EnvError` with nothing written. Adding cases to a frozen eval leaves
   `validate_freeze` passing.
2. **Seed from a labeled scoring run.** `regression add <eval> --from-run
   <ledger-at> --labels <file>` (the audit's label format, `parse_labels`,
   `eval_authoring.py:1581`) imports every labeled case whose candidate that run
   retained — a design-eval `shot` (`design-eval/score.py:1271-1274`), or a native
   `candidate_file` whose current sha256 matches the run's `candidate_snapshot`
   (`eval-authoring/score.py:642-645`) — and lists each case it could not import
   with the reason. Content-fidelity runs retain no candidate text, so their
   cases are added with `--candidate` (AC1).
3. **Re-score the current definition.** `eval_authoring.py audit <eval>
   --regression` loads the working `config.json` as written (frozen or not),
   runs the kind's own `judge()` `n` times on each **test** case's frozen
   candidate, aggregates with the eval's lower bound, and computes
   fail-precision, pass-miss-rate and drift with the existing helpers. It never
   gathers a fresh candidate and never reads or writes `oracle.sh`.
4. **Controls and stages.** The record adds a control over-flag rate (control
   cases the judge fails ÷ control cases) and the pass-miss rate at two stages:
   per sample (each raw judge call) and per case (the aggregated lower bound) —
   so an author can see whether aggregation or the judge itself catches a fail.
5. **The record is bound to what it measured.** It is appended to
   `<eval>/ledger.jsonl` as `kind: judge_audit`, `mode: regression`, with the
   working definition's `definition_hash`, its judge fingerprint, the set's
   content hash, the split, per-case samples and the metrics. The existing
   `audit` (no `--regression`) output is byte-identical to today's.
6. **Tuning stays apart from test.** `--split tuning` scores only tuning cases
   and records `split: tuning`; such records never satisfy 048-02. Moving a case
   between splits changes the set hash. Two consecutive test-split re-scores of
   one definition are both recorded, so re-score noise is visible.
7. **Honest failure.** An unreachable judge, a malformed reply, or a missing or
   hash-mismatched candidate is an `EnvError` (exit 2) and writes no record —
   never partial metrics. An empty test split reports every metric as `n/a`
   with a stated note, like the existing empty-denominator handling.
8. **Advisory, provably.** A regression run changes neither `config.json`,
   `oracle.sh`, nor any gate result (the 008-06 AC4 proof, extended).
9. **Docs.** `skills/eval-authoring/SKILL.md` documents the regression set, the
   splits, the record and its cost (`n` × test cases judge calls).
   Surface-tested.

**DoD:**
- [ ] All ACs pass; full test suite green (no regressions).
- [ ] Implementer test coverage exercises each AC with at least one
      fixture. Edge cases listed in the slice are covered explicitly — including
      a known-bad fixture modelled on the 0.7998 field report (a human-`fail`
      candidate) that surfaces as a pass-miss when the judge passes it.
- [ ] Each new test has been shown to fail when its feature is removed —
      the test is capable of failing, not vacuously green (mutate the
      feature, watch the test go red, restore).
- [ ] Host packages rebuilt and drift-clean
      (`scripts/build_host_packages.py --check`); Python 3.9 floor respected.
- [ ] Reviewed by `reviewer` subagent. Reviewer prompt built by
      `review.py`.
- [ ] Implementation review passed.
- [ ] Deviation log produced under this slice heading.
- [ ] Reconciliation sweep produced under this slice heading.
- [ ] Reconciliation review passed.
- [ ] `docs/refinement-todo.md` updated if any decisions were
      deferred during implementation; the "Judge-audit → composite gating"
      entry gains a pointer to regression records as its evidence source.

### Close-out (post-DONE)

These items can only be ticked AFTER the final `RECONCILED → DONE`
transition. Slice-land's `check_dod` (slice 009-01) excludes them
from the count.

- [ ] `docs/specs/README.md` regenerated by `workflow.py status-board`.
      Notes column receives any load-bearing per-slice invariant
      (it's preserved across regen).
- [ ] Primer hygiene per spec 025-01 rule: **if this slice closes the
      spec** (all non-deferred slices DONE), check `CLAUDE.md`,
      `AGENTS.md`, and scaffold templates when present, then **compress**
      the spec's Active-specs entry — drop facts derivable from the
      spec dir + status board, migrate load-bearing per-slice
      invariants to the status board Notes column, keep at most a
      one-liner only for cross-cutting facts. If the spec is still
      in flight (other slices DRAFT / READY / IN_PROGRESS), leave
      the entry. If this slice introduces a new skill, add or
      update its row in the Skills table.

**Anti-horizontal-phasing check:** After this slice, an author about to switch an
eval's judge model can re-score the old and new definitions on the same frozen,
labeled candidates and see whether the new one passes something a human failed
or fails an accepted control — evidence today's audit cannot produce.

### Deviation log (after reconciliation)

The original spec is preserved above. Implementation notes:

_TODO: numbered sections covering deviations from the planned shape,
reviewer findings folded back in, doc updates, plan adherence._

### Reconciliation sweep

Record the drift-prone surfaces checked during reconciliation. The transition
gate only requires this subsection to exist; the reconciliation reviewer judges
whether coverage and rationales are honest.

| Artifact | Disposition | Rationale |
|----------|-------------|-----------|
| `README.md` | `no-op` | _TODO: why this slice did not affect the project front door, or summarize the update._ |
| `docs/specs/README.md` | `updated` | _TODO: regenerated by `workflow.py status-board`, or explain why deferred._ |
| `docs/product-vision.md` | `no-op` | _TODO: checked for behavior / scope drift._ |
| `docs/architecture.md` | `no-op` | _TODO: checked for module-boundary / public-contract drift._ |
| Primer surfaces: `CLAUDE.md` / `AGENTS.md` / scaffold templates | `no-op` | _TODO: primer hygiene checked; note compression or template updates if any._ |
| `docs/inbox.md` | `no-op` | _TODO: checked for items resolved by this slice._ |
| `docs/refinement-todo.md` | `no-op` | _TODO: checked for resolved items or new deferred decisions._ |
| `docs/memory/**` | `no-op` | _TODO: note memory-sync result or why nothing was worth capturing._ |
| `docs/decisions/README.md` / ADR index | `no-op` | _TODO: use `updated` when the slice touched ADRs; otherwise mark checked._ |
| Additional live prose / generated templates touched by this slice | `deferred` | _TODO: name owner or trigger when real cleanup remains; otherwise replace with `no-op`._ |
