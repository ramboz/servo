---
status: DRAFT
dependencies: [031-01]
last_verified:
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
- [ ] All ACs pass; full `test_loop.py` suite green.
- [ ] `ruff check .` clean.
- [ ] Guard branches mutation-checked (oracle-below-threshold conjunct;
      nothing-landed condition).
- [ ] Shared helpers reused from 031-01 (no duplicate delta/breadcrumb logic;
      inline-mirror budget respected).
- [ ] Host packages rebuilt + drift clean if applicable, else N/A recorded.
- [ ] Independent review (compliance + craft) passed; deviation log +
      reconciliation sweep produced.

**Anti-horizontal-phasing check:** After this slice, a walled **goal-driver** run
also halts with `edit_permission_unavailable` and the fix breadcrumb, closing the
diagnosis hole for both drivers ADR-0037 names.
