---
status: DRAFT
dependencies: [adr-0005, adr-0024]
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

## Slice 049-01 — verify-candidate-gather

**Goal:** An eval-authoring case can declare `source: {"type": "verify",
"scenario": <name>}`, and a live `score()` gets that case's candidate by running
the project's declared verify entry point — through a shared resolver the presets
reuse in 049-02 — while every case and eval without it behaves exactly as today.

**DoR:**
- ✅ jig [ADR-0073](https://github.com/ramboz/jig/blob/main/docs/decisions/adr-0073-repo-verify-skill-contract.md)
  Accepted and jig spec 128-01 DONE, so the declaration format and the entry
  point's invocation (scenario, input, output, exit codes) are fixed. Cross-repo
  dependencies cannot be expressed in `dependencies:` (the validator accepts
  only local `NNN-MM` / `adr-NNNN` tokens), so this item is checked by hand.
- ✅ The spec's contract assumptions re-checked against the accepted jig
  contract. If it cannot take a per-case input, this slice narrows to
  input-free scenarios and refuses at freeze any verify-sourced case that carries
  an `input` — the input is part of the definition and must not be silently
  ignored.
- ✅ Re-probed: `_gather_candidate` and its call site
  (`skills/eval-authoring/score.py:415-429`, `:609-611`) and
  `_definition_fields` (`:158-161`).

**Acceptance Criteria:**

1. **Shared resolver.** `skills/_common/verify_contract.py` (stdlib only) finds the
   target's declared verify entry point and returns its argv, its scenarios and
   its identity (declaration path and sha256) — or `absent` / `malformed` with a
   reason. Resolution reads files only; it never runs the entry point.
2. **Verify-sourced live gather.** For a case with `source: {"type": "verify",
   "scenario": <name>}`, a live `score()` runs the entry point for that scenario
   once per case per run, passes the case `input` as the contract specifies,
   takes its output as the candidate, and judges it `n` times — content-fidelity's
   gather-once rule — with a 180-second timeout.
3. **Honest failure.** No declared contract, an unknown scenario, a non-zero exit,
   a timeout or empty output is an `EnvError` (rc 2) naming the case and cause —
   never a placeholder candidate and never a 0.0 score.
4. **Today's behaviour otherwise.** A case without `source` raises today's
   "candidate-gather is not yet implemented" `EnvError` unchanged; the fake-score
   hooks and the native `candidate_file` path are unchanged; a verify source on a
   Copilot-transport eval is refused at freeze, since native scoring keeps its
   file-snapshot policy.
5. **No re-freeze for existing evals.** `source` joins the pinned case fields only
   for evals that declare it (the `_definition_fields` pattern), so every
   existing frozen eval's `definition_hash` is byte-identical and its
   `validate_freeze` still passes. Changing a case's source or scenario refuses
   as stale until re-frozen.
6. **Environmental identity, recorded.** The contract's content is not hashed into
   the freeze; every ledger row of a verify-sourced run records the resolved argv
   and the declaration sha256 (advisory, like design-eval's `capture_command`).
7. **Constraint cases stay honest.** A verify-sourced case with
   `expected_output.constraints` still raises the existing missing-actual-values
   `EnvError` (`eval-authoring/score.py:516-524`).
8. **Docs.** The "named limitation" in `skills/eval-authoring/SKILL.md` is
   narrowed: live gather works for verify-sourced cases; other cases keep the
   limitation. Surface-tested.

**DoD:**
- [ ] All ACs pass; full test suite green (no regressions).
- [ ] Implementer test coverage exercises each AC with at least one
      fixture (a stub verify entry point under a temp target; no network).
- [ ] Each new test has been shown to fail when its feature is removed —
      the test is capable of failing, not vacuously green (mutate the
      feature, watch the test go red, restore).
- [ ] Host packages rebuilt and drift-clean
      (`scripts/build_host_packages.py --check`), including the copied
      `verify_contract.py` beside each installed `score.py`; Python 3.9 floor
      respected.
- [ ] Reviewed by `reviewer` subagent. Reviewer prompt built by
      `review.py`.
- [ ] Implementation review passed (compliance + craft + arch).
- [ ] Deviation log produced under this slice heading.
- [ ] Reconciliation sweep produced under this slice heading.
- [ ] Reconciliation review passed.
- [ ] `docs/refinement-todo.md`: the "candidate-gather … is unbuilt" entry is
      updated to say verify-sourced cases are resolved here and `file|command`
      sources plus actual-value extraction remain.

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

**Anti-horizontal-phasing check:** After this slice, a project that ships a verify
skill can author an eval-authoring eval whose cases name verify scenarios, and the
installed component scores live candidates under the gate and the agent loop —
where today it can only env-error.

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
