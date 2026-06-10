#!/usr/bin/env python3
"""servo oracle-hook — install/uninstall/report a Claude Code ``Stop`` hook (the
"meta-judge") that scores each assistant turn against the scaffolded oracle via
``gate.py`` and feeds a structured retry hint back when it is below threshold.

Spec 004. Slice 004-01 ships ``install`` + the meta-judge script template.
Fail-open env-error reporting (004-02), idempotency + settings backup (004-03),
and ``uninstall`` / ``status`` (004-04) follow in later slices.

Usage::

    python3 hook.py install <target> [--timeout N]
"""
from __future__ import annotations

import argparse
import json
import stat
import sys
from pathlib import Path

# Stable marker identifying servo's `Stop` entry — the installed command always
# contains it, so idempotency (004-03) and uninstall (004-04) can find exactly
# servo's entry without touching the user's other hooks.
SERVO_HOOK_REL = ".servo/hooks/meta-judge.sh"
HOOK_COMMAND = '"$CLAUDE_PROJECT_DIR"/' + SERVO_HOOK_REL
DEFAULT_TIMEOUT = 60

EXIT_OK = 0
EXIT_ENV_ERROR = 2


def _here() -> Path:
    return Path(__file__).resolve()


def _templates_root() -> Path:
    """servo's ``templates/`` dir (skills/oracle-hook/ → ../../templates)."""
    return _here().parents[2] / "templates"


def _servo_gate_py() -> Path:
    """servo's own ``gate.py`` (skills/oracle-hook/ → ../quality-gate/gate.py)."""
    return _here().parents[1] / "quality-gate" / "gate.py"


def _resolve_gate_py(target: Path) -> str:
    """The ``gate.py`` reference baked into the installed script.

    Prefer a runtime copy vendored into the target (portable, relative to
    ``$CLAUDE_PROJECT_DIR``); otherwise bake servo's own absolute ``gate.py``
    path. The installed script lets ``SERVO_GATE_PY`` override either.
    """
    vendored = target / ".claude" / "skills" / "servo-quality-gate" / "gate.py"
    if vendored.is_file():
        return '"$CLAUDE_PROJECT_DIR"/.claude/skills/servo-quality-gate/gate.py'
    return str(_servo_gate_py())


def _refuse(msg: str, *, reason: str) -> int:
    sys.stderr.write(f"oracle-hook: {msg}\n")
    sys.stdout.write(f"oracle-hook: status=env_error reason={reason}\n")
    return EXIT_ENV_ERROR


def _servo_stop_entry(timeout: int) -> dict:
    return {"hooks": [{"type": "command", "command": HOOK_COMMAND, "timeout": timeout}]}


def _entry_is_servo(entry: object) -> bool:
    if not isinstance(entry, dict):
        return False
    for h in entry.get("hooks", []):
        if isinstance(h, dict) and SERVO_HOOK_REL in str(h.get("command", "")):
            return True
    return False


def cmd_install(target: Path, *, timeout: int = DEFAULT_TIMEOUT) -> int:
    # --- validate first (no writes until everything checks out, AC3) ------- #
    if not (target / ".servo" / "install.json").is_file():
        return _refuse(
            f".servo/install.json not found at {target}; run /servo:scaffold-init first",
            reason="manifest_missing",
        )
    if not (target / "oracle.sh").is_file():
        return _refuse(
            f"oracle.sh not found at {target}; run /servo:scaffold-init first",
            reason="oracle_missing",
        )

    settings_path = target / ".claude" / "settings.json"
    settings: dict = {}
    if settings_path.is_file():
        try:
            settings = json.loads(settings_path.read_text())
        except json.JSONDecodeError:
            # Comprehensive backup + merge is 004-03; here we refuse rather than
            # clobber unparseable user content.
            return _refuse(
                f"{settings_path} is not valid JSON; refusing to overwrite",
                reason="settings_malformed",
            )
        if not isinstance(settings, dict):
            return _refuse(
                f"{settings_path} is not a JSON object; refusing to overwrite",
                reason="settings_malformed",
            )

    template = _templates_root() / "meta-judge.sh.template"
    body = template.read_text().replace("__GATE_PY__", _resolve_gate_py(target))

    # --- writes ------------------------------------------------------------ #
    # AC1: place the meta-judge script with the executable bit set.
    hooks_dir = target / ".servo" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    script = hooks_dir / "meta-judge.sh"
    script.write_text(body)
    script.chmod(script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    # AC2: register the Stop hook in <target>/.claude/settings.json.
    hooks = settings.setdefault("hooks", {})
    stop = hooks.setdefault("Stop", [])
    if not any(_entry_is_servo(e) for e in stop):
        stop.append(_servo_stop_entry(timeout))
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(settings, indent=2) + "\n")

    sys.stdout.write(f"oracle-hook: installed Stop hook -> {script}\n")
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="hook.py",
        description="Install/uninstall/report servo's meta-judge Stop hook.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_install = sub.add_parser("install", help="install the meta-judge Stop hook")
    p_install.add_argument("target", help="path to the servo-scaffolded project")
    p_install.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f"hook command timeout in seconds (default {DEFAULT_TIMEOUT})",
    )
    args = parser.parse_args(argv)

    target = Path(args.target).expanduser().resolve()
    if args.cmd == "install":
        if not target.is_dir():
            return _refuse(
                f"target not found or not a directory: {target}",
                reason="target_missing",
            )
        return cmd_install(target, timeout=args.timeout)
    return EXIT_ENV_ERROR  # unreachable: subparser is required


if __name__ == "__main__":
    raise SystemExit(main())
