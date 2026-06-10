---
status: DONE
dependencies: []
last_verified:
---

## Slice 001-04 — deferred-decisions

**Goal:** When the scaffolder can't infer a tailoring decision (weights when multiple signals are present, threshold tuning, signals it detected but couldn't classify, project-specific custom signals), it records the open question in `<target>/.servo/refinement-todo.md` with a resolution trigger — mirroring jig's deferred-decisions slice. End-to-end value: the dev gets an explicit list of "things you need to tune," not silent defaults that pass review.

**DoR:**
- ✅ Slice 001-03 DONE
- ✅ Decision categories agreed: weights, threshold, ambiguous signals, custom signals
- ✅ Refinement-todo format mirrors jig's (heading per decision, "Deferred:" reason, "Resolution trigger:" line)

**Acceptance Criteria:**

1. **Multi-signal install creates a weight-tuning todo.** When ≥2 components are detected, `<target>/.servo/refinement-todo.md` contains a `Weights` decision with "Deferred: equal weights applied — tune to reflect project priorities" and a resolution trigger.
2. **Threshold default is flagged.** Every install creates a `Threshold` decision with the chosen default and a resolution trigger ("first time oracle gate misfires").
3. **Ambiguous signals are listed.** A project with both vitest and jest configs gets an `Ambiguous test runner` decision with both names listed.
4. **Refinement-todo is idempotent.** Re-running with `--force` doesn't duplicate decisions; it rewrites the file from scratch.
5. **No spurious decisions.** A perfectly-tailorable install (one component, no ambiguity) produces a refinement-todo with only the unavoidable `Threshold` decision.

**DoD:** _(same shape)_
- [x] All ACs pass; full test suite green. _40/40 in `test_scaffold.py`, zero skips._
- [x] Test coverage per AC: AC1→`test_weights_decision_on_multi_signal`, AC2→`test_threshold_decision_*` (×2), AC3→`test_ambiguous_test_runner`, AC4→`test_force_rewrites_no_duplicate_entries`, AC5→`test_single_component_only_threshold`.
- [x] Deviation log produced under this slice heading.
- [x] Reviewer subagent review. _jig:reviewer agent, 2026-05-15 — PASS-WITH-CAVEATS. Two caveats recorded below._
- [x] Implementation review passed.
- [x] Reconciliation review passed.
- [x] `docs/refinement-todo.md` updated. _The pre-existing "Threshold default of 0.5 is arbitrary" entry was closed by this slice — the deferral is now surfaced at the target project, not in servo's dev notes._

**Anti-horizontal-phasing check:** After this slice, every install lands with an explicit `refinement-todo.md` the dev can scan in 30 seconds. The next supervised session can resolve the items via jig's normal refinement-todo flow.

### Deviation log (after reconciliation)

**Slice 001-04 — implemented 2026-05-15.** 40 tests green (up from 34). Dogfood across three flavors — multi-signal (pytest+ruff) → Threshold+Weights; single (pytest only) → Threshold only; ambiguous (vitest+jest) → Threshold+Ambiguous-test-runner with `vitest (selected)` and `jest` listed.

Deviations from spec text:

- **`DEFAULT_THRESHOLD = 0.5` is duplicated** (reviewer-noted). The constant lives in `scaffold.py` for the refinement-todo's "Deferred:" line; the template `oracle.sh.template` still carries the literal `0.5` in `THRESHOLD="${THRESHOLD:-0.5}"`. A future template default bump would silently desync from what the refinement-todo quotes back. Acceptable for this slice — the constant's docstring names the duplication explicitly, and `0.5` isn't expected to change in the near term — but a `{{THRESHOLD_DEFAULT}}` substitution marker would be a strict improvement. Tracked as a follow-up.
- **"Custom signals" category omitted** (reviewer-noted). Slice goal text names four deferred-decision categories (weights, threshold, ambiguous, custom signals); ACs only require the first three. The `# SEED:` block convention from 001-02 already surfaces the "add your own" path in the template's comment header, so a refinement-todo entry would be a pure pointer. Defensible but worth flagging — the goal wrote a check the ACs didn't cash.
- **`ambiguous_tests` is built from built-in detection only, not jig's pick** (reviewer-confirmed correct semantic). Ambiguity is a property of the project's filesystem, not the detector's preference — so when jig selects vitest but built-in also detects jest, both names land in the ambiguous list and `(selected)` marks the jig pick. Edge case: if jig picks something outside `builtin_test_frameworks`, `(selected)` could mark a name absent from the ambiguous list. Vocabulary check in `_jig_tdd_detect` makes this unreachable in practice.
- **Idempotency via `Path.write_text` (not explicit unlink)**. AC #4 is satisfied structurally — truncate-and-write can't duplicate. Also covers the "older file with stale headings" edge case (full replacement). Subtle gap: `--force` will silently overwrite user hand-edits to refinement-todo.md. Intended `--force` behavior, but worth a docs note when SKILL.md ships in 001-05.

**Open follow-ups (added to [docs/refinement-todo.md](../../refinement-todo.md)):**
1. `THRESHOLD_DEFAULT` template substitution to remove the dual source of truth.
2. Decide whether to emit a "Custom signals" category for the no-signals case (currently silent; user only sees the in-oracle "populate # SEED: blocks manually" hint).

**Reviewer verdict:** PASS-WITH-CAVEATS (independent review, jig:reviewer subagent, 2026-05-15). All 5 ACs met by behavior-driven tests; both caveats are non-blocking and now tracked.

---

