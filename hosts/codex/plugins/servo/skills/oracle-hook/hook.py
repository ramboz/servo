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

# --- Copilot host (slice 032-04, ADR-0038) ------------------------------- #
# servo's Copilot plugin package is hook-free; its one hook — the oracle `Stop`
# (meta-judge) — is installed *target-side* here as a Copilot `agentStop` hook,
# via a ported `copilot_hook_adapter.py` that reshapes Copilot's camelCase stdin
# into the snake_case the meta-judge reads and exports `CLAUDE_PROJECT_DIR` from
# the payload's `cwd` (Copilot sets no such env var).
#
# Mapped-or-unmappable hook inventory (ADR-0038 invariant, AC3): servo's ENTIRE
# hook set, enumerated so a future added hook forces a new entry here (and a new
# row in docs/architecture.md) rather than degrading silently. Today: one
# mapped entry `Stop→agentStop` (identical `{"decision":"block","reason":…}`
# output vocabulary in both hosts), empty residual.
CLAUDE_HOOK_EVENT = "Stop"  # the single Claude hook event servo installs
CLAUDE_TO_COPILOT_HOOK_EVENTS = {CLAUDE_HOOK_EVENT: "agentStop"}
COPILOT_HOOK_RESIDUAL: tuple[str, ...] = ()  # source hooks with no Copilot event

COPILOT_HOOK_EVENT = CLAUDE_TO_COPILOT_HOOK_EVENTS[CLAUDE_HOOK_EVENT]  # "agentStop"
# The Copilot hook config lives in the *consuming repo's* `.github/hooks/`; the
# adapter + meta-judge live in `.servo/hooks/`. Copilot runs repo-committed
# hooks from the repo root, so the `bash` command's paths are repo-root
# relative.
COPILOT_HOOK_CONFIG_REL = ".github/hooks/servo-oracle.json"
COPILOT_ADAPTER_NAME = "copilot_hook_adapter.py"
COPILOT_ADAPTER_REL = ".servo/hooks/" + COPILOT_ADAPTER_NAME
# `python3 .servo/hooks/copilot_hook_adapter.py Stop ".servo/hooks/meta-judge.sh"`
# The Claude event name (`Stop`) is passed to the adapter, which injects it as
# `hook_event_name`; SERVO_HOOK_REL is the stable marker uninstall matches on.
COPILOT_HOOK_BASH = (
    "python3 " + COPILOT_ADAPTER_REL + " " + CLAUDE_HOOK_EVENT + ' "' + SERVO_HOOK_REL + '"'
)
# Single rolling backup of the Copilot hook config (mirrors BACKUP_NAME).
COPILOT_BACKUP_NAME = "servo-oracle.json.servo-bak"

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
    stop = hooks.setdefault(CLAUDE_HOOK_EVENT, [])
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


# --------------------------------------------------------------------------- #
# Copilot host: install/uninstall/report the oracle `agentStop` hook target-side
# (slice 032-04, ADR-0038). Mirrors the Claude-path contract — idempotent merge,
# single backup, stable-marker identification — against a Copilot `.github/hooks/
# servo-oracle.json` instead of `.claude/settings.json`.
# --------------------------------------------------------------------------- #
def _copilot_adapter_src() -> Path:
    """servo's ported Copilot hook adapter, shipped beside this installer."""
    return _here().parent / COPILOT_ADAPTER_NAME


def _servo_agentstop_entry(timeout: int) -> dict:
    """servo's Copilot ``agentStop`` entry (flat schema — spike 032-01 / ADR-0038)."""
    return {"type": "command", "bash": COPILOT_HOOK_BASH, "timeoutSec": timeout}


def _copilot_entry_is_servo(entry: object) -> bool:
    """Identify servo's ``agentStop`` entry by the stable meta-judge marker in
    its ``bash`` command — the Copilot analogue of :func:`_entry_is_servo`, so
    uninstall touches exactly servo's entry and leaves a user's alone."""
    return isinstance(entry, dict) and SERVO_HOOK_REL in str(entry.get("bash", ""))


