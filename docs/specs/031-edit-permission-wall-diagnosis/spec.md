---
status: DONE
skill:
use_cases: []
---

# Spec 031: Edit-permission-wall diagnosis

> Implements [ADR-0037](../../decisions/adr-0037-agent-loop-permission-preflight.md)
> (Accepted 2026-09-01, after a 5-round frame-critique). Realizes the
> **post-hoc terminal-reason relabel**: when `/servo:agent-loop`'s headless
> `claude -p` child cannot edit (a silent permission wall), the run halts today
> with a *misleading* reason (`oracle_plateau` / `iteration_cap_reached`) and no
> fix hint. This spec makes the loop report the **correct** terminal reason —
> `edit_permission_unavailable` — with an actionable breadcrumb, at the halt the
> existing brakes already produce.

## Overview

The airlock spec-008 dogfood behind ADR-0037: two runs (~$2.2) where the runner
ran, cost money, and made **zero edits** because headless `Edit`/`Write` were
silently denied — but the loop halted with `oracle_plateau` /
`iteration_cap_reached` and no hint that the fix is a permission grant. The
accepted decision (ADR-0037 Option E) is a **diagnostic relabel**, not a new
brake:

- **Signal** — for each **runner** iteration, record whether it changed anything
  on disk, computed as a per-invoke **delta** (snapshot before the runner turn
  vs. after) that **includes untracked new files**.
- **Disarm flag** — a persisted `runner_ever_edited` boolean, set true on the
  first runner iteration that lands any change (an edit *proves* permission),
  checkpointed so it survives `--resume`.
- **Relabel** — at the halt the existing brakes already produce, if
  `runner_ever_edited` is false and the oracle is below threshold, relabel the
  terminal reason to `edit_permission_unavailable` (still `rc=2`) with a
  breadcrumb naming the grant to add. It never fires earlier than today, so it
  can never lose a capable run; the oracle-below-threshold conjunct confines
  every signal blind-spot to already-failing runs.

## Current state (verified against `skills/agent-loop/loop.py`, 2026-09-01)

Load-bearing facts, each probe-grounded (so they are stated here, not in
`## Assumptions`):

- **Runner/judge alternation** — `_agent_for_iteration(iteration)` returns the
  runner on odd iterations and the judge on even ones (`loop.py:444`); the judge
  is read-only by contract (`Read`/`Glob`/`Grep`, no `Write`/`Edit`/`Bash` —
  `agents/judge.md:18`), so judge iterations land zero edits *by design*.
- **Loop-driver halt** — after each iteration's gate scoring, `run_loop` breaks
  on pass (`REASON_ORACLE_PASSED`), cost ceiling (`REASON_COST_CEILING_REACHED`),
  plateau (`REASON_ORACLE_PLATEAU`, via `_check_plateau`, which fires at
  `window+1` scored iterations — `loop.py:588`, and `break`s at `loop.py:2328-2334`),
  else falls through to `REASON_MAX_ITERATIONS_REACHED` (`loop.py:2340`). The
  per-iteration runner invoke is `_invoke_claude(...)` at `loop.py:2150-2170`.
- **`_dirty_tree_paths` is the wrong signal to reuse as-is** — it excludes
  untracked `??` entries (`loop.py:1485`, deliberate, so `.servo/` artifacts
  don't self-trip) and returns `None` for a non-git target (`loop.py:1472`). A
  net-new untracked-inclusive delta is required.
- **Resume** — `run_loop` resume reconstructs only from `oracle_score_history` /
  `iteration_count` (`loop.py:2095-2099`) and deliberately skips the dirty-tree
  preflight (`loop.py:2037-2042`); so a new flag must be persisted in state to
  survive `--resume`.
- **Goal driver** — a separate path `run_goal_loop` (`loop.py:2595`) issues a
  single long `claude -p` via `_invoke_claude_goal` (`loop.py:2447`) with no
  per-iteration checkpoint; it assigns `REASON_ITERATION_CAP_REACHED`
  (`loop.py:2844`) or `REASON_ORACLE_BELOW_THRESHOLD` (`loop.py:2856`) at its
  terminal.

**Frame provenance (why `## Assumptions` is "None").** No unverified load-bearing
assumption remains: the decision frame was settled in ADR-0037's 5-round
frame-critique (`docs/decisions/reviews/adr-0037-frame-critique.md`), the facts
above are probe-grounded, and the one implementation seam (isolating the runner
invoke's disk changes from the gate call and `.servo/` write) is a testable
acceptance criterion with both-direction fixtures (031-01 AC2/AC7), not a claim
asserted as fact. So `frame_review` derives `false` — the adversarial
pre-implementation pass already ran, at the ADR.

## Assumptions

None.

## Decomposition

SPIDR split on the **Path** axis (which driver's path through the diagnosis),
with the deferred optimization split off on the **Rules** axis:

- **031-01 (Path — loop driver, the walking skeleton).** The full vertical for
  the loop driver: the untracked-inclusive per-runner-iteration disk-delta
  signal, the persisted resume-safe `runner_ever_edited` flag, and the terminal
  relabel at `run_loop`'s existing halt. End-to-end: a walled loop-driver run
  reports `edit_permission_unavailable` with a fix breadcrumb; a capable run
  (including one whose only work is *creating* new files) is never mislabeled.
- **031-02 (Path — goal driver).** Extend the relabel to `run_goal_loop`'s
  terminal, reading a whole-run disk delta around the single `_invoke_claude_goal`
  invocation. Depends on 031-01 for the shared delta/breadcrumb helpers.
- **031-03 (Rules — best-effort ex-ante advisory, DEFERRED).** The goal-driver
  optional pre-spend advisory check (ADR-0037 Option E's advisory leg). Deferred
  per ADR-0037 Open Question 1: the post-hoc relabel closes the diagnosis hole
  for both drivers, and the advisory is a pure goal-budget optimization carrying
  resolution-fidelity complexity; ship only once goal-driver waste is measured to
  warrant it.

## Slices

- [031-01 — loop-driver-relabel](slice-01-loop-driver-relabel.md)
- [031-02 — goal-driver-relabel](slice-02-goal-driver-relabel.md)
- [031-03 — goal-driver-advisory-preflight](slice-03-goal-driver-advisory-preflight.md) (DEFERRED)
