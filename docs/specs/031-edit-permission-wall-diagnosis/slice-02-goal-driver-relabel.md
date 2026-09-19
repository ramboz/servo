---
status: DONE
dependencies: [031-01]
last_verified: 2026-09-01
---

## Slice 031-02 — goal-driver-relabel

**Goal:** Extend the edit-permission-wall diagnosis to the **goal driver**
(`run_goal_loop`): compute a whole-run disk delta around its single
`_invoke_claude_goal` invocation and, at the goal driver's terminal, relabel
`iteration_cap_reached` / `oracle_below_threshold` to `edit_permission_unavailable`
(rc=2) with the same fix breadcrumb when nothing landed and the oracle is red.

**DoR:**
- ✅ 031-01 DONE (shares the disk-delta helper, the
  `REASON_EDIT_PERMISSION_UNAVAILABLE` constant, and the breadcrumb string).
- ✅ Goal-driver seams grounded in `spec.md`: `run_goal_loop`:2595,
  `_invoke_claude_goal`:2447, terminal reasons at `loop.py:2844`
  (`REASON_ITERATION_CAP_REACHED`) / `loop.py:2856`
  (`REASON_ORACLE_BELOW_THRESHOLD`).

**Acceptance Criteria:**

1. **Whole-run delta around the goal invoke.** The goal driver has no
   per-iteration checkpoint, so the disk-delta is computed once — snapshot before
   `_invoke_claude_goal` vs. after — reusing 031-01's untracked-inclusive delta
   helper. A goal run that lands any change (including a created file) is recorded
   as "edited"; one that lands nothing is not.

2. **Relabel at the goal terminal, conjoined with oracle-below-threshold.** When
   `run_goal_loop` reaches `REASON_ITERATION_CAP_REACHED` (`loop.py:2844`) or
   `REASON_ORACLE_BELOW_THRESHOLD` (`loop.py:2856`) **and** nothing landed on
   disk **and** the oracle is below threshold, the terminal reason is relabeled to
   `edit_permission_unavailable` (rc=2) with the breadcrumb. A goal run whose
   oracle passed is never relabeled. Tested for both terminal reasons.

3. **A capable goal run is never mislabeled.** A goal run that lands any change
   keeps its original terminal reason. Tested.

4. **No false-arm from bookkeeping / non-git fallback.** As in 031-01: gate /
   `.servo/` / cache residue must not count as "edited," and a non-git target
   falls back to today's terminal reason rather than crashing or false-relabeling.
   Tested.

