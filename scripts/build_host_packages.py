#!/usr/bin/env python3
"""Materialize deterministic, runtime-only Claude and Codex host packages."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import TextIO

ROOT = Path(__file__).resolve().parent.parent
HOSTS = ("claude", "codex")
REGEN_COMMAND = "python3 scripts/build_host_packages.py"

_TOP_LEVEL_RUNTIME = ("agents", "skills", "templates")
_TOP_LEVEL_FILES = ("README.md", "LICENSE", "servo.jpg")
_EXCLUDED_NAMES = {".DS_Store", ".gitkeep"}
_EXCLUDED_DIRS = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
_CODEX_DESCRIPTION_MAX = 1024


def _load_object(path: Path) -> dict:
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _validate_source(source_root: Path) -> str:
    claude = _load_object(source_root / ".claude-plugin" / "plugin.json")
    codex = _load_object(source_root / ".codex-plugin" / "plugin.json")
    claude_version = claude.get("version")
    codex_version = codex.get("version")
    if not isinstance(claude_version, str) or not claude_version:
        raise ValueError(".claude-plugin/plugin.json must declare a version")
    if codex_version != claude_version:
        raise ValueError(
            "host manifest version mismatch: .claude-plugin/plugin.json declares "
            f"{claude_version!r}, .codex-plugin/plugin.json declares {codex_version!r}"
        )
    for name in (*_TOP_LEVEL_RUNTIME, *_TOP_LEVEL_FILES):
        if not (source_root / name).exists():
            raise FileNotFoundError(f"runtime source is missing: {name}")
    return claude_version


def _is_runtime_file(path: Path, source_root: Path) -> bool:
    rel = path.relative_to(source_root)
    if any(part in _EXCLUDED_DIRS for part in rel.parts):
        return False
    if path.name in _EXCLUDED_NAMES or path.suffix == ".pyc":
        return False
    if path.name.startswith("test_") and path.suffix == ".py":
        return False
    if path.name == "crew-postmortem.md":
        return False
    return path.is_file()


def _render_codex_skill(data: bytes, skill_name: str) -> bytes:
    """Render Codex discovery metadata while preserving the skill body."""
    text = data.decode("utf-8").replace("${CLAUDE_PLUGIN_ROOT}", "${PLUGIN_ROOT}")
    opening, frontmatter, body = text.split("---", 2)
    lines = frontmatter.splitlines()
    rendered: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if line == f"name: servo:{skill_name}":
            rendered.append(f"name: {skill_name}")
            index += 1
            continue
        if line in {"description: |", "description: >-"}:
            index += 1
            paragraph: list[str] = []
            while index < len(lines):
                candidate = lines[index]
                if candidate and not candidate.startswith("  "):
                    break
                if not candidate.strip():
                    if paragraph:
                        break
                    index += 1
                    continue
                paragraph.append(candidate)
                index += 1
            rendered.append("description: >-")
            summary = " ".join(part.strip() for part in paragraph)
            if len(summary) > _CODEX_DESCRIPTION_MAX:
                raise ValueError(
                    f"{skill_name} discovery description is {len(summary)} characters; "
                    f"shorten its first paragraph to <= {_CODEX_DESCRIPTION_MAX}"
                )
            rendered.append(f"  {summary}")
            # Skip the remainder of the original description metadata. Its
            # operational detail already lives in the skill body; Codex's
            # discovery description is intentionally a short routing summary.
            while index < len(lines) and (not lines[index] or lines[index].startswith("  ")):
                index += 1
            continue
        rendered.append(line)
        index += 1
    return (opening + "---\n" + "\n".join(rendered) + "\n---" + body).encode("utf-8")


def _copy_runtime_tree(source_root: Path, plugin_root: Path, host: str) -> None:
    for root_name in _TOP_LEVEL_RUNTIME:
        source_dir = source_root / root_name
        for source in sorted(source_dir.rglob("*")):
            if not _is_runtime_file(source, source_root):
                continue
            rel = source.relative_to(source_root)
            target = plugin_root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            data = source.read_bytes()
            if host == "codex" and source.name == "SKILL.md":
                data = _render_codex_skill(data, rel.parent.name)
            target.write_bytes(data)
            target.chmod(0o755 if source.stat().st_mode & 0o111 else 0o644)

    for name in _TOP_LEVEL_FILES:
        source = source_root / name
        target = plugin_root / name
        target.write_bytes(source.read_bytes())
        target.chmod(0o644)


def _write_marketplace(path: Path) -> None:
    payload = {
        "name": "servo",
        "interface": {"displayName": "servo"},
        "plugins": [
            {
                "name": "servo",
                "source": {"source": "local", "path": "./plugins/servo"},
                "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
                "category": "Engineering",
            }
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n")


def _replace_dir(staged: Path, target: Path) -> None:
    if target.exists():
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(staged), str(target))


def build_all(source_root: Path, hosts_root: Path, out: TextIO | None = None) -> int:
    if out is None:
        out = sys.stdout
    source_root = source_root.resolve()
    hosts_root = hosts_root.resolve()
    try:
        version = _validate_source(source_root)
        scratch = Path(tempfile.mkdtemp(prefix="servo-host-build-"))
        try:
            claude = scratch / "claude"
            claude.mkdir(parents=True)
            _copy_runtime_tree(source_root, claude, "claude")
            manifest_target = claude / ".claude-plugin" / "plugin.json"
            manifest_target.parent.mkdir(parents=True)
            manifest_target.write_bytes(
                (source_root / ".claude-plugin" / "plugin.json").read_bytes()
            )

            codex_root = scratch / "codex"
            codex = codex_root / "plugins" / "servo"
            codex.mkdir(parents=True)
            _copy_runtime_tree(source_root, codex, "codex")
            codex_manifest = codex / ".codex-plugin" / "plugin.json"
            codex_manifest.parent.mkdir(parents=True)
            codex_manifest.write_bytes(
                (source_root / ".codex-plugin" / "plugin.json").read_bytes()
            )
            _write_marketplace(codex_root / ".agents" / "plugins" / "marketplace.json")

            _replace_dir(claude, hosts_root / "claude")
            _replace_dir(codex_root, hosts_root / "codex")
        finally:
            shutil.rmtree(scratch, ignore_errors=True)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        out.write(f"ERROR: failed to build host packages: {exc}\n")
        return 1
    out.write(f"OK: built Claude and Codex host packages (version {version}).\n")
    return 0


def _file_map(root: Path) -> dict[str, bytes]:
    if not root.is_dir():
        return {}
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.suffix != ".pyc"
    }


def check_drift(source_root: Path, hosts_root: Path, out: TextIO | None = None) -> int:
    if out is None:
        out = sys.stdout
    scratch = Path(tempfile.mkdtemp(prefix="servo-host-drift-"))
    try:
        if build_all(source_root, scratch, out=type("Sink", (), {"write": lambda *_: None})()):
            out.write("ERROR: could not regenerate host packages for drift check.\n")
            return 1
        expected = _file_map(scratch)
        committed = _file_map(hosts_root)
        drift = sorted(
            key for key in set(expected) | set(committed) if expected.get(key) != committed.get(key)
        )
        if not drift:
            out.write("OK: committed host packages are in sync with source.\n")
            return 0
        out.write("ERROR: committed host packages are stale relative to source.\n")
        for rel in drift:
            out.write(f"  - hosts/{rel}\n")
        out.write(f"Regenerate and commit them with: {REGEN_COMMAND}\n")
        return 1
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build Servo's committed host packages.")
    parser.add_argument("--source-root", default=str(ROOT))
    parser.add_argument("--hosts-root")
    parser.add_argument("--check", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    ns = _build_parser().parse_args(argv)
    source_root = Path(ns.source_root)
    hosts_root = Path(ns.hosts_root) if ns.hosts_root else source_root / "hosts"
    if ns.check:
        return check_drift(source_root, hosts_root)
    return build_all(source_root, hosts_root)


if __name__ == "__main__":
    raise SystemExit(main())
