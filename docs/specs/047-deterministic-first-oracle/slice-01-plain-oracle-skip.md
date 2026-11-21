---
status: DRAFT
dependencies: [adr-0052]
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

## Slice 047-01 — plain-oracle-skip

**Goal:** In a plain (no required policy) servo oracle, judged components declare
their kind and run after the deterministic ones; when the deterministic results
already decide the exit code, the oracle skips the judged components, exits as
full scoring would, prints a lower-bound composite, and says on stderr what it
skipped and why (ADR-0052 Option D).

**DoR:**
- ✅ [ADR-0052](../../decisions/adr-0052-deterministic-components-gate-judges.md)
  Accepted.
- ✅ Arch-review confirms the kind mechanism: a `kind_<name>` shell function
  inside the component's `# SEED:` block, written by the shared
  `fidelity_eval.splice_component` when an installer passes a judged kind. Check
  that nothing seals SEED-block content beyond what the spec's Assumptions
  probed (`driver_identity` strips SEED blocks; the required-policy
  `fragment_hash` covers spec-oracle fragments only, which stay deterministic).
- ✅ The pre-047 `templates/oracle.sh.template` is captured as a test fixture —
  the baseline for AC5–AC7.

**Acceptance Criteria:**

1. **Judged installers declare their kind.** After `design_eval.py install`,
   `content_fidelity.py install` and `eval_authoring.py install`, the
   component's SEED block in `oracle.sh` declares it `judged` and names the
   directory holding its frozen `config.json` (the three installers use
   different layouts: `.servo/design-eval/`, `.servo/content-fidelity/`,
   `.servo/<component>/`). Scaffold-init's
   deterministic fragments (`templates/components/*.sh.fragment`) and
   spec-oracle overlays declare nothing, and a component with no declaration is
   `deterministic`. Observable: `oracle.sh` fixtures after each install, plus a
   probe that prints each component's kind.
2. **Deterministic components run first.** A newly scaffolded `oracle.sh` with
   two or more components scores every deterministic component before any
   judged one, whatever the `COMPONENTS` order. Observable: a fixture whose
   score functions append their names to a trace file, with the judged
   component listed first in `COMPONENTS`; the trace lists the deterministic
   names first.
3. **An unavailable deterministic component decides the run.** A deterministic
   component returns rc 2: the oracle exits 2, no judged `score_<name>` is
   called (trace), the existing `oracle: missing components:` stderr line names
   only the deterministic component(s), and a second line reads
   `oracle: skipped components: <names> reason=deterministic_unavailable`.
4. **A quality ceiling below threshold decides the run.** With deterministic
   scores such that the weighted average with every judged component at 1.0,
   rounded to four decimals as the composite is, falls below `THRESHOLD`: the
   oracle exits 1, calls no judged component, prints
   `oracle: composite=<lower bound> threshold=<T>` (skipped components count 0
   and keep their weight in the denominator), and writes
   `oracle: skipped components: <names> reason=quality_ceiling_below_threshold`
   to stderr.
5. **Exit-code equivalence (property test).** Over a generated matrix — one to
   four deterministic and one to three judged components; scores in [0, 1]
   including 0, 1 and values either side of `THRESHOLD`; weights ≥ 0 including
   0; rc-2 injections; `THRESHOLD` from 0 to 1 — the new oracle's exit code
   equals the pre-047 template's on the same inputs, it never exits 0 after
   skipping anything, and every run it does not skip prints the same stdout as
   the pre-047 template.
6. **Unaffected oracles stay byte-identical.** A single-component oracle, an
   all-deterministic oracle, an all-judged oracle, and an oracle whose judged
   components carry no declaration produce the same stdout, stderr and exit code
   as the pre-047 template.
7. **Existing installs keep working; nothing is re-frozen.** (a) An `oracle.sh`
   rendered from the pre-047 template, and one rendered from the new template,
   both pass `oracle_overlay`'s canonical-driver check
   (`oracle_overlay.py:338-357`). (b) Re-installing an already-frozen
   design-eval, content-fidelity or eval-authoring component adds the
   declaration and leaves its frozen `config.json` valid: `validate_freeze`
   passes with no stale refusal.
8. **Docs.** The template's header comment and `docs/architecture.md` describe
   kinds, run order, the skip rule and the lower-bound composite; the "Adding a
   component" convention explains how a custom judged component declares itself.
   Surface-tested.

**DoD:**
- [ ] All ACs pass; full test suite green (no regressions).
- [ ] Implementer test coverage exercises each AC with at least one
      fixture. Edge cases listed in the slice are covered explicitly.
- [ ] Each new test has been shown to fail when its feature is removed —
      the test is capable of failing, not vacuously green (mutate the
      feature, watch the test go red, restore). In particular, dropping the
      ceiling rounding reds an AC5 boundary case.
- [ ] `scripts/shellcheck.sh` clean on the template; host packages rebuilt and
      drift-clean (`scripts/build_host_packages.py --check`); Python 3.9 floor
      respected (ADR-0020).
- [ ] Reviewed by `reviewer` subagent. Reviewer prompt built by
      `review.py`.
- [ ] Implementation review passed (compliance + craft + arch).
- [ ] Deviation log produced under this slice heading.
- [ ] Reconciliation sweep produced under this slice heading.
- [ ] Reconciliation review passed.
- [ ] `docs/refinement-todo.md` updated if any decisions were
      deferred during implementation.

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

**Anti-horizontal-phasing check:** After this slice, a scaffolded target with a
test suite and a frozen design-fidelity eval whose tests are failing gets the
same `below_threshold` (or `env_error`) result it gets today, without waiting
for a screenshot-and-judge cycle, and its oracle stderr names what was skipped
and why.

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
