# ADR-0008 verification harness — V1 (Stop-hook collision) & V2 (caps bind /goal)

Empirical probes for the two **open verification gates** in
[ADR-0008](../adr-0008-loop-on-autonomy-primitives.md) that the docs leave
`UNVERIFIABLE`. The ADR must not be accepted (nor spec 003 amended) until these
have real answers — this directory produces them.

| Gate | Question | Decides |
|------|----------|---------|
| **V1** | Does `/goal`'s managed session-scoped `Stop` hook **collide** with servo's shipped meta-judge `Stop` hook ([ADR-0006](../adr-0006-meta-judge-output-contract.md)) — stack, preempt, or break? | Whether the meta-judge survives the rebase (Kill-criterion 1). |
| **V2** | Does `/goal` **engage in headless `-p`** at all, and does the outer `--max-budget-usd` **hard-bind** a `/goal`-driven run? | Whether servo can still enforce its retained cost ceiling once `/goal` owns the loop (Kill-criterion 2), and whether the headless model even applies. |

## Design

The probes run real `claude` against **throwaway servo-shaped targets** built by
the harness, using a deterministic, controllable workload:

- **`fixtures/oracle.sh`** — a *read-only* oracle whose verdict is driven by
  `<target>/.servo/exp/phase` (`fail`→exit 1, `pass`→exit 0). It prints both the
  `oracle: composite=X threshold=Y` line `gate.py` parses **and** the
  `SERVO_ORACLE_VERDICT …` sentinel the proposed `/goal` condition fact-checks.
  Being read-only is the point: the meta-judge runs it on *every* Stop without
  advancing the loop.
- **`fixtures/work_step.sh`** — the *only* state mutator. After `pass_after`
  calls it flips the phase fail→pass. Only the agent's loop body calls it, so the
  meta-judge's scoring never drives progress (no confound).
- **`fixtures/mj_wrapper.sh`** — behavior-preserving instrumentation installed
  over servo's **real** meta-judge (kept as `meta-judge.real.sh`). Logs each Stop
  firing's `stop_hook_active`, the delegate's rc, and its stdout
  (`block`/`systemMessage`/empty), then re-emits unchanged.

**V1** runs three arms and compares: **A** meta-judge only (baseline; also proves
project hooks fire in `-p`), **B** `/goal` only, **C** both (the collision test).
**V2** runs: **a** `/goal` engages? **b** does `--max-budget-usd` halt a goal that
never completes (`pass_after=99`)? **c** plain control (no `/goal`).

`--include-hook-events` is captured in the stream so `/goal`'s managed hook may be
observed directly alongside the meta-judge log. The robust loop-progress signal
is `final_progress` / `reached_status_pass`, not the possibly-ambiguous
`num_turns`.

## Run

```bash
./preflight.sh              # FREE — no API. Validates the whole substrate. Run first.
./v1_collision.sh           # live: 3 nested claude runs (V1)
./v2_caps.sh                # live: 3 nested claude runs (V2)
./v3_hook_restrictions.sh   # live: baseline vs disableAllHooks (V3)
python3 v3_audit_env.py [<target>]   # FREE: audit a real env for the hook-kill switches (V3)
./v4_clean_clone_sim.sh     # FREE: clone-portability of oracle + meta-judge (V4)
#   v4_routines_probe.md    # manual cloud checklist (V4 cloud leg — not automatable here)
python3 analyze.py {v1|v2|v3} _work/runs/<run-dir>   # re-print analysis anytime
```

Knobs (env): `ADR8_MODEL` (default `claude-haiku-4-5-20251001`),
`ADR8_MAX_BUDGET_USD` (default `0.50`/run), `ADR8_V2B_BUDGET` (default `0.08`),
`ADR8_RUN_TIMEOUT_SECS` (default `240`), `ADR8_ALLOWED_TOOLS`.

Read the per-arm metrics + the `INTERPRETATION` block `analyze.py` prints; a
machine-readable rollup lands at `_work/runs/<run>/analysis.json`.

## V3 & V4 probes (remaining gates)

**V3 — availability under hook restrictions.** Confirms the Kill-criterion-4
mechanism and measures its prevalence:
- `v3_hook_restrictions.sh` (live) — `baseline` vs `disableAllHooks` arms. Expect
  the disableAllHooks arm to show **no Stop firings, no meta-judge, and no
  `/goal` continuation** — one switch disables *both* `/goal` (managed hook) and
  the meta-judge (project hook); only `loop.py` (no hooks) survives.
  `allowManagedHooksOnly` is managed-tier-only (not injectable via `--settings`);
  the script prints the manual managed-file method + cleanup.
