---
status: DONE
dependencies: [003-05, adr-0003]
last_verified: 2026-07-12
---

## Slice 021-01 - diff-anchored, narrow-first investigation

**Goal:** Give `agents/runner.md` and `agents/judge.md` diff-anchored,
narrow-first investigation guidance — anchor reads to the changed / oracle-
pointed files, use Glob/Grep to locate before reading, batch discovery before
reads, read focused ranges rather than whole files, and retry a failed search
with a simpler query instead of guessing paths. Refines the existing narrow-read
prose ("Read 1-3 relevant files to understand the failure shape" in runner.md;
"Use files_changed from the runner's verdict to focus your read" in judge.md)
into an explicit discipline. Advisory only — no oracle/gate change.

**DoR:**
- [x] ADR-0003 remains the governing roster/verdict contract; this slice makes
      no schema change.
- [x] The agent-prompt surface tests are identified (the tests that assert
      `runner.md`/`judge.md` content — same suite that guards the 003-05 prompts).

**Acceptance Criteria:**

1. **Runner guidance.** `agents/runner.md` instructs the runner to anchor reads
   to the changed / oracle-pointed files, locate-before-read with Glob/Grep,
   batch discovery before reads, read focused ranges, and retry a failed search
   with a simpler query — presented as a coherent block, not scattered asides.
2. **Judge guidance.** `agents/judge.md` gives the parallel guidance, extending
   its existing "focus your read on files_changed / oracle-pointed files" so the
   judge narrows the same way rather than re-reading the tree.
3. **Boundary preserved.** No change to `oracle.sh`, `gate.py`, `loop.py`, or the
   verdict-block schema; the guidance is advisory (ADR-0021 / ADR-0011 / ADR-0005).
4. **Surface tests.** The agent-prompt surface tests assert the new guidance is
   present in both files (a distinctive marker per file).

**DoD:**
- [x] All ACs met; full suite green.
- [x] Surface tests cover the runner and judge guidance.
- [x] Reviewed (compliance + craft); evidence recorded.
- [x] Deviation log + reconciliation sweep under this slice.
- [x] Host packages / vendored copies regenerated if servo ships them.

**Anti-horizontal-phasing check:** After this slice, every headless iteration's
runner and judge receive narrow-first investigation guidance — an observable
change in the prompts the loop actually dispatches, end-to-end.

### Deviation log (after reconciliation)

- **Prompt-only implementation.** Changed `agents/runner.md` and
  `agents/judge.md` only for runtime behavior; no changes to `oracle.sh`,
  `gate.py`, `loop.py`, or the verdict-block schema.
- **Craft review nits addressed before closeout.** `agents/runner.md` now names
  the last runner verdict retained in the transcript rather than the ambiguous
  "prior verdict"; prompt surface tests now assert against the extracted
  `## Investigation discipline` section instead of the full document.
- **Reconciliation review caught stale architecture prose.** The
  `docs/architecture.md` Subagents section still said runner and judge were
  placeholders. Updated it to describe the live runner/judge prompts and the
  spec 021 headless-operation hardening.
- **Dependency token normalized for jig DONE validation.** The original
  whole-spec dependency `003` was narrowed to the concrete shipped dependency
  `003-05` (runner/judge prompt + verdict parser contract), because the current
  workflow validator only recognizes slice-fragment and ADR tokens at DONE time.
- **Verification.** Focused prompt/verdict tests passed with
  `python3 -m unittest skills/agent-loop/test_loop.py -k RunnerVerdictBlockTests -k JudgeVerdictBlockTests`
  (7 tests), and the full repo suite passed with `python3 scripts/run_tests.py`
  (1529 tests).

### Reconciliation sweep

- **Agent prompts** — `updated`. `agents/runner.md` and `agents/judge.md` carry
  parallel `## Investigation discipline` blocks with diff/oracle anchoring,
  locate-before-read, batched discovery, focused ranges, and simpler-query
  retry guidance.
- **Prompt surface tests** — `updated`. `skills/agent-loop/test_loop.py` now
  checks the runner and judge investigation sections directly.
- **Verdict/oracle boundary** — `no-op`. Parser, oracle, and gate behavior are
  unchanged; ADR-0003 remains the verdict contract.
- **Architecture** — `updated`. `docs/architecture.md` no longer describes
  runner/judge as placeholders; it reflects their live verdict-block prompts and
  spec 021's headless-loop prompt hardening.
- **Host packages** — `updated`. `python3 scripts/build_host_packages.py`
  regenerated `hosts/claude/agents/*` and
  `hosts/codex/plugins/servo/agents/*`.
- **Review evidence** — `updated`. Compliance and craft verdicts are recorded
  in `docs/specs/021-headless-agent-investigation/reviews/`.
- **Dependency metadata** — `updated`. `dependencies:` now names `003-05`
  instead of whole-spec `003`, matching the actual runner/judge prompt contract
  this slice builds on and satisfying jig's DONE-time validator.
- **Status board** — `pending final regen` by this landing thread. Trigger:
  after both 021 slices close, regenerate `docs/specs/README.md` once so the
  board reflects the final spec state.