def _load_copilot_config(config_path: Path, *, validate_structure: bool) -> tuple[dict, bool]:
    """Parse the Copilot hook config → ``(config, had_content)``.

    The Copilot analogue of :func:`_load_settings`: refuses (:class:`_SettingsRefusal`)
    on unparseable JSON or a non-object root, and — when ``validate_structure``
    is set (the mutating callers) — on an odd-shaped ``hooks`` /
    ``hooks.agentStop``. ``status`` passes False and guards its own reads."""
    config: dict = {}
    had_content = False
    if config_path.is_file():
        raw = config_path.read_text()
        if raw.strip():
            try:
                config = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise _SettingsRefusal(
                    f"{config_path} is not valid JSON", "settings_malformed"
                ) from exc
            if not isinstance(config, dict):
                raise _SettingsRefusal(
                    f"{config_path} is not a JSON object", "settings_malformed"
                )
            had_content = True
    if validate_structure:
        hooks = config.get("hooks")
        if hooks is not None and not isinstance(hooks, dict):
            raise _SettingsRefusal(
                f'{config_path}: "hooks" is not a JSON object', "settings_malformed"
            )
        if isinstance(hooks, dict):
            entries = hooks.get(COPILOT_HOOK_EVENT)
            if entries is not None and not isinstance(entries, list):
                raise _SettingsRefusal(
                    f'{config_path}: "hooks.{COPILOT_HOOK_EVENT}" is not a JSON array',
                    "settings_malformed",
                )
    return config, had_content


def _place_copilot_scripts(target: Path) -> Path:
    """Write the adapter + meta-judge into the target's ``.servo/hooks/``.

    The meta-judge is written only when absent (project-owned & customizable —
    mirrors the Claude path, so re-install never clobbers a customized script);
    the adapter is servo machinery, refreshed when absent or byte-stale (so a
    servo upgrade re-syncs it). Returns the meta-judge path."""
    hooks_dir = target / ".servo" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)

    script = hooks_dir / "meta-judge.sh"
    if not script.exists():
        template = _templates_root() / "meta-judge.sh.template"
        body = template.read_text().replace("__GATE_PY__", _resolve_gate_py(target))
        script.write_text(body)
        script.chmod(script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    adapter = hooks_dir / COPILOT_ADAPTER_NAME
    src_bytes = _copilot_adapter_src().read_bytes()
    if not adapter.exists() or adapter.read_bytes() != src_bytes:
        adapter.write_bytes(src_bytes)
        adapter.chmod(adapter.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return script


def cmd_install_copilot(target: Path, *, timeout: int = DEFAULT_TIMEOUT) -> int:
    # Same scaffolded-target preconditions as the Claude path (validate before
    # any write — a rejected install is a true no-op).
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

    config_path = target / COPILOT_HOOK_CONFIG_REL
    try:
        config, had_content = _load_copilot_config(config_path, validate_structure=True)
    except _SettingsRefusal as e:
        return _refuse(f"{e.msg}; refusing to overwrite", reason=e.reason)

    # Place (or self-heal) the target-side scripts before the idempotency check,
    # mirroring the Claude path's script-then-merge order.
    _place_copilot_scripts(target)

    config.setdefault("version", 1)
    hooks = config.setdefault("hooks", {})
    entries = hooks.setdefault(COPILOT_HOOK_EVENT, [])
    if any(_copilot_entry_is_servo(e) for e in entries):
        sys.stdout.write(
            f"oracle-hook: Copilot {COPILOT_HOOK_EVENT} hook already installed -> {config_path}\n"
        )
        return EXIT_OK

    # Back up before the first mutation, only when there was real prior content
    # to preserve (mirrors the Claude single-backup contract, 004-03 AC3).
    if had_content:
        shutil.copyfile(config_path, config_path.parent / COPILOT_BACKUP_NAME)

    entries.append(_servo_agentstop_entry(timeout))
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, indent=2) + "\n")

    sys.stdout.write(
        f"oracle-hook: installed Copilot {COPILOT_HOOK_EVENT} hook -> {config_path}\n"
    )
    return EXIT_OK


def cmd_uninstall_copilot(target: Path) -> int:
    config_path = target / COPILOT_HOOK_CONFIG_REL
    try:
        config, _ = _load_copilot_config(config_path, validate_structure=True)
    except _SettingsRefusal as e:
        return _refuse(f"{e.msg}; refusing to modify", reason=e.reason)

    hooks = config.get("hooks")
    entries = hooks.get(COPILOT_HOOK_EVENT) if isinstance(hooks, dict) else None
    if not isinstance(entries, list) or not any(_copilot_entry_is_servo(e) for e in entries):
        sys.stdout.write(
            f"oracle-hook: no servo Copilot {COPILOT_HOOK_EVENT} hook to remove (no change)\n"
        )
        return EXIT_OK

    shutil.copyfile(config_path, config_path.parent / COPILOT_BACKUP_NAME)

    # Remove only servo's entries; clean up the emptied structure. The
    # target-side scripts are deliberately left on disk (mirrors the Claude path
    # leaving meta-judge.sh — it may be customized).
    remaining = [e for e in entries if not _copilot_entry_is_servo(e)]
    if remaining:
        hooks[COPILOT_HOOK_EVENT] = remaining
    else:
        del hooks[COPILOT_HOOK_EVENT]
    if hooks:
        # Other hook events remain (a user co-located them) — keep the file.
        config_path.write_text(json.dumps(config, indent=2) + "\n")
    else:
        # `servo-oracle.json` is servo's own dedicated file; with no hooks left
        # it is detritus — remove it rather than leave a `{version, hooks:{}}`
        # husk (the backup remains for recovery).
        config_path.unlink()

    sys.stdout.write(
        f"oracle-hook: removed servo Copilot {COPILOT_HOOK_EVENT} hook "
        "(adapter + meta-judge.sh left on disk)\n"
    )
    return EXIT_OK