- `v3_audit_env.py` (free) — inspects a target's settings hierarchy
  (user / project / project-local / managed) for `disableAllHooks` /
  `allowManagedHooksOnly` and prints a per-env verdict (exit 1 if restricted).
  Run it across servo's **real** target environments to measure how often the
  rebase would be unavailable.

**V4 — Routines running the project-local oracle + meta-judge.** Routines are a
cloud product **not exposed in this CLI** (no `routine`/`schedule` subcommand),
so the cloud leg is a manual checklist:
- `v4_clean_clone_sim.sh` (free) — `git clone`s a target and confirms
  `servo:quality-gate` + the meta-judge run from a clean checkout. Surfaces the
  portability requirement: the meta-judge works post-clone **only if `gate.py` is
  vendored** into `<target>/.claude/skills/servo-quality-gate/` (relative path);
  a non-vendored install bakes servo's absolute path → fails open in a clone.
- `v4_routines_probe.md` — discovery + the manual cloud checklist (clone? oracle?
  meta-judge Stop fires in-cloud? hook policy? `/goal` continuation?) with a
  pass/fail rubric and a results table to fill in.

## Safety & permissions

- Targets are throwaway under `_work/` (git-ignored); fixtures take no args and
  touch nothing outside their target.
- Every live run is bounded by `--max-budget-usd` **and** a wall-clock timeout.
- The nested agent is scoped by a **narrow `--allowedTools` allowlist** to *only*
  `./oracle.sh` and `./work_step.sh` — deliberately **not**
  `--permission-mode bypassPermissions`. A blanket bypass would make these
  autonomous nested agents unsafe, and a permission classifier will (correctly)
  refuse it when inferred by an agent rather than authorized by you.
- Running the live probes still spawns nested `claude -p` agents and spends real
  budget, so it needs **your** authorization (approve the run, or add a Bash
  permission rule per your settings).

## Findings already captured (no API spend)

- `preflight.sh` **passes**: `gate.py` reads the fixture correctly (fail→1,
  pass→0), and the **real** meta-judge behaves exactly per ADR-0006 —
  **BLOCK** on the first below-threshold Stop (`stop_hook_active=false`),
  **SUPPRESS** on the repeat (`stop_hook_active=true`), **silent allow** on pass.
- `claude` here is **2.1.142** (`/goal`-capable). `--max-budget-usd`,
  `--include-hook-events`, `--permission-mode` are present; **`--max-turns` is
  ABSENT from this build's `--help`** — so the hard *turn* cap is unavailable
  here and V2 can only exercise the *budget* cap. (Direct V2 data point: a hard
  turn ceiling cannot be assumed at the CLI in servo's environment.)
- A nested `claude -p` invocation runs cleanly in this environment ($0.026 smoke).

### Live results (2026-06-12)

- **V1 → STACK (no collision).** Arm C: two `Stop` hooks fire per stop (6 events
  = 2 hooks × 3 stops) — `/goal`'s managed hook (empty) + servo's meta-judge
  returning its real `{"decision":"block", composite=0.0 threshold=0.5}`, the
  same block as standalone arm A. First firing sees `stop_hook_active=false`
  (not preempted); one-nudge guard holds; all arms exit 0 → `phase=pass`. The
  meta-judge survives the rebase as a deterministic backstop.
- **V2 → favorable; both caps bind.** `/goal` engages in `-p` (arm a looped to
  `phase=pass`, progress 3, stopping on the real oracle pass; control did 1
  cycle, progress 1). **Both** outer caps hard-bind a `/goal` run:
  `--max-budget-usd` → `error_max_budget_usd` at the cap; `--max-turns N` →
  `subtype=error_max_turns` / `terminal_reason=max_turns` at the cap (cost far
  under the budget headroom). ⚠ `--max-turns` is *functional but hidden from
  `claude --help`* — test flag availability **by invocation** (vs a bogus-flag
  control), never by `--help` grep.

- **V3 → mechanism confirmed.** baseline runs both `/goal` + meta-judge to
  `pass`; `disableAllHooks` → `num_turns=0`, `$0`, **zero hooks fired**, `/goal`
  refuses verbatim (*"…can't run while hooks are restricted (disableAllHooks or
  allowManagedHooksOnly…)"*). One switch disables both `/goal` and the meta-judge
  (the refusal names both); only loop.py survives. Remaining: run
  `v3_audit_env.py` across real target envs to measure prevalence.
- **V4 → free sim done (must vendor `gate.py`); cloud leg is the manual checklist
  in `v4_routines_probe.md`.**

See the ADR Verification section for how these fold into the decision.
