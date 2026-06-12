#!/usr/bin/env python3
"""ADR-0008 V3 — audit a target environment's settings hierarchy for the switches
that disable /goal and servo's meta-judge. FREE (no API). Run this against each
real target environment to measure how common Kill-criterion 4 actually is — the
"audit" half of V3 (the v3_hook_restrictions.sh runner confirms the *mechanism*;
this measures *prevalence*).

Disabling rules (per ADR-0008 settled grounding / goal.md + hooks.md):
  • disableAllHooks (truthy at ANY settings layer)        → /goal AND all hooks off
  • allowManagedHooksOnly (truthy in the MANAGED layer)   → /goal off; project/user
                                                            (non-managed) hooks off
servo's meta-judge is a PROJECT hook, so it dies under either switch — exactly as
/goal does. loop.py (no hooks) is unaffected.

Usage:  v3_audit_env.py [<target-dir>]      (defaults to CWD)
"""
from __future__ import annotations

import json
import os
import platform
import sys
from pathlib import Path


def load(p: Path):
    try:
        return json.loads(p.read_text())
    except FileNotFoundError:
        return None
    except Exception as e:  # malformed JSON, etc.
        return {"__parse_error__": str(e)}


def managed_paths() -> list[Path]:
    sysname = platform.system()
    if sysname == "Darwin":
        return [Path("/Library/Application Support/ClaudeCode/managed-settings.json")]
    if sysname == "Windows":
        return [Path(os.path.expandvars(r"%PROGRAMDATA%\ClaudeCode\managed-settings.json"))]
    return [Path("/etc/claude-code/managed-settings.json")]


def main(argv: list[str]) -> int:
    target = Path(argv[0]).resolve() if argv else Path.cwd()
    layers: list[tuple[str, Path, bool]] = [
        ("user", Path.home() / ".claude" / "settings.json", False),
        ("project", target / ".claude" / "settings.json", False),
        ("project-local", target / ".claude" / "settings.local.json", False),
    ] + [("managed", p, True) for p in managed_paths()]

    disable_all_at: list[str] = []   # layers asserting disableAllHooks
    managed_only_at: list[str] = []  # MANAGED layers asserting allowManagedHooksOnly
    stop_hook_at: list[str] = []

    print(f"=== ADR-0008 V3 env audit — target: {target}  ({platform.system()}) ===")
    for name, p, is_managed in layers:
        s = load(p)
        if s is None:
            print(f"  {name:14} {p}  — absent")
            continue
        if isinstance(s, dict) and "__parse_error__" in s:
            print(f"  {name:14} {p}  — ⚠ PARSE ERROR: {s['__parse_error__']}")
            continue
        dah = s.get("disableAllHooks")
        amho = s.get("allowManagedHooksOnly")
        stop = ((s.get("hooks") or {}).get("Stop")) or []
        flags = []
        if dah:
            flags.append(f"disableAllHooks={dah}")
            disable_all_at.append(name)
        if amho:
            flags.append(f"allowManagedHooksOnly={amho}")
            if is_managed:
                managed_only_at.append(name)
            else:
                flags.append("(ignored — only binds in the managed tier)")
        if stop:
            flags.append(f"Stop-hooks={len(stop)}")
            stop_hook_at.append(name)
        print(f"  {name:14} {p}  — present  {'  '.join(flags) if flags else '(no relevant keys)'}")

    killers = disable_all_at + managed_only_at
    goal_ok = not killers
    metajudge_ok = not killers  # project hook → same switches as /goal

    print("\n  VERDICT for this environment:")
    print(f"    /goal available  : {'YES' if goal_ok else 'NO  (' + ', '.join(killers) + ')'}")
    print(f"    meta-judge fires : {'YES' if metajudge_ok else 'NO  (same switch)'}")
    if killers:
        print("    → Kill-criterion 4: the rebase is unavailable here; only the hand-rolled")
        print("      loop.py (no hooks, plain `claude -p` subprocess loop) survives.")
    else:
        print("    → No hook restriction detected; /goal + meta-judge both usable here.")
        if not stop_hook_at:
            print("    (note: no Stop hook registered in this target — meta-judge not installed.)")
    # Exit 1 when a restriction is in force, so this is scriptable across a fleet.
    return 1 if killers else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
