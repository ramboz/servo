---
status: DRAFT
dependencies: [003-02, 003-05, adr-0008]
last_verified:
---

## Slice 003-06 — goal-driven-loop

**STATUS: DRAFT**

> ADR-0008 rebase phase, slice 1 of 3. Adds the **primitive-delegated**
> continuation path alongside the retained hand-rolled loop (003-01..05).

**Goal:** Give the loop driver a `/goal`-driven continuation mode. Instead of
loop.py's hand-rolled `for`-loop over N `claude -p` calls, a single `claude -p`
invocation carries a `/goal` completion condition that drives across-turn
continuation, with servo's hard guardrails wired through the **outer**
invocation. The loop body runs `servo:quality-gate` each turn and prints a
machine-greppable `SERVO_ORACLE_VERDICT` sentinel; the `/goal` condition only
**fact-checks** that sentinel; a **final authoritative `gate.py` run** is the
verdict. `oracle.sh` is never replaced by `/goal`'s transcript judge (ADR-0008
hard constraint; ADR-0002 exit-code contract).

End-to-end value: a user can run a `/goal`-driven loop with every servo brake
wired in — the platform owns "keep going," servo owns "is it actually good, and
is it safe to keep going."

**DoR:**
- ✅ [ADR-0008](../../decisions/adr-0008-loop-on-autonomy-primitives.md) Accepted.
- ✅ V2 verified (claude 2.1.142 + 2.1.175): `/goal` engages in headless `-p`,
  fact-checks the printed sentinel, and **both** `--max-turns` and
  `--max-budget-usd` hard-bind a `/goal` run (`error_max_turns` /
  `error_max_budget_usd` at the cap).
- ✅ Decision: the hand-rolled loop (003-01..05) is **retained** as the
  external-driver path (003-07 routes to it); this slice adds the goal-driver
  *alongside*, selected by `--driver {loop|goal}` (default `loop` for
  backward-compat + portability).
- ✅ Decision: the `/goal` condition is a fact-check of the printed sentinel,
  never a re-judgment (hard constraint).
- ⏳ Verify at implementation: exact `result.subtype` / `terminal_reason`
  strings a `/goal` run emits in `--output-format json|stream-json` (extends the
  spike's `terminal_reason` taxonomy — see Clarifications Q1).

**Acceptance Criteria:**

1. **Goal-driver mode.** `loop.py --driver goal <target>` issues a single
   `claude -p` whose prompt sets a `/goal` condition fact-checking a
   `SERVO_ORACLE_VERDICT … status=pass` line, plus a loop-body instruction to run
   `servo:quality-gate` each turn and print the sentinel verbatim. `--driver loop`
   (default) is the unchanged 003-01..05 hand-rolled driver.
2. **Sentinel contract (shared).** The `SERVO_ORACLE_VERDICT exit=<rc>
   status=<pass|fail> composite=<c> threshold=<t>` line format is a single pinned
   constant used by (a) the loop-body prompt instruction and (b) the
   transcript-scan parser, so the `/goal` condition and the parser agree. The
   bare substring (no `composite=`/`threshold=` tail) does NOT count as a pass
   (guards against the `/goal` condition text echoing itself).
3. **Hard caps on the outer call.** The goal invocation passes
   `--max-budget-usd <cost-ceiling>` (default $2, from 003-02) AND
   `--max-turns <iteration-cap>` (default 5, from 003-01) — the two caps V2
   proved bind a `/goal` run. Their semantics carry over unchanged.
4. **Oracle stays the authority (fail-closed).** After `claude -p` returns, the
   driver runs a final `gate.py --json` against the target and treats THAT exit
   code (0/1/2) as the run verdict — not the transcript sentinel. A run whose
   transcript showed `status=pass` but whose final `gate.py` is below threshold
   halts with `terminal_reason=oracle_disagreement` (fail-closed). Pins the
   ADR-0008 hard constraint at the loop boundary.
5. **Terminal-reason mapping.** The driver parses the result for `subtype` /
   `terminal_reason` and maps: `error_max_turns` → `iteration_cap_reached`;
   `error_max_budget_usd` → `cost_ceiling_reached`; success + final-gate pass →
   `oracle_pass`; success + final-gate fail → `oracle_below_threshold`.
6. **Headless-`/goal` precondition (refuse, don't silently degrade).** If the
   `claude` binary doesn't engage `/goal` in `-p`, or `/goal` is unavailable
   (hooks restricted — V3: it refuses verbatim "can't run while hooks are
   restricted"), `--driver goal` refuses with rc=2 / `reason=goal_unavailable`;
   the stderr breadcrumb names `--driver loop` as the portable fallback. (Routing
   to that fallback automatically is 003-07's job.)
7. **State recording.** A goal-driven run records run-id + cumulative cost +
   final verdict in the existing `<target>/.servo/runs/<run-id>/state.json` shape
   (ADR-0004). `--resume` of a goal-driven run is **out of scope** here
   (detachment is 003-08); a resumed run-id refuses with a clear breadcrumb.

**DoD:**
- [ ] All ACs pass; full suite green (no regressions in `test_loop.py`
      003-01..05 cases). Goal-driver tests mock `claude -p` to emit a
      stream/result with the sentinel (fail then pass) + a `result` event.
- [ ] Per-AC coverage under `skills/agent-loop/test_loop.py` (e.g. AC1→driver
      dispatch, AC2→sentinel parse incl. bare-substring negative, AC3→argv caps,
      AC4→`oracle_disagreement`, AC5→terminal-reason map, AC6→`goal_unavailable`).
- [ ] `SKILL.md` documents the `--driver goal` mode + the sentinel composition.
- [ ] Reviewed by `jig:reviewer` (compliance + craft); deviation log produced.
- [ ] `claude -p` `/goal` behavior empirically re-confirmed at implementation
      (Clarifications Q1 string capture); findings folded into ACs.

**Anti-horizontal-phasing check:** After this slice the goal-driven path is
end-to-end usable — `loop.py --driver goal <target>` runs a guardrailed `/goal`
loop and returns a deterministic oracle verdict. It touches the user-facing CLI
surface, not just internal plumbing.
