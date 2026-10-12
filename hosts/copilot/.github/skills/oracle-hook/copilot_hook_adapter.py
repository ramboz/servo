#!/usr/bin/env python3
"""copilot_hook_adapter.py — servo's oracle `Stop` → Copilot `agentStop`
input-payload adapter (spec 032, slice 032-04).

Ported from jig's `copilot_hook_adapter.py` (spec 113-04), the **stdin-reshaping
half only**. servo's Copilot plugin package is hook-free (ADR-0038): its one
hook, the oracle `Stop` (meta-judge), is installed *target-side* by
`skills/oracle-hook/hook.py --host copilot`, which ships this adapter into the
consuming repo's `.servo/hooks/` and wires a Copilot `agentStop` hook that runs:

    python3 .servo/hooks/copilot_hook_adapter.py Stop ".servo/hooks/meta-judge.sh"

Why this exists: servo's `meta-judge.sh` reads Claude-shaped stdin — snake_case
`stop_hook_active` — and locates the project via the `CLAUDE_PROJECT_DIR`
environment variable. Copilot's `agentStop` sends camelCase stdin
(`{sessionId, timestamp, cwd, transcriptPath, stopReason, stop_hook_active}` —
spike 032-01) and exposes **no** `CLAUDE_PROJECT_DIR`-analogous env var. This
adapter sits between Copilot and the UNMODIFIED meta-judge script: it reads
Copilot's stdin JSON, reshapes it into the snake_case the meta-judge expects,
exports `CLAUDE_PROJECT_DIR` for the child from the payload's `cwd`, invokes the
target script with the reshaped JSON on stdin, and forwards its stdout + exit
code **verbatim** — so the `{"decision":"block","reason":…}` body the meta-judge
emits (identical vocabulary in both hosts) re-drives the next turn exactly as
Claude's `Stop` hook does.

What is DELIBERATELY NOT ported from jig (servo is hook-free):

  * the SessionStart root-publisher half (`merge_root_context`) — servo ships no
    SessionStart carrier hook; `$SERVO_ROOT` is resolved by a standalone locator
    instead (bug 036 / `scripts/servo_root.py`);
  * the enforcing (`--enforce` / `permissionDecision` deny) mode — that is jig's
    `preToolUse` permissions-floor gate; servo has no enforcing hook. servo's one
    hook is `Stop`→`agentStop`, whose decision is expressed in stdout (not the
    exit code), so a single verbatim-forward path covers it.

Field reshaping (only what servo's agentStop path exercises — the meta-judge
reads `stop_hook_active`; `session_id`/`transcript_path` are forwarded for
parity with Claude's payload shape and any future consumer):

    sessionId          -> session_id
    transcriptPath     -> transcript_path
    stop_hook_active   -> stop_hook_active   (Copilot already sends it snake_case;
                                              the meta-judge's runaway guard reads it)
    cwd / workingDirectory -> exported as the CLAUDE_PROJECT_DIR env var for the
                              child (not a payload key), only when not already set
    (from adapter argv[0]) -> hook_event_name = the Claude event name ("Stop")

Fail-open everywhere (this is a `Stop` hook — it must never trap a live
session): any translation error forwards the ORIGINAL stdin bytes unchanged; a
malformed invocation or a spawn failure returns exit 0 rather than propagating
an error to Copilot's hook runner. A missing nudge is the worst-case outcome,
never a blocked session. This mirrors the meta-judge's own fail-open posture.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional


def translate_payload(raw: bytes, claude_event: str) -> bytes:
    """Return the reshaped, snake_case JSON (as bytes) servo's `meta-judge.sh`
    expects, translated from Copilot's camelCase `agentStop` stdin JSON. On ANY
    error, returns `raw` unchanged (fail-open — see the module docstring)."""
    try:
        payload = json.loads(raw.decode("utf-8") or "{}")
        if not isinstance(payload, dict):
            return raw

        out: dict = {"hook_event_name": claude_event}

        if "sessionId" in payload:
            out["session_id"] = payload["sessionId"]

        # The load-bearing field for the meta-judge's runaway guard. Copilot's
        # agentStop already spells it snake_case, so this is a passthrough.
        if "stop_hook_active" in payload:
            out["stop_hook_active"] = payload["stop_hook_active"]

        if "transcriptPath" in payload:
            out["transcript_path"] = payload["transcriptPath"]

        return json.dumps(out).encode("utf-8")
    except Exception:
        return raw


def project_dir_from_payload(raw: bytes) -> Optional[str]:
    """Return the project directory from a Copilot payload — `cwd` (the key
    agentStop uses) preferred, `workingDirectory` (the base hook-input shape) as
    a fallback — or `None` on any error or absence. The caller exports it as
    `CLAUDE_PROJECT_DIR`; on `None` the meta-judge's own `${CLAUDE_PROJECT_DIR:-}`
    default then fails open (nothing to score), exactly as intended."""
    try:
        payload = json.loads(raw.decode("utf-8") or "{}")
        if not isinstance(payload, dict):
            return None
        for key in ("cwd", "workingDirectory"):
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value
        return None
    except Exception:
        return None


def _interpreter_for(script_path: str) -> str:
    """The interpreter used to run `script_path`: `python3` for a `.py` target,
    `bash` for everything else. servo's only target today is the `.sh`
    meta-judge, but the split keeps the port faithful to jig and ready for a
    future `.py` hook without depending on the target's executable bit."""
    return "python3" if script_path.endswith(".py") else "bash"


def main(argv: list) -> int:
    args = argv[1:]
    if len(args) < 2:
        # Fail-open: a malformed invocation must not raise to Copilot's hook
        # runner. Nothing meaningful to run.
        return 0
    claude_event, script_path = args[0], args[1]

    raw = sys.stdin.buffer.read()
    translated = translate_payload(raw, claude_event)

    env = dict(os.environ)
    project_dir = project_dir_from_payload(raw)
    if project_dir and "CLAUDE_PROJECT_DIR" not in env:
        env["CLAUDE_PROJECT_DIR"] = project_dir

    # Fail-open on a missing target (a packaging error): resolve the script
    # path against the same CWD the child would run from (Copilot runs
    # repo-committed hooks from the repo root, so the relative
    # `.servo/hooks/meta-judge.sh` lands there). A missing meta-judge must not
    # forward `bash`'s own non-zero "no such file" exit to Copilot — a Stop
    # hook that traps the session on a packaging bug is worse than no hook.
    if not Path(script_path).is_file():
        return 0

    try:
        # No capture: the child's stdout/stderr inherit this process's, so the
        # meta-judge's `{"decision":"block",...}` body reaches Copilot verbatim.
        # The gate decision travels in that stdout body, NEVER in the exit code.
        subprocess.run(
            [_interpreter_for(script_path), script_path], input=translated, env=env
        )
    except Exception:
        # Fail-open: a spawn failure (e.g. an unresolved script path) must never
        # look like a blocking error to Copilot — a Stop hook that traps the
        # session on a packaging bug is worse than no hook. Mirrors the
        # meta-judge's own never-block-on-breakage contract.
        return 0
    # ADVISORY posture (jig-faithful): this is not an `--enforce` hook, so the
    # adapter always exits 0 and lets the child's stdout `{"decision":"block",
    # "reason":…}` carry the gate decision. Forwarding a non-zero child exit
    # could trap the Copilot session — the exact "a Stop hook must never trap
    # the session" invariant this adapter exists to uphold. (servo's meta-judge
    # exits 0 today; returning 0 unconditionally keeps that a guarantee, not a
    # coincidence.)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
