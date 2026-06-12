---
status: Accepted
date: 2026-06-12
deciders: ramboz
supersedes:
superseded-by:
---

# ADR-0008 — Rebase agent-loop orchestration onto Claude Code autonomy primitives (/goal, /background, Routines)

## Context

Servo's agent-loop (spec 003, DONE) is a hand-rolled headless iteration
driver. `skills/agent-loop/loop.py` subprocesses `claude -p --output-format
json --resume <session_id> --agent <name> --max-budget-usd <N>` once per
iteration and owns the surrounding machinery itself: an explicit
continuation loop (`for iteration in range(...)`, default `--max-iterations
5`), checkpoint/resume against `<target>/.servo/runs/<run-id>/state.json`
(ADR-0004), a hard cumulative cost ceiling (default `$2`, ADR-0004), a
context-fill gate, SIGINT/SIGTERM handling, oracle-plateau detection, and
verdict-schema halting. It stops on any of: oracle pass, iteration cap, cost
ceiling, context-full, signal, plateau, or schema mismatch.

When spec 003 was written, none of that existed in the platform. Since then
Claude Code has shipped autonomy primitives that overlap large parts of this
machinery:

- **`/goal`** (v2.1.139, 2026-05-11) — across-turn continuation: Claude keeps
  working turn after turn until a stated completion condition holds. After
  each turn a small fast model re-checks the condition. Overlaps loop.py's
  continuation loop and (softly) its iteration cap.
- **`/background`** (alias `/bg`) — detached sessions that keep running with no
  terminal attached and can be reattached later. Overlaps loop.py's
  checkpoint/resume + the "run it unattended" use case.
- **Routines** — saved configurations (prompt + repos + connectors) that run
  unattended on Anthropic-managed cloud infrastructure, scheduled or triggered.
  Overlaps the scheduling dimension servo never built but would eventually need.

Maintaining a bespoke driver that re-implements continuation, session resume,
signal handling, and turn-capping is a standing cost: the platform now owns
these, will keep improving them, and servo's versions will drift. But the loop
mechanics were never servo's differentiator. Servo's value-add is the
**deterministic guardrail + oracle layer**: the `oracle.sh` exit-code authority
and `gate.py`'s closed `0/1/2` contract (ADR-0002), the meta-judge `Stop` hook
(spec 004, **shipped**; contract fixed by **ADR-0006**), the hard cost ceiling,
refuse-without-oracle, and refuse-on-dirty-tree.

This ADR asks: **can servo shed the loop mechanics to the platform primitives
and keep only the guardrail + oracle layer?** It is implemented by amending
spec 003; it does not amend spec 003 until the open verification gates below
clear.

## Decision

**Proposed (gated):** rebase orchestration onto the primitives, keeping the
guardrail + oracle layer as servo's *sole* value-add — **conditional on the
open verification gates** (especially V1, the Stop-hook collision, and V2, hard
caps binding a `/goal` run). If a gate fails, fall back to the hand-rolled loop
(see Kill-criteria and Alternative 2).

**Status (2026-06-12): all four verification gates have cleared** (see
Verification) — none failed, so the rebase stands. The external-driver path is
**retained as the portable layer** for hook-restricted and non-Claude-Code hosts
(Assumption 7), not as a triggered fallback.

**Delegated to the platform (when gates pass):**

1. **Continuation → `/goal`.** Each turn's loop body runs `servo:quality-gate`
   and the `/goal` condition decides whether to continue.
2. **Detachment → `/background`.** Replaces the "keep it running unattended"
   use case.
3. **Scheduling → Routines.** The scheduling dimension servo never built.
4. **Turn-capping → `claude -p --max-turns` / SDK `maxTurns`.** A *hard*,
   runtime-enforced ceiling that **V2 confirms binds a `/goal`-driven run**
   (stops with `subtype=error_max_turns` at the cap). Revises the brief's premise
   that only a soft in-condition cap was available. (`--max-turns` is functional
   but *hidden from `claude --help`* — see the grounding note.)

**Retained in servo (NOT delegated, by design):**

- **Deterministic oracle gating** — `oracle.sh` + `gate.py`'s `0/1/2` contract
  (ADR-0002). The authority for "is the work actually good."
- **Hard cost ceiling** — `/goal` has *no* native cost cap (settled fact below).
  Enforced via the outer `claude -p --max-budget-usd` flag plus servo-side
  cumulative accounting.
