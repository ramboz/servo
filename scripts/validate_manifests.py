#!/usr/bin/env python3
"""Validate Servo's root and committed host-package plugin manifests."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
MANIFESTS = (
    Path(".claude-plugin/plugin.json"),
    Path(".codex-plugin/plugin.json"),
    Path("hosts/claude/.claude-plugin/plugin.json"),
    Path("hosts/codex/plugins/servo/.codex-plugin/plugin.json"),
)
MARKETPLACES = (
    (Path(".claude-plugin/marketplace.json"), {"source": "git-subdir", "path": "hosts/claude"}),
    (
        Path(".agents/plugins/marketplace.json"),
        {"source": "local", "path": "./hosts/codex/plugins/servo"},
    ),
    (
        Path("hosts/codex/.agents/plugins/marketplace.json"),
        {"source": "local", "path": "./plugins/servo"},
    ),
)
# Copilot's marketplace descriptor lives at its own higher-precedence path
# (bug 035) and uses a relative-string `source`, NOT the git-subdir OBJECT
# dialect Claude uses — Copilot rejects the object shape. A separate descriptor
# per host is required because hosts recognize different paths AND different
# source dialects.
COPILOT_MARKETPLACE = Path(".github/plugin/marketplace.json")
COPILOT_MARKETPLACE_SOURCE = "./hosts/copilot"


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("manifest must contain a JSON object")
    return payload


def _copilot_marketplace_errors(marketplace: dict[str, Any]) -> list[str]:
    """Validate the Copilot marketplace descriptor's source shape (bug 035): the
    servo plugin's `source` must be a relative-path STRING, not an object."""
    rel = COPILOT_MARKETPLACE.as_posix()
    plugins = marketplace.get("plugins")
    if not isinstance(plugins, list):
        return [f"{rel}: plugins must be a list"]
    servo_entry = next(
        (entry for entry in plugins if isinstance(entry, dict) and entry.get("name") == "servo"),
        None,
    )
    if servo_entry is None:
        return [f"{rel}: no servo plugin entry"]
    source = servo_entry.get("source")
    if not isinstance(source, str):
        return [
            f"{rel}: plugins source must be a relative-path string for Copilot "
            "(not a git-subdir object)"
        ]
    if source != COPILOT_MARKETPLACE_SOURCE:
        return [f"{rel}: source must be {COPILOT_MARKETPLACE_SOURCE!r}"]
    return []


def validate(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    manifests: list[tuple[Path, dict[str, Any]]] = []
    for rel in MANIFESTS:
        path = root / rel
        if not path.is_file():
            errors.append(f"missing manifest: {rel.as_posix()}")
            continue
        try:
            manifests.append((rel, _load(path)))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"invalid manifest {rel.as_posix()}: {exc}")

    if errors:
        return errors

    versions = {payload.get("version") for _, payload in manifests}
    if len(versions) != 1 or not all(isinstance(version, str) and version for version in versions):
        details = ", ".join(
            f"{rel.as_posix()}={payload.get('version')!r}" for rel, payload in manifests
        )
        errors.append(f"manifest versions differ: {details}")

    for rel, payload in manifests:
        if payload.get("name") != "servo":
            errors.append(f"{rel.as_posix()}: name must be 'servo'")

    root_claude = manifests[0][1]
    host_claude = manifests[2][1]
    root_codex = manifests[1][1]
    host_codex = manifests[3][1]
    if root_claude != host_claude:
        errors.append("Claude root and committed-package manifests differ")
    if root_codex != host_codex:
        errors.append("Codex root and committed-package manifests differ")
    if root_codex.get("skills") != "./skills/":
        errors.append("Codex manifest must declare skills='./skills/'")
    if not isinstance(root_codex.get("interface"), dict):
        errors.append("Codex manifest must declare interface metadata")

    for rel, expected_source in MARKETPLACES:
        try:
            marketplace = _load(root / rel)
            plugins = marketplace.get("plugins")
            if not isinstance(plugins, list):
                raise ValueError("plugins must be a list")
            servo_entry = next(
                entry
                for entry in plugins
                if isinstance(entry, dict) and entry.get("name") == "servo"
            )
            source = servo_entry.get("source")
            if not isinstance(source, dict):
                raise ValueError("servo source must be an object")
            for key, value in expected_source.items():
                if source.get(key) != value:
                    errors.append(
                        f"{rel.as_posix()}: source.{key} must be {value!r}"
                    )
        except (OSError, StopIteration, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"invalid marketplace {rel.as_posix()}: {exc}")

    copilot_rel = COPILOT_MARKETPLACE.as_posix()
    try:
        copilot_marketplace = _load(root / COPILOT_MARKETPLACE)
        if copilot_marketplace.get("name") != "servo":
            errors.append(f"{copilot_rel}: name must be 'servo'")
        errors.extend(_copilot_marketplace_errors(copilot_marketplace))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors.append(f"invalid marketplace {copilot_rel}: {exc}")
    return errors


def main() -> int:
    errors = validate()
    if errors:
        for error in errors:
            print(f"FAIL: {error}", file=sys.stderr)
        return 1
    version = _load(ROOT / MANIFESTS[0]).get("version")
    print(f"OK: four plugin manifests agree (servo {version})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
