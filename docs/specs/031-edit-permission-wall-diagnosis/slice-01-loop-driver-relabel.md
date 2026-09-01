---
status: DONE
dependencies: [adr-0037]
last_verified: 2026-09-01
arch_review: true
---

<!-- jig grounding (spec 064-02 / ADR-0020): factual claims about loop.py are
     probe-grounded in spec.md "Current state (verified)"; ACs below cite the
     seams they touch. -->

## Slice 031-01 — loop-driver-relabel

**Goal:** For the **loop driver** (`run_loop`), diagnose a headless
edit-permission wall: track whether the runner ever landed a change (an
untracked-inclusive per-runner-iteration disk delta, persisted resume-safe as
`runner_ever_edited`), and at the halt the existing brakes already produce,
relabel the terminal reason to `edit_permission_unavailable` (rc=2) with a fix
breadcrumb when the runner never edited while the oracle is below threshold —
never firing earlier than today, so a capable run (including one that only
*creates* files) is never mislabeled.

**DoR:**
- ✅ [ADR-0037](../../decisions/adr-0037-agent-loop-permission-preflight.md)
  Accepted (2026-09-01).
- ✅ Loop-driver seams grounded in `spec.md` "Current state (verified)"
  (`_agent_for_iteration`:444, `_invoke_claude`:2150-2170, plateau `break`
  region:2328-2340, `_dirty_tree_paths`:1460/1472/1485, resume:2037-2099).

**Acceptance Criteria:**

1. **A new terminal reason `edit_permission_unavailable` exists and exits
   `rc=2`.** A `REASON_EDIT_PERMISSION_UNAVAILABLE = "edit_permission_unavailable"`
   constant is added; when the relabel fires, `run_loop`'s terminal reason is set
   to it and the process exits `2` (the existing fail-closed env-error code —
   asserted distinct from a clean `oracle_plateau`/`max_iterations_reached` exit).

