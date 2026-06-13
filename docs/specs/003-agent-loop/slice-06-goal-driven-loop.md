---
status: DONE
dependencies: [003-02, 003-05, adr-0008]
last_verified: 2026-06-12
---

## Slice 003-06 — goal-driven-loop

**STATUS: DONE**

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
- [x] All ACs pass; full suite green (no regressions in `test_loop.py`
      003-01..05 cases — 152 retained + 34 new = 186 green). Goal-driver tests
      mock `claude -p` to emit a stream/result with the sentinel (fail then
      pass) + a `result` event.
- [x] Per-AC coverage under `skills/agent-loop/test_loop.py` (AC1→driver
      dispatch, AC2→sentinel parse incl. bare-substring negative, AC3→argv caps,
      AC4→`oracle_disagreement`, AC5→terminal-reason map, AC6→`goal_unavailable`,
      AC7→state recording + resume refusal).
- [x] `SKILL.md` documents the `--driver goal` mode + the sentinel composition.
- [x] Reviewed by `jig:reviewer` (compliance + craft, both PASS); deviation log
      produced; reconciliation review PASS.
- [x] `claude -p` `/goal` behavior empirically re-confirmed at implementation on
      claude 2.1.175 (Clarifications Q1 string capture); findings folded into the
      `SUBTYPE_*` constants + AC5 map.

**Anti-horizontal-phasing check:** After this slice the goal-driven path is
end-to-end usable — `loop.py --driver goal <target>` runs a guardrailed `/goal`
loop and returns a deterministic oracle verdict. It touches the user-facing CLI
surface, not just internal plumbing.

### Deviation log (after reconciliation)

Implemented as `--driver {loop|goal}` (default `loop`) in `skills/agent-loop/loop.py`,
with `run_goal_loop` + helpers, per-AC tests in `test_loop.py`, and `SKILL.md`
documentation. All ACs met; full `test_loop.py` suite green at 186 tests (152
retained loop-mode + 34 new goal-mode); full project suite 732 passed / 1
skipped; ruff clean. Empirical `/goal` re-confirmation (DoR ⏳ / DoD): probed
live on claude **2.1.175** — `--max-turns` binding emits
`subtype=error_max_turns` / `terminal_reason=max_turns` (exit 1); the success
path emits `subtype=success` / `terminal_reason=completed` (exit 0); both match
ADR-0008 V2. Findings folded into the `SUBTYPE_*` constants + the AC5 map.

Deviations and decisions worth recording:

1. **Goal-mode summary line is a new shape, not the loop-mode summary.** AC7
   says state recording reuses "the existing `state.json` shape (ADR-0004)" —
   the **state** does (additive `driver` + goal fields under
   `state_schema_version=1`), but the **stdout summary** is a distinct variant
   (`driver: "goal"`; adds `subtype` / `claude_terminal_reason` / `num_turns` /
   `transcript_showed_pass` / `max_turns`; omits the loop-only
   `iterations_completed` / `oracle_score_history` / `context_fill_*`).
   Documented in `SKILL.md` (Output shape + goal-mode terminal-reason table).
2. **stream-json, not single-result json.** Goal mode invokes `claude -p
   --output-format stream-json --verbose` (loop mode uses single-result `json`)
   so the driver can scan the **whole transcript** for the sentinel — required
   for the AC4 `oracle_disagreement` detection, not just the final message.
3. **New goal-mode terminal-reason taxonomy.** `oracle_pass`,
   `oracle_below_threshold`, `oracle_disagreement`, `iteration_cap_reached`,
   `goal_unavailable`, `goal_resume_unsupported` are new and intentionally
   distinct from loop mode's `oracle_passed` / `max_iterations_reached`.
   `cost_ceiling_reached`, `claude_invocation_failed`, `gate_invocation_failed`,
   and the preflight reasons are shared (AC5 pins `cost_ceiling_reached`).
4. **AC4/AC5 precedence (interpretation the slice text didn't sequence).** A
   hard-cap subtype (`error_max_turns` / `error_max_budget_usd`) wins over the
   `oracle_disagreement` branch — had a real pass sentinel been printed, `/goal`
   would have stopped `success` before the cap fired. Oracle authority is
   preserved (never reported as a pass; `final_oracle_status` carries the real
   gate verdict). Documented inline and pinned by
   `test_cap_precedence_over_disagreement`.
5. **`goal_unavailable` detection is asymmetric (false-positive guard).** The
   verbatim refusal sentence ("can't run while hooks are restricted") matches
   anywhere; the managed-settings key names (`disableAllHooks` /
   `allowManagedHooksOnly`) only count on a **zero-turn run**, so an agent's own
   successful work that mentions those keys is not mis-flagged. Regression:
   `test_successful_run_mentioning_hook_keys_is_not_goal_unavailable`.
6. **Shared preflight extraction.** `_preflight` (loop mode) was refactored onto
   a new `_target_preflight_error` helper that goal mode also uses, so both
   drivers keep gate.py's reason vocabulary (AC4) with no duplication. Behavior-
   preserving — the retained `PreflightRefusalTests` (loop mode) still pass.
7. **Craft-review nits addressed inline (all `[nit]`, non-blocking).** (a)
   interrupt + `goal_unavailable` paths now report real `cumulative_cost_usd`
   (read off the result event) instead of a hardcoded `$0`; (b) loop-only flags
   (`--context-fill-threshold` / `--plateau-window` / `--resume-anyway`) under
   `--driver goal` now emit an "ignored" stderr breadcrumb instead of silently
   no-op'ing; (c) the composed `/goal` prompt names `sys.executable` (not bare
   `python3`) so the agent's in-transcript gate run shares the interpreter of
   the authoritative `_invoke_gate`. Each has a covering test.
8. **`--resume` is out of scope for goal mode (003-08).** `--driver goal
   --resume` refuses (`goal_resume_unsupported`), and a goal-written run-id
   refuses resume under the loop driver too (the state carries `driver: "goal"`).

No architecture-doc or ADR change required: ADR-0008 already governs this slice,
and the state schema stays `state_schema_version=1` (additive). No new
`docs/conventions.md` rule. No `TODO`/`FIXME` introduced.