def cmd_status_copilot(target: Path, *, as_json: bool = False) -> int:
    config_path = target / COPILOT_HOOK_CONFIG_REL
    script = target / ".servo" / "hooks" / "meta-judge.sh"
    adapter = target / COPILOT_ADAPTER_REL
    # Both target-side scripts must be present for a working install.
    script_present = script.is_file() and adapter.is_file()

    try:
        config, _ = _load_copilot_config(config_path, validate_structure=False)
    except _SettingsRefusal as e:
        return _refuse(f"{e.msg}; cannot determine status", reason=e.reason)

    hooks = config.get("hooks")
    entries = hooks.get(COPILOT_HOOK_EVENT) if isinstance(hooks, dict) else None
    entry_present = isinstance(entries, list) and any(_copilot_entry_is_servo(e) for e in entries)

    if entry_present and script_present:
        state = "installed"
    elif not entry_present and not script_present:
        state = "not_installed"
    else:
        state = "inconsistent"

    if as_json:
        sys.stdout.write(json.dumps({
            "schema_version": 1,
            "host": "copilot",
            "state": state,
            "entry_present": entry_present,
            "script_present": script_present,
            "config_path": str(config_path),
            "script_path": str(script),
            "adapter_path": str(adapter),
        }) + "\n")
    else:
        sys.stdout.write(
            f"oracle-hook: {state} "
            f"(Copilot {COPILOT_HOOK_EVENT} entry: {'present' if entry_present else 'absent'}, "
            f"meta-judge.sh + adapter: {'present' if script_present else 'absent'})\n"
        )
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="hook.py",
        description="Install/uninstall/report servo's meta-judge Stop hook.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    def _add_host(p: argparse.ArgumentParser) -> None:
        # Host selection (032-04 AC4): Claude `Stop` (in .claude/settings.json)
        # vs Copilot `agentStop` (in .github/hooks/servo-oracle.json). Defaults
        # to `claude` — zero behavior change for existing installs. An explicit
        # flag (not `.github/` presence, which most repos carry for Actions) is
        # the safe selector.
        p.add_argument(
            "--host", choices=("claude", "copilot"), default="claude",
            help="target host (default: claude; copilot writes an agentStop hook)",
        )

    p_install = sub.add_parser("install", help="install the meta-judge Stop hook")
    p_install.add_argument("target", help="path to the servo-scaffolded project")
    p_install.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f"hook command timeout in seconds (default {DEFAULT_TIMEOUT})",
    )
    _add_host(p_install)

    p_uninstall = sub.add_parser(
        "uninstall", help="remove servo's Stop hook entry (leaves the script on disk)"
    )
    p_uninstall.add_argument("target", help="path to the project")
    _add_host(p_uninstall)

    p_status = sub.add_parser(
        "status", help="report whether the meta-judge Stop hook is installed"
    )
    p_status.add_argument("target", help="path to the project")
    p_status.add_argument(
        "--json", action="store_true", dest="as_json",
        help="emit machine-readable JSON instead of a human-readable line",
    )
    _add_host(p_status)

    args = parser.parse_args(argv)

    target = Path(args.target).expanduser().resolve()
    # Shared precondition for the whole CLI surface (AC6): the target must exist.
    if not target.is_dir():
        return _refuse(
            f"target not found or not a directory: {target}", reason="target_missing"
        )

    if args.cmd == "install":
        if args.host == "copilot":
            return cmd_install_copilot(target, timeout=args.timeout)
        return cmd_install(target, timeout=args.timeout)
    if args.cmd == "uninstall":
        if args.host == "copilot":
            return cmd_uninstall_copilot(target)
        return cmd_uninstall(target)
    if args.cmd == "status":
        if args.host == "copilot":
            return cmd_status_copilot(target, as_json=args.as_json)
        return cmd_status(target, as_json=args.as_json)
    return EXIT_ENV_ERROR  # unreachable: subparser is required


if __name__ == "__main__":
    raise SystemExit(main())