- **Refuse-without-oracle** and **refuse-on-dirty-tree** — preflight guardrails.
- **Hard turn ceiling** — now **delegable to `--max-turns`** (V2-verified to bind
  a `/goal` run), so no longer required servo-side; servo MAY keep a cheap
  redundant cap as defense-in-depth, but it is not load-bearing.

**Hard constraint — do not violate (the load-bearing invariant):**

`/goal`'s stopping evaluator is a **transcript-only LLM judge** — a managed,
session-scoped prompt-based `Stop` hook that *does not run tools* and can only
judge what Claude has already surfaced in the conversation. It **MUST NOT**
replace `oracle.sh`. The required composition is:

- The loop body runs `servo:quality-gate` (the real, tool-running oracle) every
  turn and **prints the oracle's verdict into the transcript** as a
  machine-greppable sentinel, e.g.
  `SERVO_ORACLE_VERDICT exit=0 status=pass composite=0.91 threshold=0.85`.
- The `/goal` condition is phrased only as a **fact-check** of that sentinel,
  e.g. *"continue until the transcript contains a line
  `SERVO_ORACLE_VERDICT exit=0 status=pass`."*
- The evaluator never re-derives the verdict; it confirms a **deterministic
  fact** (the oracle already printed a pass), not a judgment. `oracle.sh`
  remains the sole authority for what "pass" means (ADR-0002). The transcript
  judge sits *downstream* of the oracle, never in place of it.

## Assumptions

1. The loop body can be authored so the oracle sentinel is surfaced in the
   transcript **every turn**, unambiguously enough that the transcript judge
   cannot confuse a failing run for a passing one (no partial/multi-line cut,
   one canonical token per turn).
2. `/goal`'s per-turn evaluation runs on a small fast model and is negligible
   against main-turn spend, so adding it does not distort servo's cost model.
3. Servo's target environments **permit hooks** (trust dialog accepted; *not*
   `disableAllHooks`, *not* `allowManagedHooksOnly` in managed settings).
   Both `/goal` and the meta-judge hook need this; if a target forbids hooks,
   neither works and only the hand-rolled loop survives (see V3).
4. The primitives are stable enough contracts to depend on — in particular that
   `/goal`'s transcript-judge semantics and the `--max-turns`/`--max-budget-usd`
   enforcement points will not silently change under servo in a way that breaks
   the fact-check composition or cap enforcement.
5. `/goal` is usable from the **headless** `claude -p` model servo uses today —
   **V2-confirmed** (it continues across turns in `-p` and fact-checks the
   sentinel). `/background` remains an option for a detached model.
6. Routines can clone the target and run servo's project-local `oracle.sh` (V4:
   vendored `gate.py` confirmed portable; local scheduled runs work). Two V4
   findings refine this: a continuous-invocation Routine **does not engage the
   meta-judge** (in Routines, `gate.py` — loop-body + final — is the authority,
   not the `Stop` hook), and scheduled runs reusing a persistent tree can
   **inherit a dirty state** → *refuse-on-dirty-tree* is load-bearing there. The
   remote/cloud hook policy + fresh-clone execution remain to confirm.
7. **Host scope.** The primitive-delegated path assumes a **Claude Code host with
   trusted hooks**. The primitives are Claude-Code-specific — on a non-Claude host
   (e.g. Codex, which also blocks hooks until trusted) or any runner that executes
   the task as one continuous invocation, neither `/goal` nor the meta-judge
   applies, and servo uses the external-driver path (drive the agent CLI; gate via
   `gate.py`, not a `Stop` hook). The external driver is the **portable cross-host
   layer**, not a rare fallback.

## Kill-criteria

Abandon the rebase and fall back to the hand-rolled loop (Alternative 2) if any
of the following holds:

1. **Stop-hook collision (primary).** If `/goal`'s managed session-scoped
   `Stop` hook and servo's meta-judge `Stop` hook (ADR-0006) compose
   destructively — one suppresses the other, `/goal`'s managed hook is
   exclusive, or co-presence breaks the one-nudge-per-sequence
   (`stop_hook_active`) guard — the rebase cannot preserve servo's oracle-driven
   nudging. (Gate V1.)
