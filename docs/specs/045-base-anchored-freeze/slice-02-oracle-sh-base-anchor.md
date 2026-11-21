---
status: DRAFT
dependencies: [045-01, adr-0051, adr-0002, adr-0004]
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

## Slice 045-02 — oracle-sh-base-anchor

**Goal:** Unattended scoring refuses when the working tree's `oracle.sh` differs
from its base copy, so a run cannot change the threshold default, the component
weights or list, or the spliced score functions (including the
`--enforce-freeze` flag 045-01 relies on) that judge it. Attended `gate.py` runs
are unchanged: the developer owns `oracle.sh` (`docs/product-vision.md:176`).

**Context (probed):** on the ordinary path, nothing pins `oracle.sh`. The
`THRESHOLD` default (`templates/oracle.sh.template:25`) and `COMPONENTS` weights
(`:28-30`) are plain text; the loop checks only that the file exists
(`skills/agent-loop/loop.py:1872`) and that the tree is clean at start
(`loop.py:4447`). Required-policy mode does pin `oracle.sh` and the threshold
default (`skills/quality-gate/required_runtime.py:480-482`, `:740-745`); this
slice gives the ordinary path a base-anchored equivalent and leaves required
mode's pins as they are.

**DoR:**
- ⬜ 045-01 DONE (the anchor resolver exists and is loadable from `gate.py`'s
  portable closure).
- ⬜ [ADR-0051](../../decisions/adr-0051-base-anchored-freeze.md) Accepted
  (constraint 5: anchoring applies to unattended scoring only).

**Acceptance Criteria:**

1. **Anchored gate refuses a modified oracle.** `gate.py <target>
   --freeze-anchor base` resolves the anchor with 045-01's resolver (one
   implementation). When the base has a copy of `oracle.sh` and the working
   tree's bytes differ, the gate exits 2 with `status: env_error`,
   `reason: oracle_modified_vs_base`, without running the oracle; the message
   names the base commit and suggests `git diff <sha> -- oracle.sh`.
2. **Matching oracle scores as today, with the anchor recorded.** When the bytes
   match, the oracle runs unchanged and the JSON payload (v1 and v2) adds
   `freeze_anchor`. This is an additive field under ADR-0002 clause 2;
   `schema_version` stays 1, and absent means unanchored.
3. **Explicit fallback.** With no anchor, or no `oracle.sh` at the anchor, the
   oracle runs, the payload carries `freeze_anchor: {kind: "worktree", reason}`,
   and stderr carries one line saying so.
4. **Unattended callers ask for the anchor.** `loop.py`'s `_invoke_gate`
   (`loop.py:3776`, both drivers: `:4866`, `:5644`), heartbeat's
   `_run_gate_json` (`skills/heartbeat/heartbeat.py:1707`, which campaign's
   advisory re-check reuses) and the meta-judge script
   (`templates/meta-judge.sh.template:55`) pass `--freeze-anchor base`.
   `loop.py --freeze-base <ref>` exports `SERVO_FREEZE_BASE` to the gate and
   records `freeze_anchor` in `state.json` (additive under ADR-0004). Fixture: a
   loop whose runner lowers the `THRESHOLD` default in `oracle.sh` halts on an
   `oracle_modified_vs_base` env-error instead of recording a pass. In the
   meta-judge, the refusal fails open like every gate env-error there
   (`skills/oracle-hook/SKILL.md:71`).
5. **Attended default unchanged.** `gate.py <target>` without the flag produces
   the same payload and exit code as today and makes no git call.
6. **Threshold source is visible.** When anchored, the payload records
   `threshold_source: "oracle_default" | "environment"`, so a pass reached
   through a caller's `THRESHOLD=` environment override can be told apart. The
   override itself is the caller's decision and outside the anchor; required
   mode already records it as `threshold_override`
   (`required_runtime.py:736-737`).
7. **Docs.** `docs/architecture.md` (the quality-gate JSON contract and the
   agent-loop guardrails table) documents `--freeze-anchor`,
   `oracle_modified_vs_base`, `freeze_anchor` and `threshold_source`; the
   threat-model paragraph drops the "until 045-02" residual.

**DoD:**
- [ ] All ACs pass; full test suite green (no regressions).
- [ ] Implementer test coverage exercises each AC with at least one
      fixture. Edge cases listed in the slice are covered explicitly.
- [ ] Each new test has been shown to fail when its feature is removed —
      the test is capable of failing, not vacuously green (mutate the
      feature, watch the test go red, restore).
- [ ] Host packages regenerated (`build_host_packages.py`) and `--check`
      clean, since `gate.py`, `loop.py` and the meta-judge template ship in
      every host copy.
- [ ] Reviewed by `reviewer` subagent. Reviewer prompt built by
      `review.py`.
- [ ] Implementation review passed.
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
      the spec's Active-specs entry. If the spec is still in flight, leave
      the entry.

**Anti-horizontal-phasing check:** After this slice, an unattended loop that
edits its own `oracle.sh` — to lower the bar, re-weight a component, or drop the
freeze flag — stops with a named refusal instead of passing, and every gate
payload says which oracle it trusted.

### Deviation log (after reconciliation)

The original spec is preserved above. Implementation notes:

_Filled at reconciliation._

### Reconciliation sweep

_Filled at reconciliation (artifact / disposition / rationale table)._
