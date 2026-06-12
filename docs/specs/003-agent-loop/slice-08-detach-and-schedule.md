---
status: DRAFT
dependencies: [003-06, 003-07, adr-0008]
last_verified:
---

## Slice 003-08 — detach-and-schedule

**STATUS: DRAFT**

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
- [ ] All ACs pass; full suite green.
- [ ] Per-AC coverage; the V4 clean-clone sim + dummy Routine target serve as the
      executable reference (a test asserts the Routine prompt + vendored shape).
- [ ] `SKILL.md` documents `--background` + the Routine-ready / scheduled run
      modes + the `gate.py`-authority contract.
- [ ] `docs/architecture.md` execution matrix added (AC5).
- [ ] Reviewed by `jig:reviewer` (compliance + craft); deviation log produced.
- [ ] **Closes the ADR-0008 rebase phase** — spec 003 returns to DONE once
      003-06..08 are DONE; the README skills table + status board reflect it.

**Open question (resolve at implementation):** does `/goal` + `/background`
compose in headless `-p`, or is detachment better served by a background-process
pattern around the goal-driver? The remaining ADR-0008 V4 "remote Routine
mechanics" check (`v4_routines_probe.md`) informs this; it is non-blocking for
the decision but informs this slice's detachment mechanics.

**Anti-horizontal-phasing check:** After this slice a scheduled/detached run is a
real user-facing capability — point a Routine at a servo target and it runs the
guardrailed, oracle-authoritative loop unattended. End-to-end value.
