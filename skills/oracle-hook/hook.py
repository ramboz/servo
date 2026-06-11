#!/usr/bin/env python3
"""servo oracle-hook — install/uninstall/report a Claude Code ``Stop`` hook (the
"meta-judge") that scores each assistant turn against the scaffolded oracle via
``gate.py`` and feeds a structured retry hint back when it is below threshold.

Spec 004. Slice 004-01 ships ``install`` + the meta-judge script template;
004-02 the fail-open env-error reporting; 004-03 makes ``install`` safe to
re-run against a populated ``settings.json`` (idempotent merge + backup).
``uninstall`` / ``status`` (004-04) follow in a later slice.

Usage::

    python3 hook.py install <target> [--timeout N]
"""
from __future__ import annotations

import argparse
import json
import shutil
import stat
import sys
from pathlib import Path

# Stable marker identifying servo's `Stop` entry — the installed command always
# contains it, so idempotency (004-03) and uninstall (004-04) can find exactly
# servo's entry without touching the user's other hooks.
SERVO_HOOK_REL = ".servo/hooks/meta-judge.sh"
HOOK_COMMAND = '"$CLAUDE_PROJECT_DIR"/' + SERVO_HOOK_REL
DEFAULT_TIMEOUT = 60
# Single rolling backup of the last pre-mutation settings.json (004-03 AC3).
BACKUP_NAME = "settings.json.servo-bak"

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
    # --- validate first (no writes until everything checks out) ------------ #
    # Every refusal below returns before any file is touched, so a rejected
    # install is a true no-op — it never half-writes and never backs up.
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
    had_content = False  # True iff a non-empty, parseable settings.json existed
    if settings_path.is_file():
        raw = settings_path.read_text()
        if raw.strip():
            try:
                settings = json.loads(raw)
            except json.JSONDecodeError:
                # AC4: never overwrite (or back up) unparseable user content.
                return _refuse(
                    f"{settings_path} is not valid JSON; refusing to overwrite",
                    reason="settings_malformed",
                )
            if not isinstance(settings, dict):
                return _refuse(
                    f"{settings_path} is not a JSON object; refusing to overwrite",
                    reason="settings_malformed",
                )
            had_content = True
        # An empty / whitespace-only file is treated as an empty config: there
        # is no user content to preserve, so it installs cleanly with no backup.

    # Structural pre-validation: a valid-JSON file whose `hooks` container is the
    # wrong shape is refused rather than clobbered or crashed into — the AC4
    # posture extended to structure, kept before any write so refusal is a no-op.
    existing_hooks = settings.get("hooks")
    if existing_hooks is not None and not isinstance(existing_hooks, dict):
        return _refuse(
            f'{settings_path}: "hooks" is not a JSON object; refusing to overwrite',
            reason="settings_malformed",
        )
    if isinstance(existing_hooks, dict):
        existing_stop = existing_hooks.get("Stop")
        if existing_stop is not None and not isinstance(existing_stop, list):
            return _refuse(
                f'{settings_path}: "hooks.Stop" is not a JSON array; refusing to overwrite',
                reason="settings_malformed",
            )

    template = _templates_root() / "meta-judge.sh.template"
    body = template.read_text().replace("__GATE_PY__", _resolve_gate_py(target))

    # --- writes ------------------------------------------------------------ #
    # Place the meta-judge script, but never clobber a user-customized one: write
    # only when absent (this also self-heals a deleted script). The body is
    # otherwise deterministic, so re-install is a no-op here.
    hooks_dir = target / ".servo" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    script = hooks_dir / "meta-judge.sh"
    if not script.exists():
        script.write_text(body)
        script.chmod(script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    # AC1/AC2/AC5: merge servo's Stop entry idempotently — preserve all other
    # keys, hook events, and Stop entries; identify servo's by its stable marker.
    hooks = settings.setdefault("hooks", {})
    stop = hooks.setdefault("Stop", [])
    if any(_entry_is_servo(e) for e in stop):
        # Servo's entry is already present — a true no-op on settings.json (no
        # rewrite) and, per AC3, no backup rewrite either.
        sys.stdout.write(f"oracle-hook: Stop hook already installed -> {script}\n")
        return EXIT_OK

    # AC3: back up the prior settings.json before the first mutation — only when
    # there is real user content to preserve (a fresh or empty file gets none).
    if had_content:
        shutil.copyfile(settings_path, settings_path.parent / BACKUP_NAME)

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
