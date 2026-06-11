---
name: servo:oracle-hook
description: |
  Install, uninstall, or report the status of servo's meta-judge `Stop` hook in
  a target project. The installed hook scores every assistant turn against the
  scaffolded oracle (via `gate.py`) and blocks the stop with a structured retry
  hint when the oracle is below threshold — the interactive cousin of
  `/servo:agent-loop`. Installing it mutates `<target>/.claude/settings.json`,
  so it is a **Tier-2** surface: offered explicitly, never auto-installed.

  Fire this skill when the user wants to:

    - "install the oracle hook" / "add the Stop hook" / "set up the meta-judge"
    - "uninstall the oracle hook" / "remove the meta-judge" / "remove the Stop hook"
    - "is the oracle hook installed?" / "oracle hook status" / "check the hook"

  Do NOT fire on:

    - "run the oracle" / "score this code" / "what's the oracle score?" — that's
      `/servo:quality-gate` (a one-shot score, not the hook installer).
    - "iterate on this" / "run an agent loop" / "headless loop" — that's
      `/servo:agent-loop` (the headless cousin; this hook is the interactive one).
    - "set up servo" / "scaffold the oracle" / "install servo" — that's
      `/servo:scaffold-init`; the hook refuses to install until the target is
      servo-scaffolded.
    - "fix the failing test" / "review my code" — out of scope. The hook installs
      and reports; it does not modify code or review it.

  When in doubt, ask which servo skill the user means rather than invent a
  trigger match.
---

# /servo:oracle-hook

Install (and cleanly uninstall) a Claude Code **`Stop` hook** — the **meta-judge** — that runs the scaffolded oracle after every assistant turn and feeds a **structured retry hint** back to Claude when the oracle is below threshold. It is the deterministic, oracle-scored replacement for ad-hoc transcript-regex "looks done" Stop-hook scans: the hint is real evidence (composite vs threshold), not a guess.

The helper is at `${CLAUDE_PLUGIN_ROOT}/skills/oracle-hook/hook.py`. It manages two artifacts in the target:

```
<target>/
├── .claude/settings.json   # hooks.Stop[] entry added/removed by install/uninstall
│                           # backed up to settings.json.servo-bak before first mutation
└── .servo/hooks/meta-judge.sh   # the hook script; project-owned & customizable;
                                 #   survives uninstall
```

## When to use this skill

Use when the user wants to **install / uninstall / report** the Stop hook on an already-scaffolded target. Three neighbours it is *not*:

- **`/servo:quality-gate`** runs the oracle once and prints a score. The hook *installs a thing that runs it for you* on every turn-stop.
- **`/servo:agent-loop`** is the **headless** cousin — it subprocesses `claude -p` N times unattended and fails **closed** (every guardrail halts the loop). This hook is the **interactive** cousin — a human is in the session — and it fails **open** (see below).
- **`/servo:scaffold-init`** sets up the oracle. The hook refuses to install until that has happened.

## Tier-2: explicit opt-in only

Installing the hook **mutates `<target>/.claude/settings.json`** — a higher-risk, project-shared, version-controlled file. Per [architecture.md](../../docs/architecture.md) "Tier model", that makes `/servo:oracle-hook` a **Tier-2** surface: **offered explicitly, never auto-installed**. Before mutating, `install` **backs up** the prior `settings.json` to `settings.json.servo-bak` (byte-faithful, single rolling backup; skipped when there was no prior content). The merge is **non-clobbering**: it preserves unrelated top-level keys, other hook events, and any Stop hooks the user already has.

Surface this to the user before running `install`, so they are not surprised: it edits a tracked settings file (backed up), and the installed hook will start nudging on below-threshold turn-stops.

## The meta-judge decision table (what the installed hook does)

The installed `meta-judge.sh` is a thin, deterministic decision table over `gate.py`'s result. Its output contract is frozen as **ADR-0006**:

