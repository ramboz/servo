#!/usr/bin/env python3
"""Vendor servo runtime machinery into a project-local `<target>/.claude/`.

Slice 007-03 (scaffold-runtime). This is the explicit project-local scaffold
mode: it copies the contract-required skills, agents, and templates into a
target repo with servo-prefixed skill/agent names so the project carries the
exact runtime surface it needs without depending on a globally installed
plugin checkout.

This helper is deliberately separate from `skills/scaffold-init/scaffold.py`,
whose bare-positional `scaffold.py <target>` form is the spec-001 oracle-install
contract and must not change. The install contract
(`.claude-plugin/install-contract.json`) is the single source of truth for
*what* to vendor; this script only decides *where*.

Usage:
    python3 scripts/scaffold_runtime.py <target>

stdlib-only, Python 3.10+.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MANIFEST_SCHEMA_VERSION = 1
CONTRACT_PATH = Path(".claude-plugin") / "install-contract.json"
PLUGIN_MANIFEST_PATH = Path(".claude-plugin") / "plugin.json"
MANIFEST_NAME = "scaffold-install.json"

# Markdown link `[text](dest)`. Used to strip vendored links that cannot
# resolve inside the scaffold target (e.g. `../docs/decisions/...` refs that
# only exist in the servo source checkout).
_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def source_root() -> Path:
    """Locate the servo source checkout that owns the artifacts to vendor.

    `scripts/scaffold_runtime.py` lives one directory below the repo root, so
    the source root is this file's parent's parent. We do not read
    `CLAUDE_PLUGIN_ROOT` here on purpose: scaffolding pulls from the checkout
    that ships this script, keeping the operation self-describing.
    """
    return Path(__file__).resolve().parents[1]


def iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def load_contract(src: Path) -> dict[str, Any]:
    contract = _read_json(src / CONTRACT_PATH)
    if contract.get("schema_version") != 1:
        raise ValueError("install contract must have schema_version=1")
    required = contract.get("required")
    if not isinstance(required, dict):
        raise ValueError("install contract must contain a required object")
    scaffold = contract.get("scaffold")
    if not isinstance(scaffold, dict):
        raise ValueError("install contract must contain a scaffold object")
    for key in ("skill_prefix", "agent_prefix", "runtime_root", "managed_marker"):
        if not isinstance(scaffold.get(key), str) or not scaffold.get(key):
            raise ValueError(f"scaffold.{key} must be a non-empty string")
    return contract


def plugin_version(src: Path) -> str:
    manifest = _read_json(src / PLUGIN_MANIFEST_PATH)
    version = manifest.get("version")
    if not isinstance(version, str) or not version:
        raise ValueError(f"{PLUGIN_MANIFEST_PATH.as_posix()} must contain a version string")
    return version


def _copy_file(src_file: Path, dst_file: Path) -> None:
    dst_file.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src_file, dst_file)


def _normalized_skills(contract: dict[str, Any]) -> list[dict[str, Any]]:
    skills: list[dict[str, Any]] = []
    for entry in contract["required"].get("skills", []):
        if isinstance(entry, str):
            skills.append({"name": entry, "files": ["SKILL.md"]})
        elif isinstance(entry, dict):
            skills.append({"name": entry["name"], "files": entry["files"]})
    return skills


def _rewrite_skill_md_plugin_root(
    skill_md: Path,
    skill_names: list[str],
    skill_prefix: str,
) -> None:
    """Rewrite plugin-root command paths in a vendored SKILL.md (AC1).

    For every contract skill `name`, rewrite the literal
    `${CLAUDE_PLUGIN_ROOT}/skills/<name>/` to the vendored, prefixed location
    `.claude/skills/<prefix><name>/`. After this, no `${CLAUDE_PLUGIN_ROOT}`
    should remain in the vendored SKILL.md — the scaffold-mode commands point
    at files that exist under the target.

    The `.py` helpers are intentionally *not* rewritten: they resolve their
    own siblings via `_templates_root` and remain valid dual-mode code; their
    docstring references to `CLAUDE_PLUGIN_ROOT` are accurate plugin-mode docs.
    """
    text = skill_md.read_text()
    for name in skill_names:
        text = text.replace(
            f"${{CLAUDE_PLUGIN_ROOT}}/skills/{name}/",
            f".claude/skills/{skill_prefix}{name}/",
        )
    skill_md.write_text(text)


def _rewrite_markdown_links(md_path: Path, target_root: Path) -> None:
    """Strip vendored markdown links that cannot resolve inside the target (AC3).

    A link `[text](dest)` is kept when `dest` is a URL, a bare `#anchor`, a
    `mailto:`, or a relative path that resolves to an existing file under the
    scaffold target. Otherwise it is reduced to its plain `text`, dropping the
    `](dest)`. This handles the agents' `[ADR-0003](../docs/decisions/...)`
    refs, which only exist in the servo source checkout.
    """
    target_root = target_root.resolve()

    def _replace(match: re.Match[str]) -> str:
        text, dest = match.group(1), match.group(2)
        if dest.startswith(("http://", "https://", "mailto:", "#")):
            return match.group(0)
        path_part = dest.split("#", 1)[0]
        if not path_part:
            return match.group(0)
        resolved = (md_path.parent / path_part).resolve()
        try:
            resolved.relative_to(target_root)
        except ValueError:
            # Escapes the scaffold target — definitely stale.
            return text
        if resolved.exists():
            return match.group(0)
        return text

    original = md_path.read_text()
    rewritten = _MD_LINK_RE.sub(_replace, original)
    if rewritten != original:
        md_path.write_text(rewritten)


def scaffold_runtime(target: Path | str) -> dict[str, Any]:
    """Vendor servo runtime machinery into `<target>/.claude/`.

    Idempotent: managed files are overwritten in place and the manifest is
    rewritten, so a re-run refreshes the managed surface without duplication.
    Returns the manifest dict that was written.
    """
    target_path = Path(target).resolve()
    if not target_path.exists():
        raise FileNotFoundError(f"target does not exist: {target_path}")
    if not target_path.is_dir():
        raise NotADirectoryError(f"target is not a directory: {target_path}")

    src = source_root()
    contract = load_contract(src)
    scaffold_cfg = contract["scaffold"]
    skill_prefix = scaffold_cfg["skill_prefix"]
    agent_prefix = scaffold_cfg["agent_prefix"]
    runtime_root = scaffold_cfg["runtime_root"]
    managed_marker = scaffold_cfg["managed_marker"]

    claude_root = target_path / ".claude"
    skills_dst_root = claude_root / "skills"
    agents_dst_root = claude_root / "agents"
    templates_dst_root = target_path / runtime_root / "templates"

    skill_names = [skill["name"] for skill in _normalized_skills(contract)]

    # Collect vendored markdown copies so link rewriting (AC3) runs once after
    # every managed file is in place — link resolution depends on the full
    # scaffold layout existing on disk.
    vendored_markdown: list[Path] = []

    copied_skills: list[str] = []
    for skill in _normalized_skills(contract):
        dst_name = f"{skill_prefix}{skill['name']}"
        for file_name in skill["files"]:
            src_file = src / "skills" / skill["name"] / file_name
            dst_file = skills_dst_root / dst_name / file_name
            _copy_file(src_file, dst_file)
            if file_name == "SKILL.md":
                # AC1: vendored SKILL.md commands point at vendored, prefixed
                # skill paths rather than the plugin checkout.
                _rewrite_skill_md_plugin_root(dst_file, skill_names, skill_prefix)
                vendored_markdown.append(dst_file)
        copied_skills.append(dst_name)

    copied_agents: list[str] = []
    for agent in contract["required"].get("agents", []):
        dst_name = f"{agent_prefix}{agent}"
        dst_file = agents_dst_root / f"{dst_name}.md"
        _copy_file(src / "agents" / f"{agent}.md", dst_file)
        vendored_markdown.append(dst_file)
        copied_agents.append(dst_name)

    copied_templates: list[str] = []
    for template in contract["required"].get("templates", []):
        _copy_file(src / "templates" / template, templates_dst_root / template)
        copied_templates.append(template)

    # AC3: strip vendored markdown links that cannot resolve inside the target.
    for md_path in vendored_markdown:
        _rewrite_markdown_links(md_path, target_path)

    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "source_version": plugin_version(src),
        "timestamp": iso_now(),
        "managed_marker": managed_marker,
        "skills": copied_skills,
        "agents": copied_agents,
        "templates": copied_templates,
    }
    manifest_path = target_path / runtime_root / MANIFEST_NAME
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scaffold_runtime.py",
        description="Vendor servo runtime machinery into a project-local .claude/.",
    )
    parser.add_argument("target", help="path to the target project directory")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    ns = parser.parse_args(argv)
    try:
        manifest = scaffold_runtime(ns.target)
    except (FileNotFoundError, NotADirectoryError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except (ValueError, json.JSONDecodeError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    target_path = Path(ns.target).resolve()
    print(
        f"servo: scaffolded runtime into {target_path / '.claude'} "
        f"({len(manifest['skills'])} skills, {len(manifest['agents'])} agents, "
        f"{len(manifest['templates'])} templates)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