**DoD:**
- [x] All ACs pass; full `test_loop.py` suite green (370 passed).
- [x] `ruff check .` clean (pinned `ruff==0.15.17`).
- [x] Guard branches mutation-checked: oracle-below-threshold conjunct,
      `runner_ever_edited` (nothing-landed), and the goal-reason generalization
      each turn a test red when neutered (executed by the orchestrator after the
      implementer's mid-check interruption; see deviation log).
- [x] Shared helpers reused from 031-01 — one `_relabel_terminal_reason` serves
      both drivers (generalized, not forked); `_tree_snapshot` + breadcrumb reused;
      only the ~7-line exit-code wiring inline-mirrored.
- [x] Host packages rebuilt + drift clean (both host `loop.py` copies carry the
      goal block + unified key; `--check` clean).
- [x] Independent review (compliance + craft) passed; deviation log +
      reconciliation sweep produced and reconciliation review passed.

**Anti-horizontal-phasing check:** After this slice, a walled **goal-driver** run
also halts with `edit_permission_unavailable` and the fix breadcrumb, closing the
diagnosis hole for both drivers ADR-0037 names.

### Deviation log (after reconciliation)

**Implementation (within the ACs):**
- **Whole-run delta** — `_tree_snapshot` snapshotted once before/after
  `_invoke_claude_goal` (loop.py:2989/3002), before the authoritative
  `_invoke_gate`, reusing 031-01's untracked-inclusive, bookkeeping-filtered
  helper. The goal driver does not resume, so the flags ride local vars +
  forensic state, not a resume checkpoint.
- **One shared decision helper** — `_relabel_terminal_reason` was generalized to
  recognize the goal terminals (`REASON_ITERATION_CAP_REACHED`,
  `REASON_ORACLE_BELOW_THRESHOLD`) alongside the loop halts, so BOTH drivers use
  one pure helper (no fork); only the ~7-line exit-code wiring is inline-mirrored
  (justified by the drivers' different exit mechanisms).
- **Cost-ceiling halts are deliberately never relabeled** — the helper's eligible
  set excludes `REASON_COST_CEILING_REACHED` (goal subtype `error_max_budget`):
  running out of budget is not a permission wall. Matches AC2's scope and
  031-01's exclusion. Recorded per the compliance reviewer's note.

**Recovery from an interrupted implementer (honest record):** the implementer
subagent was cut off by an API error (host sleep) *mid-mutation-check*, leaving an
un-restored neutering of the oracle-below-threshold conjunct in `loop.py`
(`if False and final_oracle_status != STATUS_BELOW_THRESHOLD:`). The orchestrator
caught it via the full-suite run (3 failures, all the oracle-status-conjunct
tests), restored the line, scanned for any other residue (none), and **re-executed
all guard mutation checks** to completion: guard (a) oracle-below-threshold
(proven load-bearing by the accidental cutoff itself — its 3 tests went red), (b)
`runner_ever_edited` (neutered → 4 capable-run tests red, loop + goal), and the
goal-reason generalization (removed from the eligible set → 2 goal-relabel tests
red). All restored; `loop.py` verified residue-free; full suite green (370).

**Review nits folded in during reconciliation (all non-blocking):**
- **Cross-driver state-key unification** (craft) — the goal driver persisted its
  landed-a-change flag as `ever_edited`; unified the **state key** to
  `runner_ever_edited` (the shipped 031-01 key + the field documented in
  `docs/architecture.md`), so a state.json consumer reads one name for one
  concept. Local var stays `ever_edited` (accurate: goal has no runner/judge
  split). Four goal-test assertions updated to the unified key.
- **Direct goal-reason unit cases** (compliance) — added
  `test_iteration_cap_below_unarmed_git_relabels` +
  `test_oracle_below_threshold_reason_unarmed_git_relabels` to
  `RelabelDecisionUnitTests` (previously the goal reasons were covered only
  end-to-end); fixed that class's now-stale "only two brakes eligible" comment.
- **Test symmetry** (craft) — added the sibling's
  `assertNotIn("terminal_breadcrumb", summary)` to
  `test_created_file_keeps_iteration_cap_reached`.

### Reconciliation sweep

- **`docs/architecture.md`** — **updated**: the edit-permission-wall paragraph now
  states both drivers are covered (one shared helper), the cost-ceiling exclusion,
  and the heartbeat-dispatch non-interaction.
- **`docs/refinement-todo.md`** — **updated (resolved)**: the rc=2-downstream item
  filed in 031-01 is marked RESOLVED with the dispatch audit — no classification
  regression (dispatch keys passed/tried on `final_oracle_status`, unchanged; a
  walled run writes a parseable summary so it is not env-error'd); the only change
  is that a walled run no longer trips the plateau→quarantine string-match, which
  is correct.
- **Host packages** — **updated**: regenerated; both host `loop.py` copies carry
  the goal-relabel block + the unified key; `--check` clean.
- **ADRs** — **no-op**: within ADR-0037's accepted scope (it names both drivers);
  no new decision.
- **`docs/inbox.md`** — **no-op**: servo has no inbox file.
- **Spec-close primer hygiene** — 031-02 closes the live scope of spec 031
  (031-03 stays DEFERRED); the spec rolls up to DONE. No per-slice invariant needs
  migrating to a primer (the contract lives in `architecture.md` + ADR-0037).
- **Memory-sync** — the new terms are self-describing in `architecture.md`; a
  session-level memory note records the ADR-0037 build + the interrupted-implementer
  recovery lesson.
