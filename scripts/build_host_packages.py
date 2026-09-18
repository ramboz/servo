#!/usr/bin/env python3
"""Materialize deterministic, runtime-only Claude, Codex, and Copilot host packages."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import TextIO

ROOT = Path(__file__).resolve().parent.parent
HOSTS = ("claude", "codex", "copilot")
REGEN_COMMAND = "python3 scripts/build_host_packages.py"

_TOP_LEVEL_RUNTIME = ("agents", "skills", "templates")
_TOP_LEVEL_FILES = ("README.md", "LICENSE", "servo.jpg")
_EXCLUDED_NAMES = {".DS_Store", ".gitkeep"}
_EXCLUDED_DIRS = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
_CODEX_DESCRIPTION_MAX = 1024

# --------------------------------------------------------------------------- #
# Copilot host (slice 028-02, mirroring jig's shipped `build_copilot_plugin.py`
# + `CopilotScaffoldRenderer`, ported as functions into this function-based
# builder). Copilot's durable config home is `.github/`, so the committed
# package IS that `.github/` tree plus a legacy `.plugin/plugin.json` manifest.
# --------------------------------------------------------------------------- #

# Copilot's skill loader rejects a `name:` containing `:` and a `description:`
# field over 1024 characters (spike 028-01 AC / ADR-0034).
_COPILOT_DESCRIPTION_MAX = 1024
_COPILOT_DESCRIPTION_SUFFIX = " (full description in skill body)"

# servo's source skill names carry a `servo:` *invocation* namespace that must
# not appear in the loaded `name:` field (jig's own names are already bare, so
# jig only asserts; servo strips first, then asserts).
_SERVO_NAMESPACE = "servo:"

# Bug 036: Copilot exposes no plugin-root env var, so plugin-mode skill bodies
# name `$SERVO_ROOT` instead of `${CLAUDE_PLUGIN_ROOT}`, and a standalone
# locator resolves it in a fresh shell.
_CLAUDE_PLUGIN_ROOT_PREFIX = "${CLAUDE_PLUGIN_ROOT}"
_SERVO_ROOT_VAR = "SERVO_ROOT"
_SERVO_ROOT_TOKEN = "$" + _SERVO_ROOT_VAR
# The fresh-shell locator one-liner injected into every plugin-mode skill that
# references `$SERVO_ROOT`. It honours `COPILOT_HOME` (the same override the
# locator itself reads) and iterates a quoted glob so install paths with spaces
# still work. Unlike jig, there is NO SessionStart carrier — this locator is the
# sole resolution path (servo's Copilot package is hook-free, ADR-0034).
_SERVO_ROOT_LOCATOR = (
    _SERVO_ROOT_VAR
    + '="$(for f in "${COPILOT_HOME:-$HOME/.copilot}"/installed-plugins/*/*/'
    + ".github/scripts/servo_root.py"
    + '; do [ -f "$f" ] && python3 "$f" && break; done)"'
)
_SERVO_ROOT_NOTE_MARKER = "servo's runtime root (this plugin's own directory)"

_COPILOT_MANIFEST_SKILLS = ".github/skills"
_COPILOT_MANIFEST_AGENTS = ".github/agents"

# YAML block-scalar headers a `description:` field may use (folded `>`/`>-`/`>+`
# or literal `|`/`|-`/`|+`). Shared by the description reader and the field
# rewriter so both agree on where "the value continues on later lines".
_DESCRIPTION_BLOCK_MARKERS = (">", "|", ">-", "|-", ">+", "|+")

# Slice 028-03 — servo's `agents/<name>.md` (runner, judge) render as Copilot
# custom agents under `.github/agents/<name>.agent.md`, mirroring jig's
# `render_copilot_agent` + `CLAUDE_TO_COPILOT_TOOLS`. A closed, hand-verified
# Claude-tool -> Copilot-tool-name mapping: an unmapped tool is a source
# defect (or an un-updated mapping) to fix, never silently dropped or passed
# through unmapped into a rendered `.agent.md` (mapped-or-explicit, no silent
# pass — the same stance `_copilot_safe_skill_name` takes for skill names).
CLAUDE_TO_COPILOT_TOOLS = {
    "Read": "view",
    "Glob": "glob",
    "Grep": "grep",
    "Write": "create",
    "Edit": "edit",
    "Bash": "bash",
}


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
    # Test files never ship to host packages, regardless of language — the
    # inventory guard (test_build_host_packages) excludes any `test_*`, so the
    # `.py`-only filter here would let a `test_*.mjs` (e.g. design-eval's
    # capture_lib node tests) slip into the package and fail that guard.
    if path.name.startswith("test_") and path.suffix in (".py", ".mjs", ".js", ".ts"):
        return False
    if path.name == "crew-postmortem.md":
        return False
    # Test-only data directories never ship to adopters. `test_*` catches test
    # modules, but a `fixtures/` tree beside them is just as test-only and would
    # otherwise land in every installed plugin (spec 026-01 reconciliation).
    if "fixtures" in rel.parts:
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


def _split_frontmatter(text: str) -> tuple[str, str]:
    """Split a SKILL.md into (frontmatter_with_fences, body). If the file has
    no YAML frontmatter, returns ('', text)."""
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\n") != "---":
        return ("", text)
    for i in range(1, len(lines)):
        if lines[i].rstrip("\n") == "---":
            return ("".join(lines[: i + 1]), "".join(lines[i + 1:]))
    return ("", text)


def _frontmatter_value(frontmatter: str, key: str, default: str = "") -> str:
    """Return the value of a simple one-line `key: value` frontmatter field, or
    `default` when absent (quotes stripped)."""
    for line in frontmatter.splitlines():
        match = re.match(rf"^{re.escape(key)}:\s*(.*)$", line)
        if match:
            return match.group(1).strip().strip("\"'") or default
    return default


def _read_skill_description(text: str) -> str:
    """Decode and whitespace-normalize a SKILL.md `description:` value.

    Handles an inline string or an indented folded/literal block scalar, and
    collapses runs of whitespace (so YAML folding/chomping does not count
    toward Copilot's 1024-character loader limit). Mirrors the reader jig's
    `install_contract._read_skill_description` uses so the two measure the same
    thing."""
    if text.startswith("---\n"):
        closing = text.find("\n---\n", 4)
        block = text[4:closing] if closing >= 0 else text[4:]
    else:
        block = text
    lines = block.splitlines()
    for index, line in enumerate(lines):
        if not line.startswith("description:"):
            continue
        value = line[len("description:"):].strip()
        if value and value not in _DESCRIPTION_BLOCK_MARKERS:
            return " ".join(value.strip("\"'").split())
        parts: list[str] = []
        for continuation in lines[index + 1:]:
            if continuation.strip() and not continuation.startswith((" ", "\t")):
                break
            parts.extend(continuation.split())
        return " ".join(parts)
    return ""


def _loader_safe_description(description: str) -> str:
    """Return `description` unchanged when it already fits Copilot's 1024-char
    skill-loader limit; otherwise return a word-boundary-truncated summary that
    fits the same budget, with a suffix pointing at the full text.

    Never drops content silently — the caller preserves the untruncated
    original in the SKILL.md body; this only bounds the returned string."""
    if len(description) <= _COPILOT_DESCRIPTION_MAX:
        return description
    budget = _COPILOT_DESCRIPTION_MAX - len(_COPILOT_DESCRIPTION_SUFFIX)
    truncated = description[:budget].rstrip()
    if " " in truncated:
        truncated = truncated.rsplit(" ", 1)[0]
    return truncated + _COPILOT_DESCRIPTION_SUFFIX


def _copilot_safe_skill_name(name: str) -> str:
    """Strip servo's `servo:` invocation namespace from a skill `name:` value,
    then assert the result is namespace-safe (no `:`). A colon-bearing name
    after the strip is a source defect to fix, not something to launder."""
    stripped = name[len(_SERVO_NAMESPACE):] if name.startswith(_SERVO_NAMESPACE) else name
    if ":" in stripped:
        raise ValueError(
            f"skill name {name!r} still contains ':' after stripping the "
            f"'{_SERVO_NAMESPACE}' namespace — Copilot's skill loader rejects "
            "namespace-unsafe names; fix the source SKILL.md 'name:' field"
        )
    return stripped


def _replace_name_line(frontmatter: str, new_name: str) -> str:
    """Rewrite the single `name:` line, leaving every other line untouched."""
    lines = frontmatter.splitlines(keepends=True)
    out: list[str] = []
    replaced = False
    for line in lines:
        if not replaced and line.startswith("name:"):
            newline = "\n" if line.endswith("\n") else ""
            out.append(f"name: {new_name}{newline}")
            replaced = True
        else:
            out.append(line)
    return "".join(out)


def _replace_description_field(frontmatter: str, new_value: str) -> str:
    """Replace a frontmatter's `description:` field (inline or a folded/literal
    block scalar) with a `>-` folded block scalar carrying `new_value` on one
    indented line, leaving every other line untouched. `frontmatter` includes
    both `---` fences.

    A block scalar (not an inline quoted string) is used deliberately: it needs
    NO escaping, so the raw on-disk field text equals the decoded value. That
    keeps the re-measured length honest — an inline `json.dumps` value would
    escape every inner quote (`\\"`), and `_read_skill_description` strips outer
    quotes but does not decode escapes, so a quote-heavy truncated summary would
    re-measure *over* 1024 even though its decoded value fits. servo's skills are
    quote-heavy, so this path genuinely fires (jig's stays dormant)."""
    lines = frontmatter.splitlines(keepends=True)
    out: list[str] = []
    i = 0
    replaced = False
    while i < len(lines):
        line = lines[i]
        if not replaced and line.startswith("description:"):
            out.append("description: >-\n")
            out.append(f"  {new_value}\n")
            value_part = line[len("description:"):].strip()
            i += 1
            if not value_part or value_part in _DESCRIPTION_BLOCK_MARKERS:
                while i < len(lines) and (
                    lines[i].strip() == "" or lines[i][:1] in (" ", "\t")
                ):
                    i += 1
            replaced = True
            continue
        out.append(line)
        i += 1
    return "".join(out)


def _ensure_servo_root_note(text: str) -> str:
    """Bug 036 — a skill that *uses* `$SERVO_ROOT` must also say how to resolve
    it. Copilot exposes no plugin-root env var and servo ships no SessionStart
    carrier, so this self-contained locator note is the only resolution path.
    Injected once, right after the frontmatter."""
    if _SERVO_ROOT_TOKEN not in text or _SERVO_ROOT_NOTE_MARKER in text:
        return text
    note = (
        "> **`" + _SERVO_ROOT_TOKEN + "`** — " + _SERVO_ROOT_NOTE_MARKER + ".\n"
        "> Copilot exposes no plugin-root environment variable, and servo's "
        "Copilot\n"
        "> package ships no hook to publish one. In a fresh shell, resolve it "
        "with\n"
        "> the locator:\n"
        "> `" + _SERVO_ROOT_LOCATOR + "`\n"
    )
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            cut = end + len("\n---\n")
            # Trailing blank line separates the root note from whatever follows
            # (a full-description note on the 9 over-limit skills, else the body).
            return text[:cut] + "\n" + note + "\n" + text[cut:]
    return note + "\n" + text


def _render_copilot_skill(data: bytes, skill_name: str) -> bytes:
    """Render one skill's SKILL.md for Copilot's loader-compat invariant + the
    bug-036 plugin-mode path rewrite.

    Distinct from `_render_codex_skill` (which collapses the description to its
    first paragraph, discarding later ones): Copilot keeps the FULL description
    byte-for-byte when it fits <=1024, and only when it overflows truncates the
    frontmatter value while appending the complete original to the body — so no
    routing/trigger guidance is ever lost.

    (a) strips the `servo:` namespace from `name:` then asserts it is `:`-free;
    (b) enforces the <=1024 `description:` limit (keep-or-truncate-and-preserve);
    (c) rewrites `${CLAUDE_PLUGIN_ROOT}/` helper paths to `$SERVO_ROOT/` and
        injects the root-resolution note into any skill that references it."""
    text = data.decode("utf-8")
    fm, body = _split_frontmatter(text)
    if fm:
        name = _frontmatter_value(fm, "name")
        safe_name = _copilot_safe_skill_name(name)
        if safe_name != name:
            fm = _replace_name_line(fm, safe_name)
        original_description = _read_skill_description(text)
        safe_description = _loader_safe_description(original_description)
        if safe_description != original_description:
            fm = _replace_description_field(fm, safe_description)
            note = (
                "> **Full description** (Copilot's skill loader caps a "
                "frontmatter `description` at 1024 characters; the summary "
                "above is shortened — this is the complete original text, "
                "preserved so no routing/trigger guidance is lost):\n"
                ">\n"
                f"> {original_description}\n\n"
            )
            body = note + body
        text = fm + body
    text = text.replace(_CLAUDE_PLUGIN_ROOT_PREFIX + "/", _SERVO_ROOT_TOKEN + "/")
    text = _ensure_servo_root_note(text)
    return text.encode("utf-8")


def _copilot_tool_names(claude_tools: list[str]) -> list[str]:
    """Map a source agent's Claude `tools:` list to Copilot's tool-name
    vocabulary (`CLAUDE_TO_COPILOT_TOOLS`), preserving order. Raises on any
    name absent from that mapping — a render-layer guard, not a transform:
    an unmapped tool is a source defect (or an un-updated mapping) to fix,
    never silently dropped or passed through unmapped."""
    mapped: list[str] = []
    for tool in claude_tools:
        try:
            mapped.append(CLAUDE_TO_COPILOT_TOOLS[tool])
        except KeyError as exc:
            raise ValueError(
                f"no Copilot tool mapping for Claude tool {tool!r} — add an "
                "entry to CLAUDE_TO_COPILOT_TOOLS"
            ) from exc
    return mapped


def _frontmatter_list(frontmatter: str, key: str) -> list[str]:
    """Return the items of a YAML block list under `key:` (`key:` followed by
    `  - item` lines) in `frontmatter`, or `[]` if `key` is absent or empty.
    A targeted reader (like `_frontmatter_value`), not a general YAML parser —
    sufficient for the flat `tools:` lists servo's source agents carry."""
    items: list[str] = []
    capturing = False
    for line in frontmatter.splitlines():
        if capturing:
            if line.startswith("  - "):
                items.append(line[len("  - "):].strip())
                continue
            break
        if re.match(rf"^{re.escape(key)}:\s*$", line):
            capturing = True
    return items


def _replace_tools_block(frontmatter: str, new_tools: list[str]) -> str:
    """Replace a frontmatter's `tools:` block list with `new_tools`, leaving
    every other line — including `name:`/`description:` — untouched.
    `frontmatter` includes both `---` fences."""
    lines = frontmatter.splitlines(keepends=True)
    out: list[str] = []
    i = 0
    replaced = False
    while i < len(lines):
        line = lines[i]
        if not replaced and line.rstrip("\n") == "tools:":
            out.append("tools:\n")
            out.extend(f"  - {tool}\n" for tool in new_tools)
            i += 1
            while i < len(lines) and lines[i].startswith("  - "):
                i += 1
            replaced = True
            continue
        out.append(line)
        i += 1
    return "".join(out)


def _render_copilot_agent(data: bytes, name: str) -> bytes:
    """Render one `agents/<name>.md` source agent to Copilot's `.agent.md`
    custom-agent form (slice 028-03; mirrors jig's `render_copilot_agent`):
    `tools:` mapped Claude->Copilot (`_copilot_tool_names`); `name:`/
    `description:`/body preserved untouched (a surgical edit, like
    `_replace_description_field`, not a rebuild-from-scratch).

    Model-id neutrality: raises if the source frontmatter carries a
    `model:` field — Copilot agent rendering must never emit one (model
    selection defers to Copilot's own `/model`). servo's source agents
    already omit `model:`; this guards against regression rather than
    papering over one, mirroring jig's `CopilotSkillNameError` stance for
    skill names."""
    text = data.decode("utf-8")
    fm, body = _split_frontmatter(text)
    if not fm:
        raise ValueError(f"agent {name!r} source has no YAML frontmatter to render")
    if re.search(r"^model:", fm, re.MULTILINE):
        raise ValueError(
            f"agent {name!r} source frontmatter carries a 'model:' field — "
            "Copilot agent rendering never emits a model id; remove it from "
            "the source before regenerating"
        )
    claude_tools = _frontmatter_list(fm, "tools")
    if re.search(r"^tools:", fm, re.MULTILINE) and not claude_tools:
        # A `tools:` key exists but the block-list reader found no `  - <tool>`
        # items — i.e. an inline/flow-sequence form (`tools: [Read, Write]`) the
        # surgical renderer does not map. Fail loud rather than pass the Claude
        # tool vocabulary through unmapped: the module contract is
        # "never silently dropped or passed through unmapped" (see header).
        raise ValueError(
            f"agent {name!r} has a 'tools:' key the block-list reader could not "
            "parse (inline/flow-sequence form unsupported) — declare tools as a "
            "'tools:' block of '  - <tool>' lines so each is mapped Claude->Copilot"
        )
    copilot_tools = _copilot_tool_names(claude_tools)
    fm = _replace_tools_block(fm, copilot_tools)
    return (fm + body).encode("utf-8")


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


def _copy_copilot_tree(source_root: Path, github_root: Path) -> None:
    """Populate `hosts/copilot/.github/` — skills (loader-safe + $SERVO_ROOT
    rewrite), agents (Claude->Copilot tools map, `.agent.md` form), templates
    (unrendered), and the servo_root.py locator.

    servo's Copilot package ships no plugin hooks (ADR-0034), so there is no
    `.github/hooks/`. Exclusions match the Claude/Codex builders
    (`_is_runtime_file`), so the skill and agent sets are identical across
    hosts."""
    # Skills → .github/skills/<name>/ (public skills + shared _common infra).
    skills_src = source_root / "skills"
    for source in sorted(skills_src.rglob("*")):
        if not _is_runtime_file(source, source_root):
            continue
        rel = source.relative_to(source_root)  # skills/<name>/<file>
        target = github_root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        data = source.read_bytes()
        if source.name == "SKILL.md":
            data = _render_copilot_skill(data, rel.parent.name)
        target.write_bytes(data)
        target.chmod(0o755 if source.stat().st_mode & 0o111 else 0o644)
    # Agents → .github/agents/<name>.agent.md (slice 028-03).
    agents_src = source_root / "agents"
    for source in sorted(agents_src.rglob("*")):
        if not _is_runtime_file(source, source_root):
            continue
        name = source.stem
        data = _render_copilot_agent(source.read_bytes(), name)
        target = github_root / "agents" / f"{name}.agent.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        target.chmod(0o755 if source.stat().st_mode & 0o111 else 0o644)
    # Templates → .github/templates/ (UNRENDERED — canonical ${CLAUDE_PLUGIN_ROOT}
    # intact so scaffold-time per-mode dispatch acts on the canonical spelling).
    templates_src = source_root / "templates"
    for source in sorted(templates_src.rglob("*")):
        if not _is_runtime_file(source, source_root):
            continue
        rel = source.relative_to(source_root)  # templates/<file>
        target = github_root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
        target.chmod(0o755 if source.stat().st_mode & 0o111 else 0o644)
    # The $SERVO_ROOT fresh-shell locator (bug 036).
    locator_src = source_root / "scripts" / "servo_root.py"
    locator_dst = github_root / "scripts" / "servo_root.py"
    locator_dst.parent.mkdir(parents=True, exist_ok=True)
    locator_dst.write_bytes(locator_src.read_bytes())
    locator_dst.chmod(0o755)


def _write_copilot_manifest(copilot_root: Path, version: str, description: str) -> None:
    """Write `.plugin/plugin.json` in Copilot's legacy format: metadata plus the
    component-path fields for the components servo ships (skills + agents). NO
    `hooks` field — servo's Copilot plugin ships no hooks (ADR-0034)."""
    payload = {
        "name": "servo",
        "version": version,
        "description": description,
        "skills": _COPILOT_MANIFEST_SKILLS,
        "agents": _COPILOT_MANIFEST_AGENTS,
    }
    dst = copilot_root / ".plugin" / "plugin.json"
    dst.parent.mkdir(parents=True, exist_ok=True)
    # ensure_ascii=False keeps the description's em dash raw, matching the
    # canonical manifest and the committed marketplace descriptor.
    dst.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def validate_copilot_package(
    plugin_root: Path, expected_skills: set[str] | None = None
) -> list[str]:
    """Statically validate a built Copilot package tree (slice 028-02 AC7) — the
    deterministic substitute for a live `copilot plugin install` (headless
    `copilot -p` does not reliably fire repo hooks).

    Checks: the `.plugin/plugin.json` manifest is valid JSON, names servo,
    carries a non-empty version, declares the `skills`/`agents` component paths
    and NO `hooks` field; the declared skills path resolves and (when
    `expected_skills` is given) matches the source skill set exactly; every
    SKILL.md frontmatter is loader-safe (name `:`-free, description <=1024).

    Agent files (`.github/agents/*.agent.md`, rendered by slice 028-03) are
    verified present and loader-safe (name `:`-free, no `model:` field —
    the 028-03 invariants), so the release smoke gates on every declared
    component, not just the drift guard. Returns diagnostics
    (empty == valid)."""
    problems: list[str] = []
    manifest_path = plugin_root / ".plugin" / "plugin.json"
    skills_rel = _COPILOT_MANIFEST_SKILLS
    agents_rel = _COPILOT_MANIFEST_AGENTS
    if not manifest_path.is_file():
        problems.append(".plugin/plugin.json: missing")
    else:
        try:
            manifest = json.loads(manifest_path.read_text())
        except (OSError, ValueError) as exc:
            problems.append(f".plugin/plugin.json: unreadable/invalid JSON ({exc})")
            manifest = {}
        if not isinstance(manifest, dict):
            problems.append(".plugin/plugin.json: must be a JSON object")
        else:
            if manifest.get("name") != "servo":
                problems.append(".plugin/plugin.json: name must be 'servo'")
            if not (isinstance(manifest.get("version"), str) and manifest.get("version")):
                problems.append(".plugin/plugin.json: version must be a non-empty string")
            if isinstance(manifest.get("skills"), str):
                skills_rel = manifest["skills"]
            else:
                problems.append(".plugin/plugin.json: must declare a 'skills' component path")
            if isinstance(manifest.get("agents"), str):
                agents_rel = manifest["agents"]
            else:
                problems.append(".plugin/plugin.json: must declare an 'agents' component path")
            if "hooks" in manifest:
                problems.append(
                    ".plugin/plugin.json: must NOT declare a 'hooks' field "
                    "(servo's Copilot package is hook-free)"
                )
    skills_dir = plugin_root / skills_rel
    if not skills_dir.is_dir():
        problems.append(f"{skills_rel}: skills directory is missing")
        return problems
    packaged = {p.parent.name for p in skills_dir.glob("*/SKILL.md")}
    if expected_skills is not None and packaged != expected_skills:
        problems.append(
            f"{skills_rel}: skill set != source "
            f"(missing={sorted(expected_skills - packaged)}, "
            f"extra={sorted(packaged - expected_skills)})"
        )
    for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
        name = skill_md.parent.name
        text = skill_md.read_text()
        fm, _ = _split_frontmatter(text)
        loaded_name = _frontmatter_value(fm, "name")
        if ":" in loaded_name:
            problems.append(f"{skills_rel}/{name}/SKILL.md: name {loaded_name!r} contains ':'")
        description = _read_skill_description(text)
        if len(description) > _COPILOT_DESCRIPTION_MAX:
            problems.append(
                f"{skills_rel}/{name}/SKILL.md: description is "
                f"{len(description)} characters (>{_COPILOT_DESCRIPTION_MAX})"
            )
    # Agent files (028-03): the release smoke gates on agent presence +
    # loader-safety, not just the drift guard, so a zip missing its declared
    # agents fails the smoke rather than shipping incomplete.
    agents_dir = plugin_root / agents_rel
    agent_files = sorted(agents_dir.glob("*.agent.md")) if agents_dir.is_dir() else []
    if not agent_files:
        problems.append(f"{agents_rel}: no '*.agent.md' agent files present")
    for agent_md in agent_files:
        fm, _ = _split_frontmatter(agent_md.read_text())
        loaded_name = _frontmatter_value(fm, "name")
        if ":" in loaded_name:
            problems.append(f"{agents_rel}/{agent_md.name}: name {loaded_name!r} contains ':'")
        if re.search(r"^model:", fm, re.MULTILINE):
            problems.append(
                f"{agents_rel}/{agent_md.name}: carries a 'model:' field "
                "(Copilot agents are model-neutral)"
            )
    return problems


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
        canonical = _load_object(source_root / ".claude-plugin" / "plugin.json")
        description = canonical.get("description", "")
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

            copilot_root = scratch / "copilot"
            copilot_root.mkdir(parents=True)
            _copy_copilot_tree(source_root, copilot_root / ".github")
            _write_copilot_manifest(copilot_root, version, description)

            _replace_dir(claude, hosts_root / "claude")
            _replace_dir(codex_root, hosts_root / "codex")
            _replace_dir(copilot_root, hosts_root / "copilot")
        finally:
            shutil.rmtree(scratch, ignore_errors=True)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        out.write(f"ERROR: failed to build host packages: {exc}\n")
        return 1
    out.write(f"OK: built Claude, Codex, and Copilot host packages (version {version}).\n")
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
