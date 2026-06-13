---
status: DONE
dependencies: [003-06, 003-07, adr-0008]
last_verified: 2026-06-13
---

## Slice 003-08 — detach-and-schedule

**STATUS: DONE**

> ADR-0008 rebase phase, slice 3 of 3. The unattended surface: detached +
> scheduled runs on the autonomy primitives.

**Goal:** Support running the guardrailed loop **unattended** — detached
(`/background`) and scheduled (Routines) — with `gate.py` as the in-Routine
authority. ADR-0008 V4 found a Routine executes the task as a single continuous
agent invocation, so the meta-judge `Stop` hook is **moot** there; the
deterministic authority is the loop-body `gate.py` + the final `gate.py` run
(003-06 AC4). This slice makes a servo target **Routine-ready** and documents the
execution contract; it does **not** create Routines (they're a web/desktop
product, not a CLI subcommand — ADR-0008 V4 discovery).

End-to-end value: a user can point a scheduled Routine (or a detached background
run) at a servo target and get a guardrailed, oracle-authoritative loop with no
human attached.

**DoR:**
- ✅ [ADR-0008](../../decisions/adr-0008-loop-on-autonomy-primitives.md) Accepted; 003-06 + 003-07 exist.
- ✅ V4: Routines run as one continuous invocation → meta-judge moot →
  `gate.py` is the in-Routine authority. Reference shapes:
  `adr-0008-experiments/v4_clean_clone_sim.sh` + `make_v4_routine_target.sh`.
- ✅ Discovery: Routines are created via web/desktop, not the `claude` CLI
  (no `routine`/`schedule` subcommand in 2.1.175).
- ⏳ Verify at implementation: exact headless detachment mechanics (`/background`
  in `-p` vs a documented background-process pattern) — see Open question.

**Acceptance Criteria:**

1. **Detached run mode.** `loop.py --driver goal --background <target>` launches
   the run detached so a long unattended run survives terminal detach, using
   `/background` where the host supports it; the run-id + `state.json` let the
   user reattach/inspect. Bounded by 003-06's hard caps regardless.
2. **Routine-ready target.** The driver (or a `servo:scaffold-init` extension)
   produces a Routine-ready target: vendored `gate.py` (003-07) + a standard
   Routine prompt (loop body runs `servo:quality-gate`, prints the sentinel,
   under a `/goal` condition). `adr-0008-experiments/make_v4_routine_target.sh`
   is the reference generator; a test asserts the produced shape.
3. **`gate.py`-authority execution contract.** Documented + enforced: in a
   Routine / continuous-invocation context the final `gate.py` run is the
   verdict; the run does **not** depend on the meta-judge `Stop` hook firing (it
   may not — V4). The contract is recorded in `SKILL.md` + `docs/architecture.md`.
4. **Clean baseline per scheduled run.** A scheduled rerun starts from a clean
   committed baseline — the 003-07 `refuse-on-dirty-tree` guard plus a documented
   `git reset --hard` / fresh-clone expectation — so successive triggers don't
   inherit state (V4 pollution finding).
5. **Host-scope matrix documented.** `docs/architecture.md` carries the full
   execution matrix: CC interactive → meta-judge backstop (spec 004); CC headless
   `-p` → goal-driver + outer caps (003-06); Routine / continuous → `gate.py`
   authority (this slice); hook-restricted / non-Claude host (e.g. Codex) →
   external `loop.py` driver (003-01..05, retained). 

**DoD:**
- [x] All ACs pass; full suite green (888 passed / 1 skipped; `test_loop.py` +
      `test_skill_surface.py` 287 passed; ruff clean).
- [x] Per-AC coverage; the V4 clean-clone sim + dummy Routine target serve as the
      executable reference (a test asserts the Routine prompt + vendored shape).
- [x] `SKILL.md` documents `--background` + the Routine-ready / scheduled run
      modes + the `gate.py`-authority contract.
- [x] `docs/architecture.md` execution matrix added (AC5).
- [x] Reviewed by `jig:reviewer` (compliance + craft, both PASS — see
      `reviews/slice-08-{compliance,craft}.md`); deviation log produced below.
- [x] **Closes the ADR-0008 rebase phase** — spec 003 returns to DONE once
      003-06..08 are DONE; the README skills table + status board reflect it.

**Open question (RESOLVED at implementation):** does `/goal` + `/background`
compose in headless `-p`, or is detachment better served by a background-process
pattern around the goal-driver? **Resolved → background-process pattern.** Probed
`claude --help` on 2.1.175: there is **no headless `--background` flag**;
`/background` (alias `/bg`) is an **interactive agent-view** action that detaches a
TUI session — meaningless for a one-shot `claude -p` subprocess. So `--background`
detaches at the **OS level** (`subprocess.Popen(..., start_new_session=True)` =
POSIX setsid), re-execing the goal driver in a new session; the run-id + `state.json`
(003-04) are the inspect/await surface. The remaining ADR-0008 V4 "remote Routine
mechanics" check (`v4_routines_probe.md`) stays a non-blocking follow-up.