| Situation | Hook action | Why |
|---|---|---|
| `stop_hook_active` is true (or stdin is unparseable) | exit 0, silent — gate never runs | Already nudged this stop sequence; an indeterminate guard biases toward never trapping the session |
| oracle **passes** (`gate.py` exit 0) | exit 0, silent | Work clears the bar; let the turn stop |
| oracle **below threshold** (`gate.py` exit 1) | **block** with a structured `reason` hint naming composite + threshold (+ any `missing`) | The meta-judge's whole point — keep working with real evidence |
| oracle **env-error** (`gate.py` exit 2), or an uninvocable / unparseable gate | exit 0 + a one-line `systemMessage` warning to the **user** | **Fail open** — a broken oracle must never trap a live session |

Two consequences worth stating up front:

- **Fail open.** Unlike `/servo:agent-loop`'s fail-closed brakes, a misconfigured or slow oracle here **never blocks** — it warns the user and lets the stop proceed. A `Stop` hook that can deadlock a human's session is worse than no hook at all.
- **At most one nudge per stop sequence.** The hook respects `stop_hook_active`, so it blocks **once** then lets the next stop through — well inside Claude Code's consecutive-block cap. (Aggressive block-until-pass is a documented project customization, not the default.)

## Block vs soft-context (a project-owned knob)

A `Stop` hook can feed text back two mutually-exclusive ways:

- **block** — `{"decision":"block","reason":"<hint>"}`: the turn does **not** end; Claude keeps working *now*. This is the v1 default — it is the only mode that actually makes the agent keep working.
- **soft context** — `{"hookSpecificOutput":{"hookEventName":"Stop","additionalContext":"<hint>"}}`: the turn **ends**; the hint is injected as a system reminder on the *next* turn. Non-blocking.

v1 ships **block**. The softer `additionalContext` mode is a **project-owned** knob: the installed `meta-judge.sh` belongs to the project after install and can be edited to switch modes (re-install never clobbers a customized script). Per the "Project vs servo-core split", the project owns the hook event choice, the hint phrasing, and the block-vs-soft-context mode; servo owns the script template and the `settings.json` mutation + backup machinery.

## Three subcommands

One closed exit contract is shared by all three: **0** = success (installed / uninstalled / an idempotent no-op / a valid status), **2** = env-error (a one-line `oracle-hook: … reason=<code>` is emitted). There is **no exit 1** — below-threshold is `gate.py`'s signal, not the installer's.

### `hook.py install <target>` — install the Stop hook

Drops `meta-judge.sh` into `<target>/.servo/hooks/` and registers a `Stop` hook in `<target>/.claude/settings.json` (creating `.claude/` + `settings.json` if absent). **Idempotent**: re-running yields exactly one servo Stop entry, never a duplicate, and never rewrites the backup on a no-op. Refuses (exit 2, no half-write, no backup) if the target is not servo-scaffolded or `settings.json` is unparseable / wrong-shaped.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/oracle-hook/hook.py" install <target>

# longer hook timeout (seconds; default 60)
python3 "${CLAUDE_PLUGIN_ROOT}/skills/oracle-hook/hook.py" install <target> --timeout 90
```

### `hook.py uninstall <target>` — remove servo's Stop entry

Reverses the `settings.json` surgery: removes **only** servo's entry (matched by a stable marker), backs up before mutating, cleans up an emptied `Stop` / `hooks` structure, and **leaves `meta-judge.sh` on disk** (it may be customized). A no-op success when there is no servo entry (or no settings file at all).

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/oracle-hook/hook.py" uninstall <target>
```

### `hook.py status <target>` — report install state

Reports one of three machine-readable states. Read-only; refuses only on unparseable JSON.

| State | Meaning |
|---|---|
| `installed` | Stop entry **and** `meta-judge.sh` both present |
| `not_installed` | neither present |
| `inconsistent` | exactly one present — either an entry with no script (broken), or a script with no entry (the orphan left after `uninstall`) |

```bash
# human-readable
python3 "${CLAUDE_PLUGIN_ROOT}/skills/oracle-hook/hook.py" status <target>

# machine-readable (schema_version, state, entry_present, script_present)
python3 "${CLAUDE_PLUGIN_ROOT}/skills/oracle-hook/hook.py" status <target> --json
```

## Options