2. **Caps escape the loop.** If `--max-turns` / `--max-budget-usd` on the outer
   `claude -p` invocation do **not** bind a `/goal`-driven continuation (i.e.
   `/goal` can run past servo's hard ceilings), servo loses the very enforcement
   point that delegating the loop was supposed to preserve. The retained cost
   ceiling would then be unenforceable without servo's own outer loop — which
   collapses the rebase's benefit. (Gate V2.)
3. **Transcript judge is unreliable.** If the evaluator cannot dependably
   fact-check the printed oracle sentinel — false *positives* (stops while the
   oracle is still failing) or false *negatives* (loops past a printed pass) —
   the continuation contract is broken and the oracle's authority is
   effectively undermined at the loop boundary.
4. **Target environments forbid hooks.** If servo's primary target environments
   commonly set `disableAllHooks` / `allowManagedHooksOnly`, `/goal` is
   unavailable there and the rebase only works in a subset of environments —
   so the hand-rolled loop must remain the default for portability. (Gate V3.)

## Consequences

### Positive

- Sheds duplicated mechanics (session resume, signal handling, the turn loop,
  detachment, scheduling) to the platform; servo shrinks to its differentiated
  core — the deterministic guardrail + oracle layer.
- Servo rides future platform improvements to continuation/detachment/
  scheduling for free instead of re-implementing them.
- Sharper conceptual split: the platform owns *"keep going"*; servo owns *"is it
  actually good, and is it safe to keep going."*
- Gains a scheduling story (Routines) servo never had.

### Negative

- Couples servo to `/goal`, a young primitive (v2.1.139), and to its
  transcript-judge semantics — a contract servo does not control.
- Loses portability to hook-restricted environments, which the
  subprocess-only hand-rolled loop did not depend on.
- The fact-check composition is more indirect than loop.py's direct exit-code
  read — it introduces a failure class (verdict printed but mis-judged) the
  hand-rolled loop never had.
- Two `Stop` hooks (`/goal`'s managed one + the meta-judge) both fire per stop.
  V1 confirms they **stack** cleanly — no amendment forced by collision — but
  `/goal` driving continuation makes the meta-judge partly redundant as a
  *driver*; repositioning it as a deterministic *backstop* is a spec-003
  refinement to ADR-0006's one-nudge guard, not a breakage.

### Neutral

- The oracle authority and the `gate.py` `0/1/2` exit-code contract (ADR-0002)
  are unchanged in either outcome — they are explicitly out of scope for
  delegation.
- The hard cost ceiling stays servo-owned in either outcome; only its
  *enforcement mechanism* (servo's own loop vs. the outer `--max-budget-usd`)
  changes.

## Alternatives considered

1. **Replace `oracle.sh` with `/goal`'s evaluator — rejected hard.** This
   inverts servo's core invariant: a transcript-only LLM judge would sit in
   authority over the deterministic oracle, violating the ADR-0002 exit-code
   contract and the entire premise that servo gates on deterministic facts, not
   judgments. The `/goal` evaluator provably cannot reproduce `oracle.sh` — it
   does not run tools (settled fact below). Non-starter; recorded only to fix it
   as out of bounds.
2. **Keep agent-loop fully hand-rolled (status quo) — rejected as the default,
   retained as the fallback.** Default-rejected because it perpetuates
   re-implementing platform primitives. But explicitly *retained as the fallback
   that the kill-criteria fall back to*: if V1 (Stop-hook collision) or V3
   (hook-restricted environments) fail, the hand-rolled loop remains servo's
   supported path. It is demoted from default to fallback, not discarded.

## Verification

### Settled grounding (confirmed before this ADR)

Claims verified against the Claude Code docs at `code.claude.com/docs/en/…`
(retrieved 2026-06-12) and against the servo repo:

- **`/goal` exists and continues across turns**, re-checking a condition each
  turn via a small fast model — `goal.md`; introduced v2.1.139, 2026-05-11
  (`changelog.md`).
- **`/goal`'s evaluator is transcript-only and runs no tools** — `goal.md`:
  *"It does not call tools, so it can only judge what Claude has already
  surfaced in the conversation."* This is the basis of the Hard constraint and
  of rejecting Alternative 1.
- **`/goal` has no native hard token/cost ceiling** — `goal.md` documents no
  `--max-cost`/budget parameter; the only bound it offers is a soft, model-
  judged in-condition clause (e.g. *"or stop after 20 turns"*). **Therefore the
  cost-ceiling guardrail is RETAINED in servo, not delegated.** (Settled per the
  decision brief — recorded as fact, not an open question.)
- **Both a hard turn ceiling and a hard spend ceiling exist and bind a `/goal`
  run (verified functionally on 2.1.142 + 2.1.175).** `cli-reference.md`
  documents `--max-turns` (*"Limit the number of agentic turns (print mode only).
  Exits with an error when the limit is reached"*) and `--max-budget-usd`; the
  Agent SDK exposes a hard `maxTurns`. Both confirmed by direct invocation:
  `--max-turns N` halts a `/goal` run with `subtype=error_max_turns` /
  `terminal_reason=max_turns` at the cap (cost far under the budget headroom),
  and `--max-budget-usd` halts with `error_max_budget_usd` at the cap. **So both
  the hard turn and hard cost ceilings are delegable to the outer `claude -p`
  flags even when `/goal` owns the loop.** ⚠ Method note: `--max-turns` is *not
  listed in `claude --help`* yet is fully functional — confirmed by an acceptance
  probe against a bogus-flag control (a bogus flag errors `unknown option`;
  `--max-turns` runs cleanly). Do **not** infer flag availability from `--help`.
- **`/goal` is unavailable under hook restrictions** — `goal.md`: *"/goal is
  also unavailable when `disableAllHooks` is set at any settings level or when
  `allowManagedHooksOnly` is set in managed settings."* Servo's meta-judge is a
  *project* (non-managed) hook, so the *same* settings disable it too — under
  those settings **both** the rebased design and the current Stop-hook break,
  while loop.py (no hooks) survives. (Feeds Assumption 3, Kill-criterion 4, V3.)
- **`/background` detaches a running session** (alias `/bg`), reattachable —
  `agent-view.md`. **Routines run unattended on Anthropic-managed cloud
  infrastructure**, distinct from in-session `/loop` and from `/schedule` —
  `routines.md`.
- **The meta-judge Stop hook is SHIPPED, not planned** — spec 004 is DONE and
  **ADR-0006** is Accepted (`skills/oracle-hook/hook.py`,
  `templates/meta-judge.sh.template`). The collision question (V1) is therefore
  against an *accepted contract*, not a design sketch.

### Verification gates — all four cleared (2026-06-12); only non-blocking follow-ups remain (V3 prevalence audit, V4 remote mechanics check)

V1 and V2 were the decisive unknowns. Both were probed with a live harness
(`docs/decisions/adr-0008-experiments/`) that runs real `claude` against
throwaway servo-shaped targets using the **real** `gate.py` + meta-judge,
instrumented to log every `Stop` firing. Both cleared favorably and **reproduced
on both v2.1.142 and v2.1.175** (`/goal`-capable); the captured runs + analysis
rollups are under that directory.

- **V1 — Stop-hook collision → RESOLVED: STACK (no collision). The meta-judge
  survives; Kill-criterion 1 does not trigger.** Three arms — A (meta-judge
  only), B (`/goal` only), C (both). In arm C the stream shows **two `Stop`
  hooks firing per stop** (6 `Stop` hook events = 2 hooks × 3 stops): one is
  `/goal`'s managed hook (empty response), the other is servo's meta-judge
  returning its real `{"decision":"block", … composite=0.0 threshold=0.5}` — the
  same block it emits standalone in arm A. The meta-judge's first firing sees
  `stop_hook_active=false` in C exactly as in A (so `/goal`'s hook does **not**
  preempt it), and its one-nudge-per-sequence guard still holds (later firings
  see `true` → suppress). All arms exit 0 and reach `phase=pass`; no deadlock,
  runaway, or error. *Residual design note (a spec-003 refinement, not a
  blocker):* because `/goal` now drives continuation, the meta-judge is partly
  **redundant as a continuation driver** — its retained value is as the
  deterministic **backstop** that blocks a stop when the real oracle is below
  threshold (defending against the transcript-judge being fooled by a spurious
  sentinel). ADR-0006's one-nudge guard + the meta-judge's role should be
  revisited when amending spec 003.
- **V2 — headless `/goal` + cap binding → RESOLVED favorably; BOTH caps bind.
  Kill-criterion 2 does not trigger.** (a) `/goal` **engages in headless `-p`**:
  with `/goal` it looped to `phase=pass` (progress 3) and stopped exactly when
  the real oracle printed `status=pass`, vs. the plain control's single cycle
  (progress 1, no pass) — so `/goal` drives continuation **and** the
  transcript-judge-over-printed-sentinel composition (the Hard constraint) works
  in `-p`. (b) **Both hard caps bind a `/goal` run**: `--max-budget-usd` halts
  with `error_max_budget_usd` at the cap (`$0.08` → stopped at `$0.084`), and
  `--max-turns N` halts with `subtype=error_max_turns` / `terminal_reason=
  max_turns` at the cap (`num_turns≈cap`, cost far below the budget headroom — so
  the *turn* cap, not spend, bound it). So servo's hard cost ceiling **and** a
  hard turn ceiling are both enforceable through the outer `claude -p` flags when
  `/goal` owns the loop. (`--max-turns` is functional despite being absent from
  `claude --help` — verified by an acceptance probe vs a bogus-flag control.)

- **V3 — availability under hook restrictions → MECHANISM CONFIRMED (live,
  2026-06-12); prevalence audit remains.** `v3_hook_restrictions.sh`: the baseline
  arm runs both `/goal` + meta-judge to `pass`; the `disableAllHooks` arm produced
  `num_turns=0`, `$0`, **zero hooks fired**, and `/goal` refused verbatim — *"/goal
  can't run while hooks are restricted (disableAllHooks or allowManagedHooksOnly is
  set in settings or by policy)."* One switch takes out BOTH `/goal` and the
  (project) meta-judge; the refusal even names `allowManagedHooksOnly`, confirming
  both gates without the managed-file test. Under such a restriction the whole
  `/goal`-led invocation no-ops — only loop.py (no `/goal`, no hooks) runs.
  REMAINING (org-specific, not a technical unknown): run `v3_audit_env.py` across
  servo's real target environments to measure how common the restriction is
  (Kill-criterion 4 fires iff it is).
- **V4 — Routines run the project-local oracle → RESOLVED (by design, 2026-06-12).**
  Evidence: the free clone sim (`v4_clean_clone_sim.sh`) + a manual dry-run and a
  **scheduled** Routine trigger (`v4_routines_probe.md`). Established: the vendored
  oracle + `gate.py` are **clone-portable** (the meta-judge resolves only on a
  *vendored, relative* `gate.py` path; a non-vendored install bakes servo's absolute
  path and fails open in a clone), the local env permits hooks, and the sentinel
  composition runs unattended. Two findings shaped the resolution: (i) the Routine
  executes the task as a **single continuous agent session** (no per-turn `Stop`) —
  so the meta-judge never fires *naturally* in a Routine; (ii) a scheduled run
  **inherited a dirty working tree** from a prior run (a spurious immediate pass).
  **Resolution:** in a Routine, servo's deterministic authority is **`gate.py`**
  (the loop-body run + a final authoritative run), with **`refuse-on-dirty-tree`**
  enforced at start and **`gate.py` vendored** into the target; the meta-judge
  `Stop` hook stays the backstop for interactive / `claude -p` turn-mediated use
  only (V1). This sidesteps the one unverified point — whether a *cloud* Routine
  fires project `Stop` hooks — which no longer gates the decision. A remote Routine
  run remains a worthwhile but **non-blocking** mechanics check (fresh clone;
  oracle/test execute in-cloud; `audit_env.py` for the cloud policy, informational).

## References

- Claude Code docs (retrieved 2026-06-12): `goal.md`, `cli-reference.md`
  (`--max-turns`, `--max-budget-usd`), `agent-view.md` (`/background`),
  `hooks.md` (`disableAllHooks`, `allowManagedHooksOnly`), `routines.md`,
  `changelog.md` (v2.1.139); Claude Agent SDK `maxTurns` / stop-reasons.
- Servo: spec 003 (`docs/specs/003-agent-loop/`), spec 004 (oracle-hook);
  ADR-0002 (gate caller contract), ADR-0004 (session-state file format),
  ADR-0006 (meta-judge output contract & fail-open posture).
- Servo code: `skills/agent-loop/loop.py`, `skills/quality-gate/gate.py`,
  `skills/oracle-hook/hook.py`, `templates/oracle.sh.template`,
  `templates/meta-judge.sh.template`.
- V1/V2 verification harness + captured runs:
  `docs/decisions/adr-0008-experiments/` (preflight + V1/V2 runners + analyzer;
  results captured 2026-06-12).
