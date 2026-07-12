#!/usr/bin/env python3
"""servo oracle-hook — install/uninstall/report a Claude Code ``Stop`` hook (the
"meta-judge") that scores each assistant turn against the scaffolded oracle via
``gate.py`` and feeds a structured retry hint back when it is below threshold.

Spec 004. Slice 004-01 ships ``install`` + the meta-judge script template;
004-02 the fail-open env-error reporting; 004-03 makes ``install`` safe to
re-run against a populated ``settings.json`` (idempotent merge + backup); 004-04
adds ``uninstall`` (reverse the settings surgery, leave the script) + ``status``.

Usage::

    python3 hook.py install   <target> [--timeout N]
    python3 hook.py uninstall <target>
    python3 hook.py status    <target> [--json]

Exit codes — one closed contract shared by all three subcommands:

    0  success: installed / uninstalled (incl. an idempotent no-op) / status
       reported a valid state (``installed`` | ``not_installed`` | ``inconsistent``).
    2  env-error: a one-line ``oracle-hook: ... reason=<code>`` is emitted (target
       missing or not a directory; ``settings.json`` unparseable — or, for the
       mutating ``install`` / ``uninstall``, wrong-shaped; ``install`` on an
       unscaffolded target). There is no exit 1 — the below-threshold signal is
       ``gate.py``'s contract, not the installer's.
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


class _SettingsRefusal(Exception):
    """Raised by :func:`_load_settings` when ``settings.json`` cannot be used
    safely. Carries the env-error ``reason`` + a human message for ``_refuse``."""

    def __init__(self, msg: str, reason: str):
        super().__init__(msg)
        self.msg = msg
        self.reason = reason


def _load_settings(settings_path: Path, *, validate_structure: bool) -> tuple[dict, bool]:
    """Parse ``settings.json`` → ``(settings, had_content)``.

    ``had_content`` is True only when a non-empty, parseable JSON *object*
    existed — an empty / whitespace-only file is an empty config with nothing to
    preserve. Raises :class:`_SettingsRefusal` on unparseable JSON or a
    non-object root. When ``validate_structure`` is set (the mutating callers,
    ``install`` / ``uninstall``) an odd-shaped ``hooks`` / ``hooks.Stop`` also
    refuses — a mutation must never clobber, or crash into, a structure it does
    not understand. ``status`` (read-only) passes False and guards its own reads.
    """
    settings: dict = {}
    had_content = False
    if settings_path.is_file():
        raw = settings_path.read_text()
        if raw.strip():
            try:
                settings = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise _SettingsRefusal(
                    f"{settings_path} is not valid JSON", "settings_malformed"
                ) from exc
            if not isinstance(settings, dict):
                raise _SettingsRefusal(
                    f"{settings_path} is not a JSON object", "settings_malformed"
                )
            had_content = True
    if validate_structure:
        hooks = settings.get("hooks")
        if hooks is not None and not isinstance(hooks, dict):
            raise _SettingsRefusal(
                f'{settings_path}: "hooks" is not a JSON object', "settings_malformed"
            )
        if isinstance(hooks, dict):
            stop = hooks.get("Stop")
            if stop is not None and not isinstance(stop, list):
                raise _SettingsRefusal(
                    f'{settings_path}: "hooks.Stop" is not a JSON array', "settings_malformed"
                )
    return settings, had_content


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
    # AC4 (004-03): refuse before any write on unparseable / wrong-shaped content
    # — never overwrite (or back up) something we can't safely merge into.
    try:
        settings, had_content = _load_settings(settings_path, validate_structure=True)
    except _SettingsRefusal as e:
        return _refuse(f"{e.msg}; refusing to overwrite", reason=e.reason)

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


def cmd_uninstall(target: Path) -> int:
    settings_path = target / ".claude" / "settings.json"
    try:
        settings, _ = _load_settings(settings_path, validate_structure=True)
    except _SettingsRefusal as e:
        return _refuse(f"{e.msg}; refusing to modify", reason=e.reason)

    hooks = settings.get("hooks")
    stop = hooks.get("Stop") if isinstance(hooks, dict) else None
    if not isinstance(stop, list) or not any(_entry_is_servo(e) for e in stop):
        # AC3: no servo Stop entry present (or no settings.json at all) → an
        # idempotent no-op success; never rewrite unrelated content, never back up.
        sys.stdout.write("oracle-hook: no servo Stop hook to remove (no change)\n")
        return EXIT_OK

    # AC4: back up the pre-mutation settings.json before removing servo's entry.
    shutil.copyfile(settings_path, settings_path.parent / BACKUP_NAME)

    # AC1: remove only servo's entries; if that empties the array, clean up the
    # dead structure (no `Stop: []` / `hooks: {}` left behind). AC2: the
    # meta-judge.sh script is deliberately left on disk (it may be customized).
    remaining = [e for e in stop if not _entry_is_servo(e)]
    if remaining:
        hooks["Stop"] = remaining
    else:
        del hooks["Stop"]
        if not hooks:
            del settings["hooks"]
    settings_path.write_text(json.dumps(settings, indent=2) + "\n")

    sys.stdout.write("oracle-hook: removed servo Stop hook (meta-judge.sh left on disk)\n")
    return EXIT_OK


def cmd_status(target: Path, *, as_json: bool = False) -> int:
    settings_path = target / ".claude" / "settings.json"
    script = target / ".servo" / "hooks" / "meta-judge.sh"
    script_present = script.is_file()

    # Read-only: refuse only on unparseable JSON. An odd-shaped (but valid-JSON)
    # hooks/Stop is reported leniently as "no servo entry" rather than erroring —
    # inspection need not understand a structure it isn't going to mutate.
    try:
        settings, _ = _load_settings(settings_path, validate_structure=False)
    except _SettingsRefusal as e:
        return _refuse(f"{e.msg}; cannot determine status", reason=e.reason)

    hooks = settings.get("hooks")
    stop = hooks.get("Stop") if isinstance(hooks, dict) else None
    entry_present = isinstance(stop, list) and any(_entry_is_servo(e) for e in stop)

    # AC5: three distinct, machine-readable states. `inconsistent` covers either
    # XOR case (entry without script — the broken case; or script without entry —
    # the post-uninstall orphan); the booleans below disambiguate which.
    if entry_present and script_present:
        state = "installed"
    elif not entry_present and not script_present:
        state = "not_installed"
    else:
        state = "inconsistent"

    if as_json:
        sys.stdout.write(json.dumps({
            "schema_version": 1,
            "state": state,
            "entry_present": entry_present,
            "script_present": script_present,
            "settings_path": str(settings_path),
            "script_path": str(script),
        }) + "\n")
    else:
        sys.stdout.write(
            f"oracle-hook: {state} "
            f"(Stop entry: {'present' if entry_present else 'absent'}, "
            f"meta-judge.sh: {'present' if script_present else 'absent'})\n"
        )
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

    p_uninstall = sub.add_parser(
        "uninstall", help="remove servo's Stop hook entry (leaves the script on disk)"
    )
    p_uninstall.add_argument("target", help="path to the project")

    p_status = sub.add_parser(
        "status", help="report whether the meta-judge Stop hook is installed"
    )
    p_status.add_argument("target", help="path to the project")
    p_status.add_argument(
        "--json", action="store_true", dest="as_json",
        help="emit machine-readable JSON instead of a human-readable line",
    )

    args = parser.parse_args(argv)

    target = Path(args.target).expanduser().resolve()
    # Shared precondition for the whole CLI surface (AC6): the target must exist.
    if not target.is_dir():
        return _refuse(
            f"target not found or not a directory: {target}", reason="target_missing"
        )

    if args.cmd == "install":
        return cmd_install(target, timeout=args.timeout)
    if args.cmd == "uninstall":
        return cmd_uninstall(target)
    if args.cmd == "status":
        return cmd_status(target, as_json=args.as_json)
    return EXIT_ENV_ERROR  # unreachable: subparser is required


if __name__ == "__main__":
    raise SystemExit(main())