**Anti-horizontal-phasing check:** After this slice a scheduled/detached run is a
real user-facing capability — point a Routine at a servo target and it runs the
guardrailed, oracle-authoritative loop unattended. End-to-end value.

### Deviation log (after reconciliation)

Implemented in `skills/agent-loop/loop.py` (new: `_emit_routine_prompt`,
`_build_detached_child_argv`, `_spawn_detached`, `_detach_summary`,
`run_goal_loop_background`; `run_goal_loop` gained `run_id` + `detached` injection;
`_compose_goal_prompt` gained a `python` param; `main()` wires `--background` /
`--emit-routine-prompt` / the internal `--_detached-run-id`), with per-AC tests in
`test_loop.py` (`BackgroundArgvUnitTests`, `BackgroundDispatchTests`,
`BackgroundFlagConflictTests`, `EmitRoutinePromptTests`) + doc-surface tests in
`test_skill_surface.py` (`Slice003_08SurfaceTests`), and docs in `SKILL.md` +
`docs/architecture.md`. All five ACs met; full project suite **888 passed / 1
skipped**; `test_loop.py` + `test_skill_surface.py` **287 passed**; ruff clean.
Reviewed by `jig:reviewer` — compliance + craft both **PASS**
(`reviews/slice-08-*.md`).

Deviations and decisions worth recording:

1. **Open question resolved → OS-level background-process pattern (not `/background`).**
   `claude -p` exposes **no headless `--background` flag** (probed on 2.1.175);
   `/background` is an *interactive* agent-view action. So `--background` detaches via
   `subprocess.Popen(..., start_new_session=True)` (POSIX setsid), re-execing the goal
   driver in a new OS session with output → `<run-dir>/background.log`. `/background` is
   documented as the interactive analog. This is the genuine resolution of the slice's
   flagged open question; the V4 "remote Routine mechanics" check stays non-blocking.
2. **`--background` requires the goal driver — refuses, doesn't downgrade (vs AC1's
   literal "using `/background` where the host supports it").** Background routes as
   `--driver goal`; on a host that can't run `/goal` it refuses (`goal_unavailable`)
   rather than silently downgrading to a non-detachable loop run, and `--driver loop
   --background` is rejected at argparse. The OS-level detach itself is driver-agnostic,
   but a backgrounded run that can't carry the `/goal` continuation contract shouldn't
   masquerade as one. Documented in `SKILL.md` + the `main()` `parser.error`.
3. **Parent-allocated run-id, injected into the detached child.** The parent runs the
   visible synchronous preflight (target / **dirty-tree** (AC4) / vendor), pre-allocates
   the run-id + seeds `state.json` so the run-id it prints is usable immediately, then
   re-execs the child with the internal `--_detached-run-id` so both processes share one
   run dir. The child carries `--allow-dirty` (the parent is the single dirty-tree gate)
   and short-circuits routing (the parent already verified host support). Intentional
   belt-and-suspenders: the child re-runs (idempotent) vendor + its own `run_goal_loop`,
   logging `goal_unavailable` as defense-in-depth if the host changed.
4. **`--emit-routine-prompt` emits a *portable* gate command.** The Routine runs in a
   cloud clone, so the emitted prompt uses `python3 .claude/skills/servo-quality-gate/
   gate.py . --json` (bare `python3` + the relative vendored path), not this host's
   absolute `sys.executable`. `_compose_goal_prompt` gained a `python` param for this;
   live goal runs still pin `sys.executable` (unchanged). A test asserts no absolute
   interpreter leaks and that the emitted prompt can't self-satisfy the pass predicate.
5. **New closed-set reasons / summary shapes.** `detached` (parent's provisional
   terminal reason — the run continues in the child; rc=0) and `detach_failed`
   (fail-closed when the child can't be spawned; rc=2). The detach summary is a distinct
   shape (`detached: true` + `pid` + `state_path`/`log_path`); the state file carries
   `detached: true`. `state_schema_version` stays **1** (the `detached` key is additive
   per ADR-0004).
6. **Craft nits addressed inline** (both `[nit]`, non-blocking): added a
   `BACKGROUND_LOG_NAME` constant (was a bare `"background.log"` literal, vs the
   `STATE_FILE_NAME` convention); added a docstring note to `run_goal_loop_background`
   that `/goal` host-eligibility is the **caller's** precondition (verified by `main()`
   routing before the call).
7. **No ADR / architecture-boundary change.** ADR-0008 already governs; `arch_review`
   and `code_health_review` both probe `false` (a new CLI surface + an OS-detach helper,
   not a module-boundary or contract shift — consistent with 003-07). `docs/architecture.md`
   gained the **execution matrix by host** (AC5) + a `background.log` artifact note, but
   that documents the *existing* ADR-0008 decision, not a new one. The `gate.py` `0/1/2`
   contract (ADR-0002) and `oracle.sh`'s authority are unchanged. No `TODO`/`FIXME`
   introduced; no `docs/conventions.md` rule added.