2. **The disk-delta signal counts created (untracked) files and is per-invoke.**
   A helper computes whether the target's git tree changed across a single runner
   invoke — snapshot immediately before `_invoke_claude` and immediately after,
   **including untracked new files** (unlike `_dirty_tree_paths`, which skips
   `??`, `loop.py:1485`). Tested: a fixture where the runner's only change is
   creating a new untracked file reports "landed a change" (a *delta*, so a
   pre-existing dirty tree from `--allow-dirty`/`--resume` does not read as this
   iteration's change).

3. **`runner_ever_edited` arms on the first runner edit and is persisted.** The
   run state carries a `runner_ever_edited` boolean (default false); the first
   runner iteration whose delta is non-empty sets it true, permanently for the
   run. It is written into the checkpoint state file so a `--resume` reload
   (which today rebuilds only from `oracle_score_history`/`iteration_count`,
   `loop.py:2095-2099`) restores it. Tested: a run that edits at iteration 1 then
   is resumed shows `runner_ever_edited=true` after reload.

4. **Judge iterations never arm or count.** The signal is recorded on **runner**
   iterations only (`_agent_for_iteration` odd), never judge iterations (even,
   read-only by contract). Tested: a run where only judge iterations execute
   (or where the judge's turn is the one inspected) does not arm the flag and
   does not itself trigger the relabel.

5. **The relabel fires at the existing halt, conjoined with oracle-below-threshold.**
   When `run_loop` halts via `REASON_ORACLE_PLATEAU` or
   `REASON_MAX_ITERATIONS_REACHED` **and** `runner_ever_edited` is false **and**
   the final oracle status is below threshold (not a pass), the terminal reason
   is relabeled to `edit_permission_unavailable`. It does **not** relabel a halt
   whose oracle passed. Tested for both plateau and max-iterations halts.

6. **A capable run is never mislabeled.** When `runner_ever_edited` is true (the
   runner edited at least once), a subsequent `oracle_plateau` /
   `max_iterations_reached` halt keeps its original reason — the edit proves
   permission. Tested: a run that edits then plateaus halts as `oracle_plateau`,
   not `edit_permission_unavailable`.

7. **No false-arm from bookkeeping.** The delta snapshot brackets the runner
   invoke only; changes made by the subsequent `gate.py` call or `loop.py`'s own
   `.servo/` state write, and untracked bookkeeping artifacts (`__pycache__`,
   coverage, `.servo/`), must **not** arm `runner_ever_edited`. Tested
   (disarm-direction fixture): a walled runner whose only on-disk residue is
   gate/`.servo`/cache bookkeeping leaves the flag false and the halt is
   relabeled.

8. **The relabel carries an actionable breadcrumb.** The terminal output / state
   for `edit_permission_unavailable` includes a fix hint naming the grant to add
   (a worktree `.claude/settings.local.json` permission grant, or a Routine with
   Bash + Edit/Write granted, per 003-08). Tested: the breadcrumb string is
   present in the run's terminal record.

9. **Non-git targets fall back safely.** When the delta cannot be computed
   (non-git target — `_dirty_tree_paths`-style `None`, `loop.py:1472`), the flag
   stays unarmed-but-unusable and the loop keeps today's terminal reason
   (`oracle_plateau` / `max_iterations_reached`) rather than crashing or
   false-relabeling. Tested with a non-git target fixture.

**DoD:**
- [x] All ACs pass; full `test_loop.py` suite green (359 passed).
- [x] `ruff check .` clean (pinned `ruff==0.15.17`, line-length 100).
- [x] Fail-closed / guard branches mutation-checked: all six guards
      (oracle-below-threshold conjunct AC5, disarm-on-edit AC6, untracked
      inclusion AC2, judge exclusion AC4, plus the `edit_signal_computed` gate
      and the before/after-invoke bracket added in reconciliation) each turn a
      test red when neutered — proven load-bearing.
- [x] Host packages rebuilt + drift clean (`build_host_packages.py --check`
      in sync; all three `loop.py` copies carry the change).
- [x] Independent review (compliance + craft + arch) passed; deviation log +
      reconciliation sweep produced and reconciliation review passed.

**Anti-horizontal-phasing check:** After this slice, a real walled loop-driver
run (headless `Edit` denied) halts with `edit_permission_unavailable` and a fix
breadcrumb end-to-end — the operator sees the correct diagnosis, not
`oracle_plateau` — while a capable run, including a file-creating one, is
unaffected.

### Deviation log (after reconciliation)

Original ACs above are preserved; this records what changed during
implementation and reconciliation.

**Implementation judgment calls (within the ACs):**
- **Signal mechanism** — the disk delta is a set-difference of `git status
  --porcelain` lines (default untracked mode, matching `_dirty_tree_paths` for
  consistency), computed by a new `_tree_snapshot(target)` (returns `None` for a
  non-git target OR any `git status` error). Servo/tooling bookkeeping is
  filtered inside the snapshot (`.servo/`, `__pycache__`, `*.pyc`, coverage, and
  same-class `.pytest_cache`/`.mypy_cache`/`.ruff_cache`/`.git`).
- **AC5 conjunct narrowed to `== STATUS_BELOW_THRESHOLD`** (not `!= STATUS_PASS`).
  This additionally excludes an `env_error` final halt from relabeling — a
  broken-gate halt is a different diagnosis than a permission wall. Defensible
  tightening consistent with AC5's literal "below threshold (not a pass)";
  flagged and accepted by all three reviewers.
- **State fields are additive, no `state_schema_version` bump** —
  `runner_ever_edited`, `edit_signal_computed`, `terminal_breadcrumb` each default
  safely (`False`/absent) with resume `setdefault` backfill, per ADR-0004's
  additive clause (old state files still resume).
- **rc=2 on a relabeled halt** — `edit_permission_unavailable` returns
  `EXIT_ENV_ERROR` (first case of a *fully-executed* `run_loop` returning rc=2),
  giving AC1's "distinct from a clean plateau/max-iterations exit." Breadcrumb
  surfaced in three places (summary JSON `terminal_breadcrumb` — added
  *conditionally* so other halt lines keep byte-identical shape; `state`; stderr).

**Review nits folded in during reconciliation (all non-blocking; addressed, not deferred):**
1. **Signal-availability unification** (converged across compliance + craft +
   arch). The relabel guard previously re-derived `edit_signal_available =
   _is_git_work_tree(target)` (rev-parse only), which could disagree with the
   arm path (`_tree_snapshot`, `None` also on a transient `git status` error) and
   mislabel a capable run on a healthy tree whose `git status` transiently
   failed. Fixed by threading a persisted `edit_signal_computed` flag (set True
   whenever a runner-iteration snapshot is computable) and feeding *that* to the
   guard — the two notions now match. New test
   `test_persistent_git_status_error_no_relabel` (fake `git`: `rev-parse`→true,
   `status`→exit 1) → no relabel; mutation-checked (guard e).
2. **AC7 bracket-timing test** (craft). The before/after-invoke bracket was
   previously unproven (both AC7 fixtures left only bookkeeping residue the
   filter catches regardless of timing). New test
   `test_gate_residue_after_invoke_does_not_arm`: a below-threshold oracle that
   writes a **non-bookkeeping** file during the gate call → `runner_ever_edited`
   stays False and the run is relabeled, proving `snapshot_after` (taken before
   the gate) is load-bearing. Verified by a temporary relocation of the arm block
   below the gate → test goes RED (mutation-check f).
3. **Type hints** (craft) — `Optional[set]`/`set` → `Optional[set[str]]`/`set[str]`.

**Accepted residual (no code change, per ADR-0037's stated blind-spot):** a
runner whose only edits land in `.gitignore`d paths would not arm the flag —
same already-failing-run-bounded class as the ADR's named residuals. Worth a
one-line note if 031-02 reuses these helpers.

### Reconciliation sweep

- **`docs/architecture.md`** — **updated**: added the three new `state.json`
  fields, a paragraph describing the edit-permission-wall relabel (ADR-0037 /
  spec 031), and the conditional `terminal_breadcrumb` on the summary line.
- **Host packages** (`hosts/claude/...`, `hosts/codex/...`) — **updated**:
  regenerated via `build_host_packages.py`; `--check` clean (all three `loop.py`
  copies carry the change).
- **`docs/refinement-todo.md`** — **updated**: recorded the rc=2-on-completed-run
  downstream re-check (heartbeat dispatch / exit-code consumers) for when 031-02
  lands.
- **ADRs** — **no-op**: ADR-0037 already documents the full contract; this slice
  changes no decision and adds no rejected-alternative choice.
- **`docs/inbox.md`** — **no-op**: servo has no inbox file; nothing to triage.
- **Glossary / memory** — **deferred** to the spec-close memory-sync (031-02 is
  the last live slice); terms (`edit_permission_unavailable`, `runner_ever_edited`)
  are self-describing in architecture.md.
- **Downstream exit-code consumers** — **deferred** to 031-02 (tracked in
  refinement-todo): the new rc=2-on-fully-executed-run should be re-checked
  against heartbeat dispatch before the goal-driver relabel lands.