| Flag | Applies to | What it does |
|---|---|---|
| `--timeout <seconds>` | `install` | The `Stop` hook command timeout written into `settings.json` (default 60). Independently, the installed script bounds its own `gate.py` call via `SERVO_META_JUDGE_GATE_TIMEOUT` (default 45s) — a separate knob, not derived from `--timeout`. At the defaults the gate bound (45s) fires before the hook timeout (60s), so a hung oracle yields a clean fail-open env-error rather than an abrupt hook kill; if you lower `--timeout` below 45, lower `SERVO_META_JUDGE_GATE_TIMEOUT` to keep that ordering. |
| `--json` | `status` | Emit one-line JSON (`schema_version=1`) instead of the human-readable line. |

## Exit contract & refusal handling

The closed `{0, 2}` contract means a refusal is exit 2 with a `reason`. **Do NOT silently retry** — surface the message verbatim to the user and offer the matching recovery.

| `reason` | Meaning | Recovery to suggest |
|---|---|---|
| `target_missing` | Target path absent or not a directory | Confirm the path; check the working directory for a relative path. |
| `manifest_missing` | `.servo/install.json` absent — target not servo-scaffolded | Run `/servo:scaffold-init` on the target first. |
| `oracle_missing` | `oracle.sh` absent (manifest present) | Re-scaffold with `/servo:scaffold-init` (`--force`). |
| `settings_malformed` | `settings.json` is not valid JSON, or `hooks` / `hooks.Stop` is the wrong shape | Surface verbatim; inspect `<target>/.claude/settings.json`. `install` / `uninstall` refuse before any write or backup — nothing was touched. |

## Q&A before installing

Confirm these before running `install` (ask only what the user hasn't already answered):

1. **Which target?** The path to the project to install the hook into. All three subcommands take it as the positional argument.
2. **Is it servo-scaffolded first?** The hook scores `<target>/oracle.sh` via `gate.py`, so the target must be **servo-scaffolded first** (`.servo/install.json` + `oracle.sh`). `install` refuses with `manifest_missing` / `oracle_missing` otherwise — recover with `/servo:scaffold-init`.
3. **Block or soft-context?** v1 installs **block** mode (Claude keeps working now). If the user wants the non-blocking next-turn `additionalContext` mode instead, install then edit the project-owned `meta-judge.sh`.
4. **How do I undo it?** `hook.py uninstall <target>` removes servo's `settings.json` entry (backed up first) and leaves the script on disk. Re-install is idempotent.
5. **How do I check it later?** `hook.py status <target>` reports `installed` / `not_installed` / `inconsistent` (use `--json` for a script). An `inconsistent` result means the entry and the script disagree — e.g. the orphaned script left after `uninstall`.

## Examples

**Install onto a scaffolded target**:

```
user: add the Stop hook to my project so it nudges when the oracle fails
assistant: [confirms the target is servo-scaffolded; notes this is Tier-2 — it edits
            settings.json, backed up first]
        → python3 .../hook.py install /path/to/repo
        → "oracle-hook: installed Stop hook -> /path/to/repo/.servo/hooks/meta-judge.sh"
        → exit 0
```

**Check status (JSON)**:

```
user: is the oracle hook installed?
assistant: → python3 .../hook.py status /path/to/repo --json
        → {"schema_version": 1, "state": "installed", "entry_present": true,
           "script_present": true, ...}
```

**Uninstall**:

```
user: remove the meta-judge hook
assistant: → python3 .../hook.py uninstall /path/to/repo
        → "oracle-hook: removed servo Stop hook (meta-judge.sh left on disk)"
        → exit 0
assistant: [notes status is now `inconsistent` — the script is left on disk by design;
            delete .servo/hooks/meta-judge.sh to reach `not_installed`]
```

**Refusal — target not scaffolded**:

```
assistant: → python3 .../hook.py install /path/to/repo
        stderr: oracle-hook: .servo/install.json not found at /path/to/repo; run /servo:scaffold-init first
        stdout: oracle-hook: status=env_error reason=manifest_missing
assistant: [surfaces verbatim; offers to run /servo:scaffold-init; does NOT silently retry]
```

## After install

Nothing else runs now — the hook fires on the *next* turn-stop in an interactive Claude Code session in that target. The first below-threshold stop is blocked once with an evidence-backed hint; an env-error warns the user and lets the stop through. The installed `meta-judge.sh` is the project's to customize; `uninstall` reverses only the `settings.json` entry.
