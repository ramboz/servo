---
status: DONE
dependencies: [001, 002]
last_verified:
---

# Spec 004 — oracle-hook

> Install (and cleanly uninstall) a Claude Code **`Stop` hook** that runs the
> scaffolded oracle after every assistant turn and feeds a **structured retry
> hint** back to Claude when the oracle is below threshold — the deterministic,
> oracle-scored replacement for ad-hoc transcript-regex Stop-hook scans.
> Idempotent `install` / `uninstall` / `status`; mutates
> `<target>/.claude/settings.json` with a backup; **fails open** so a broken
> oracle never traps a session.

## Why this spec

Specs 001–003 built servo's closed loop for **headless** operation:
`/servo:agent-loop` subprocesses `claude -p` against a target N times, scoring
each iteration with `gate.py`. But the most common way people actually run
Claude Code is **interactively** — a human at a prompt, no loop driver in sight.
In that mode nothing scores the work unless someone remembers to run the gate.

Spec 004 brings the same oracle-scored discipline to the interactive session. A
Claude Code `Stop` hook fires when Claude finishes a turn; servo's hook runs the
**same** scaffolded `oracle.sh` (via `gate.py`, spec 002) and, when the oracle is
below threshold, blocks the stop with a **structured retry hint** — composite vs
threshold (plus any components the gate reports as `missing`) — so Claude keeps
working instead of declaring victory early.

This is the **meta-judge** pattern. The thing it replaces is a brittle one:
ad-hoc `Stop`-hook scripts that *regex-scan the transcript* for "looks done"
phrases. That heuristic is easy to fool and encodes no real quality signal.
Servo already owns a real quality signal — the composite oracle — so the
meta-judge just runs it. The hint is evidence-backed, not a guess.

The hook closes the jig-review gap **"Stop-hook grading (oracle-scored,
structured retry hints)"** ([ROADMAP](../ROADMAP.md)). It is the **interactive
cousin** of `/servo:agent-loop`, and it inverts exactly one polarity:

- `agent-loop` fails **closed** — every guardrail *halts* the loop, because the
  danger is burning budget unattended.
- `oracle-hook` fails **open** — an oracle env-error *lets the turn stop*,
  because the danger is a Stop hook that blocks forever on a misconfigured
  oracle and traps a live session. A meta-judge that can deadlock a human's
  session is worse than no meta-judge at all.

Because installing the hook **mutates `settings.json`**, it is a **Tier-2**
surface (per [architecture.md](../../architecture.md) "Tier model"): offered
explicitly, never auto-installed.

## Pre-spec research (Stop-hook contract)

A 2026-06 documentation probe (Claude Code hooks reference) established the
load-bearing `Stop`-hook contract this spec builds on. The parts servo depends
on:

- **Trigger.** The `Stop` event fires when Claude finishes responding to a turn.
- **stdin.** The hook receives a JSON object on stdin including `session_id`,
  `transcript_path`, `cwd`, `hook_event_name` (`"Stop"`), and — load-bearing —
  **`stop_hook_active`** (boolean: true once this hook has already blocked in the
  current stop sequence). `stop_hook_active` is the infinite-loop guard.
- **Feeding text back — two mechanisms, not one.** The ROADMAP's shorthand
  ("emits retry hints as `additionalContext`") conflates them:
  - **Block** — `{"decision": "block", "reason": "<hint>"}` on stdout with exit
    0 (or exit 2 with the hint on stderr). The turn does **not** end; Claude is
    forced to keep working *now*; `reason` is shown to Claude. This is what makes
    a meta-judge actually nudge.
  - **Soft context** — `{"hookSpecificOutput": {"hookEventName": "Stop",
    "additionalContext": "<hint>"}}` with exit 0. The turn **ends**; the hint is
    injected as a system reminder Claude sees on the *next* turn. Non-blocking.
  - The two are mutually exclusive in one response.
- **Exit codes.** `0` = success (stdout parsed as JSON); `2` = blocking error
  (stderr shown to Claude); any other non-zero = non-blocking error (stderr to
  the transcript, turn proceeds).
- **settings.json shape.** `Stop` hooks register under `hooks.Stop[]` and take
  **no matcher**; each entry is `{ "hooks": [{ "type": "command", "command":
  "...", "timeout": N }] }`.
- **Environment.** `$CLAUDE_PROJECT_DIR` expands to the project root at hook
  invocation — the portable way for the hook command to find its script and the
  target to score.
- **Block cap.** Claude Code overrides a `Stop` hook after a bounded number of
  consecutive blocks (docs: 8) and forcibly stops; an env var
  (`CLAUDE_CODE_STOP_HOOK_BLOCK_CAP`) raises it. Servo does not rely on the exact
  number — it respects `stop_hook_active` so it nudges at most once per sequence.

Version-dependent or not-yet-empirically-confirmed details are recorded under
[Assumptions](#assumptions) and verified during the spike-shaped slice 004-01
(the same escape-hatch posture spec 003-01 used for the headless surface).

## Goals

1. **Install a Stop hook, idempotently.** `hook.py install <target>` drops the
   meta-judge script into `<target>/.servo/hooks/meta-judge.sh` and registers a
   `Stop` hook in `<target>/.claude/settings.json`. Re-running is a no-op, not a
   duplicate.
2. **Grade against the scaffolded oracle.** The meta-judge runs `gate.py` against
   `$CLAUDE_PROJECT_DIR` and consumes spec 002's existing `--json` contract
   (`status` / `composite` / `threshold` / `missing`, exit 0/1/2). No new oracle,
   no new exit-code contract.
3. **Emit a structured retry hint.** On `below_threshold`, the hint names the
   composite and the threshold (plus any `missing` components the gate reports) —
   evidence, not a transcript-regex guess. (Per-component *failing-score*
   evidence needs a spec-002 `gate.py` enhancement; deferred — see slice 004-01
   and [refinement-todo](../../refinement-todo.md).)
4. **Fail open and bound runaway.** An oracle `env_error` never blocks (it
   surfaces a one-line warning to the user and lets the turn stop). The hook
   respects `stop_hook_active` so it nudges at most once per stop sequence, well
   inside Claude Code's block cap.
5. **Clean, reversible install.** Back up `settings.json` before mutating; merge
   without clobbering unrelated keys or other hooks; `uninstall` removes **only**
   servo's entry (leaving the script on disk); `status` reports the install
   state. This is the ROADMAP's `install` / `uninstall` / `status` contract.
6. **Tier-2 explicit opt-in.** Mutating `settings.json` is a higher-risk surface;
   `/servo:oracle-hook` is offered explicitly and never auto-installs.
7. **Project owns policy.** Per [architecture.md](../../architecture.md)
   "Project vs servo-core split": the **project** owns the hook event choice, the
   retry-hint phrasing, and the block-vs-soft-context mode; **servo** owns the
   script template and the `settings.json` mutation + backup machinery.

## Non-goals

- **No LLM judge in the hook (v1).** The meta-judge is the **deterministic**
  oracle, not a model call. Claude Code's `type: "prompt"` / `type: "agent"`
  hooks are a future option; v1 ships a `type: "command"` hook. Servo will not
  pay a model round-trip on every turn-stop.
- **No transcript parsing.** The hook targets `$CLAUDE_PROJECT_DIR` and runs the
  oracle. It does **not** read `transcript_path`. This is a deliberate rejection
  of the regex-scan pattern it replaces.
- **No global settings mutation.** Only `<target>/.claude/settings.json`
  (project-scoped, version-controllable). Never `~/.claude/settings.json` and
  never `settings.local.json` (the project-shared file is the right home for a
  project-owned oracle hook; see [Open questions](#open-questions)).
- **No multi-event installer.** v1 installs a `Stop` hook only. PreToolUse /
  PostToolUse / SubagentStop / SessionStart are out of scope.
- **No new gate contract.** `gate.py`'s closed 0/1/2 exit codes and `--json`
  schema (ADR-0002) are the truth-source, used as-is.
- **No CI wiring.** The installed hook is a per-developer interactive aid, not a
  CI gate (servo already has `gate.py` for that).

## Core model

The meta-judge is a thin, deterministic decision table over `gate.py`'s result.
It runs on every `Stop`, but does the least surprising thing in each case:

| Oracle result (`gate.py --json`) | Meta-judge action | Why |
|---|---|---|
| `stop_hook_active == true` (stdin) | exit 0, silent | Already nudged this sequence — never runaway-block |
| `status=pass` (exit 0) | exit 0, silent | Work clears the bar; let the turn stop |
| `status=below_threshold` (exit 1) | **block** + structured `reason` hint | The meta-judge's whole point — keep working |
| `status=env_error` (exit 2) | exit 0 + `systemMessage` warning to user | **Fail open** — a broken oracle must not trap the session |
| `gate.py` itself errors / not found | exit 0 + `systemMessage` warning | Same fail-open posture |

The **install model** is settings.json surgery plus script placement:

```
<target>/
├── .claude/
│   └── settings.json          # hooks.Stop[] entry added/removed by install/uninstall
│                              # backed up to settings.json.servo-bak before first mutation
└── .servo/
    └── hooks/
        └── meta-judge.sh       # copied from templates/; user-customizable; survives uninstall
```

The meta-judge script template is servo-owned and ships at
`templates/meta-judge.sh.template` (alongside the existing
`templates/oracle.sh.template`). `install` copies it to the target and points the
`settings.json` entry at it via `$CLAUDE_PROJECT_DIR`.

## Hook output contract (ADR-0006 candidate)

The decision table above is a **behavioral contract** that future specs, the
installed projects, and users depend on — the `Stop`-hook analog of ADR-0002's
gate-caller contract. The hard-to-reverse choices:

1. **Block (not soft-context) is the v1 default.** A meta-judge exists to *make*
   the agent keep working; `decision: block` does that, `additionalContext` only
   hints next turn. The soft-context mode is offered as a project-owned knob.
2. **Fail open on `env_error`.** The inverse of agent-loop's fail-closed brakes,
   for the reasons in [Why this spec](#why-this-spec).
3. **One nudge per stop sequence** (respect `stop_hook_active`). Aggressive
   block-until-pass is a documented project-owned customization, not the default.

This crystallizes as **ADR-0006 — meta-judge Stop-hook output contract &
fail-open posture**, expected to land at slice 004-02 (when the full table —
block + fail-open + `stop_hook_active` — is first implemented). The
block-vs-context base choice is made provisionally in 004-01.

## SPIDR analysis

| Technique | Question | Decision |
|---|---|---|
| **S — Spike** | Can a `Stop` hook run `gate.py` and feed a structured hint back that actually makes Claude keep working? | **Yes, but spike-shaped first slice.** 004-01 validates the contract end-to-end by piping synthetic `Stop` stdin into the script; live confirmation of version-dependent stdin fields happens there. |
| **P — Path** | Install first or judge first? | **Both in 004-01** (the vertical minimum is "install → hook fires → grades → nudges"); then edge paths — fail-open (004-02), re-install/backup (004-03), uninstall/status (004-04). |
| **I — Interface** | What is the stable boundary? | The meta-judge script's **stdin/stdout/exit contract** + the `hooks.Stop[]` entry in `settings.json` + the `hook.py {install,uninstall,status}` CLI. |
| **D — Data** | What data does the hook touch? | stdin: `stop_hook_active` only (minimal coupling). `gate.py --json`: `status` / `composite` / `threshold` / `missing`. `settings.json`: the `hooks.Stop[]` array, merged not clobbered. |
| **R — Rules** | What prevents a session-trapping footgun? | Fail open on env_error; respect `stop_hook_active` (one nudge/sequence); never mutate global settings; back up before mutating; uninstall removes only servo's entry. |

## Slices

- [004-01 — install-and-judge](slice-01-install-and-judge.md)
- [004-02 — fail-open-safety](slice-02-fail-open-safety.md)
- [004-03 — idempotent-install-and-backup](slice-03-idempotent-install-and-backup.md)
- [004-04 — uninstall-and-status](slice-04-uninstall-and-status.md)
- [004-05 — skill-and-dogfood](slice-05-skill-and-dogfood.md)

Five slices, matching the spec 001 / 002 / 003 / 006 cadence (spike-shaped first
slice → one safety/robustness rule per slice → skill surface + dogfood last).
The vertical-value rule holds: after every slice the installer is end-to-end
usable on its own.

## Open questions

- **`settings.json` vs `settings.local.json`.** v1 writes the project-shared
  `settings.json` so the hook is version-controllable and team-shared. A
  per-developer install (`settings.local.json`, gitignored) may be wanted later;
  lean is a `--local` flag in a future slice, not v1.
- **Block vs soft-context default.** v1 defaults to **block**. If interactive
  users find a once-per-sequence block too aggressive, the default could flip to
  `additionalContext` with `--block` opt-in. Resolved provisionally in 004-01;
  revisit after dogfood (004-05).
- **Hint richness.** v1 hint = composite / threshold (+ any `missing`) from
  `gate.py --json`. Surfacing per-component *scores* (so the hint names the
  weakest components on a below-threshold run) needs a spec-002 `gate.py`
  enhancement and is deferred (refinement-todo). Borrowing 003's per-iteration
  prompt-assembly (judge-verdict phrasing) is a further possible enhancement;
  both deferred unless dogfood shows the terse hint is insufficient.
- **`meta-judge.sh` shell portability.** The template is POSIX `sh` + `gate.py`;
  it shells out to `python3`. Whether to depend on `jq` for JSON assembly or
  hand-roll it is a 004-01 implementation call (lean: avoid `jq`, emit the small
  fixed JSON with `printf`, so the hook has zero extra dependencies).
- **Does `install` require a prior servo scaffold?** Lean: yes — `install`
  refuses (env-error style) if `<target>/.servo/install.json` or `oracle.sh` is
  absent, pointing at `/servo:scaffold-init`. Pinned in 004-01.

## Spec-level Definition of Done

- [ ] All five slices DONE (004-01 … 004-05), each reviewed per the spec-workflow
      multi-pass review flow.
- [ ] End-to-end dogfood: install onto a scaffolded fixture target, fire a
      synthetic `Stop` event, observe a block-with-hint on a below-threshold
      oracle and a silent pass on an above-threshold oracle (004-05).
- [ ] [README.md](../../../README.md) skills table: `oracle-hook` row reads
      `DONE` (flipped from `future`).
- [ ] [architecture.md](../../architecture.md): the "Skill split" `future` row
      for `/servo:oracle-hook` is updated to spec 004; a "Meta-judge hook" entry
      is added under "Runtime artifacts" documenting the decision table + the
      `meta-judge.sh` / `settings.json` install model.
- [ ] **ADR-0006** recorded (Accepted) — meta-judge Stop-hook output contract &
      fail-open posture.
- [ ] `.claude-plugin/install-contract.json` lists the new `oracle-hook` skill +
      `templates/meta-judge.sh.template`, and `scripts/verify_install_surfaces.sh`
      passes (spec 007 runtime-install verifier stays green).
- [ ] [docs/specs/README.md](../README.md) status board reflects DONE.
- [ ] Any deferred decisions recorded in [docs/refinement-todo.md](../../refinement-todo.md).

## References

- [Spec 001 — scaffold-init](../001-scaffold-init/spec.md) — provides
  `oracle.sh` + `.servo/install.json` the hook scores.
- [Spec 002 — quality-gate](../002-quality-gate/spec.md) — `gate.py`, the
  truth-source the meta-judge calls (closed 0/1/2 + `--json`).
- [Spec 003 — agent-loop](../003-agent-loop/spec.md) — the headless cousin; the
  hook borrows its retry-hint phrasing ideas and inverts its fail-closed posture.
- [ADR-0002 — gate caller contract](../../decisions/adr-0002-gate-caller-contract.md)
- [ADR-0001 — filesystem-only coupling](../../decisions/adr-0001-reuse-jig-test-detector.md)
- [ROADMAP](../ROADMAP.md) — 004-oracle-hook row + the jig-gap inventory.

## Assumptions

> Risk-gated grounding per the spec-authoring discipline: load-bearing factual
> claims about the `Stop`-hook surface that were established by docs-probe (not
> by an executed live hook) and are confirmed empirically in spike slice 004-01.

- **A1 — `stop_hook_active` semantics.** Assumed: stdin carries
  `stop_hook_active`, true once the hook has already blocked in the current stop
  sequence, and exit-0-when-true reliably prevents a runaway block loop.
  *Confirm in 004-01 against a live `Stop` event.* If absent/unreliable, 004-01's
  fallback is a hook-local block counter keyed on `session_id` written under
  `.servo/hooks/`.
- **A2 — block mechanism.** Assumed: `{"decision":"block","reason":…}` (exit 0)
  causes Claude to continue the turn and shows `reason` to Claude. *Confirm in
  004-01.* Exit-2-with-stderr is the documented equivalent fallback.
- **A3 — richer stdin fields are optional.** `assistant_message`, `stop_reason`,
  and `effort.level` may appear on stdin but are **version-dependent**; v1 does
  not depend on them. No assumption load-bearing.
- **A4 — settings.json `hooks.Stop[]` shape + no matcher.** Assumed correct per
  docs. *Confirm in 004-01* that a hand-written entry of this shape actually
  fires the script.
- **A5 — `$CLAUDE_PROJECT_DIR`** expands to the scaffolded project root at hook
  invocation and equals the gate.py target. *Confirm in 004-01.*
- **A6 — block cap** exists and is bounded (docs: 8). v1 does not depend on the
  exact value (it nudges once per sequence via A1). No assumption load-bearing
  beyond "a cap exists."
