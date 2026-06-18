#!/usr/bin/env python3
"""Verify servo install surfaces.

Slices 007-01 and 007-02 implement plugin-root and release-zip
verification; slice 007-03 adds project-local scaffold verification
(`verify_install.py scaffold <target>`).
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from json import JSONDecodeError
from pathlib import Path, PureWindowsPath
from typing import Any, Iterable, TextIO

OUTPUT_SCHEMA_VERSION = 1
CONTRACT_SCHEMA_VERSION = 1
CONTRACT_PATH = Path(".claude-plugin") / "install-contract.json"
PLUGIN_MANIFEST_PATH = Path(".claude-plugin") / "plugin.json"
MARKETPLACE_PATH = Path(".claude-plugin") / "marketplace.json"


def iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def availability_marker_path() -> Path:
    state_home = os.environ.get("XDG_STATE_HOME")
    if state_home:
        return Path(state_home).expanduser() / "servo" / "available.json"
    return Path.home() / ".local" / "state" / "servo" / "available.json"


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    os.replace(tmp, path)


def write_availability_marker(root: Path | str, source_kind: str, source_version: str) -> None:
    root_path = Path(root).resolve()
    payload = {
        "schema_version": 1,
        "plugin_name": "servo",
        "source_kind": source_kind,
        "source_path": str(root_path),
        "source_version": source_version,
        "updated_at": iso_now(),
    }
    try:
        _write_json_atomic(availability_marker_path(), payload)
    except OSError as exc:
        print(
            f"servo: could not write availability marker: {exc}",
            file=sys.stderr,
        )


@dataclass(frozen=True)
class Failure:
    reason: str
    path: str
    message: str

    def to_json(self) -> dict[str, str]:
        return {
            "reason": self.reason,
            "path": self.path,
            "message": self.message,
        }


@dataclass(frozen=True)
class VerificationResult:
    mode: str
    plugin_name: str | None
    version: str | None
    failures: tuple[Failure, ...]

    @property
    def status(self) -> str:
        return "pass" if not self.failures else "fail"

    @property
    def ok(self) -> bool:
        return not self.failures

    def to_json(self) -> dict[str, Any]:
        return {
            "schema_version": OUTPUT_SCHEMA_VERSION,
            "mode": self.mode,
            "status": self.status,
            "plugin_name": self.plugin_name,
            "version": self.version,
            "failures": [failure.to_json() for failure in self.failures],
        }


def _display_path(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _failure(root: Path, reason: str, path: Path, message: str) -> Failure:
    return Failure(reason=reason, path=_display_path(root, path), message=message)


def _read_json_file(
    root: Path,
    relative_path: Path,
    *,
    missing_reason: str,
    malformed_reason: str,
) -> tuple[dict[str, Any] | None, Failure | None]:
    path = root / relative_path
    if not path.is_file():
        return None, _failure(root, missing_reason, path, f"{relative_path.as_posix()} is missing")
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        return None, _failure(
            root,
            malformed_reason,
            path,
            f"{relative_path.as_posix()} is not valid JSON: {exc.msg}",
        )
    if not isinstance(payload, dict):
        return None, _failure(
            root,
            malformed_reason,
            path,
            f"{relative_path.as_posix()} must contain a JSON object",
        )
    return payload, None


def _parse_json_bytes(
    root: Path,
    relative_path: Path,
    data: bytes,
    *,
    malformed_reason: str,
) -> tuple[dict[str, Any] | None, Failure | None]:
    try:
        payload = json.loads(data.decode("utf-8"))
    except UnicodeDecodeError:
        return None, _failure(
            root,
            malformed_reason,
            root / relative_path,
            f"{relative_path.as_posix()} is not valid UTF-8",
        )
    except JSONDecodeError as exc:
        return None, _failure(
            root,
            malformed_reason,
            root / relative_path,
            f"{relative_path.as_posix()} is not valid JSON: {exc.msg}",
        )
    if not isinstance(payload, dict):
        return None, _failure(
            root,
            malformed_reason,
            root / relative_path,
            f"{relative_path.as_posix()} must contain a JSON object",
        )
    return payload, None


def _load_contract(root: Path) -> tuple[dict[str, Any] | None, list[Failure]]:
    contract, failure = _read_json_file(
        root,
        CONTRACT_PATH,
        missing_reason="contract_missing",
        malformed_reason="contract_malformed",
    )
    if failure is not None:
        return None, [failure]
    assert contract is not None

    failures: list[Failure] = []
    if contract.get("schema_version") != CONTRACT_SCHEMA_VERSION:
        failures.append(
            _failure(
                root,
                "contract_malformed",
                root / CONTRACT_PATH,
                "install contract must have schema_version=1",
            )
        )
    if not isinstance(contract.get("plugin_name"), str) or not contract.get("plugin_name"):
        failures.append(
            _failure(
                root,
                "contract_malformed",
                root / CONTRACT_PATH,
                "install contract must name plugin_name",
            )
        )
    required = contract.get("required")
    if not isinstance(required, dict):
        failures.append(
            _failure(
                root,
                "contract_malformed",
                root / CONTRACT_PATH,
                "install contract must contain a required object",
            )
        )
    else:
        for key in ("skills", "agents", "templates", "hooks", "scripts"):
            if key not in required:
                failures.append(
                    _failure(
                        root,
                        "contract_malformed",
                        root / CONTRACT_PATH,
                        f"required.{key} is missing",
                    )
                )
    if failures:
        return None, failures
    return contract, []


def _normalize_skill_entries(
    root: Path, contract: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[Failure]]:
    required = contract["required"]
    raw_skills = required.get("skills")
    failures: list[Failure] = []
    normalized: list[dict[str, Any]] = []
    if not isinstance(raw_skills, list):
        return [], [
            _failure(
                root,
                "contract_malformed",
                root / CONTRACT_PATH,
                "required.skills must be a list",
            )
        ]

    for idx, entry in enumerate(raw_skills):
        if isinstance(entry, str):
            name = entry
            files: list[Any] = ["SKILL.md"]
        elif isinstance(entry, dict):
            name = entry.get("name")
            files = entry.get("files")
        else:
            name = None
            files = None

        if not isinstance(name, str) or not name:
            failures.append(
                _failure(
                    root,
                    "contract_malformed",
                    root / CONTRACT_PATH,
                    f"required.skills[{idx}] must name a skill",
                )
            )
            continue
        if not isinstance(files, list) or not all(isinstance(item, str) and item for item in files):
            failures.append(
                _failure(
                    root,
                    "contract_malformed",
                    root / CONTRACT_PATH,
                    f"required.skills[{idx}].files must be a list of paths",
                )
            )
            continue
        if "SKILL.md" not in files:
            failures.append(
                _failure(
                    root,
                    "contract_malformed",
                    root / CONTRACT_PATH,
                    f"required.skills[{idx}].files must include SKILL.md",
                )
            )
            continue
        normalized.append({"name": name, "files": files})
    return normalized, failures


def _require_string_list(
    root: Path, contract: dict[str, Any], key: str
) -> tuple[list[str], list[Failure]]:
    raw = contract["required"].get(key)
    if isinstance(raw, list) and all(isinstance(item, str) and item for item in raw):
        return list(raw), []
    return [], [
        _failure(
            root,
            "contract_malformed",
            root / CONTRACT_PATH,
            f"required.{key} must be a list of strings",
        )
    ]


def _validate_manifests(
    root: Path, contract: dict[str, Any]
) -> tuple[str | None, str | None, list[Failure]]:
    plugin_name = contract.get("plugin_name")
    version: str | None = None
    failures: list[Failure] = []

    plugin_manifest, failure = _read_json_file(
        root,
        PLUGIN_MANIFEST_PATH,
        missing_reason="manifest_missing",
        malformed_reason="manifest_malformed",
    )
    if failure is not None:
        failures.append(failure)
    elif plugin_manifest is not None:
        actual_name = plugin_manifest.get("name")
        if actual_name != plugin_name:
            failures.append(
                _failure(
                    root,
                    "manifest_mismatch",
                    root / PLUGIN_MANIFEST_PATH,
                    f"plugin manifest name {actual_name!r} does not match contract {plugin_name!r}",
                )
            )
        raw_version = plugin_manifest.get("version")
        if isinstance(raw_version, str) and raw_version:
            version = raw_version
        else:
            failures.append(
                _failure(
                    root,
                    "manifest_mismatch",
                    root / PLUGIN_MANIFEST_PATH,
                    "plugin manifest must contain a non-empty version string",
                )
            )

    marketplace, failure = _read_json_file(
        root,
        MARKETPLACE_PATH,
        missing_reason="manifest_missing",
        malformed_reason="manifest_malformed",
    )
    if failure is not None:
        failures.append(failure)
    elif marketplace is not None:
        marketplace_name = marketplace.get("name")
        if marketplace_name != plugin_name:
            failures.append(
                _failure(
                    root,
                    "manifest_mismatch",
                    root / MARKETPLACE_PATH,
                    f"marketplace name {marketplace_name!r} does not match "
                    f"contract {plugin_name!r}",
                )
            )
        plugin_entries = marketplace.get("plugins")
        if not isinstance(plugin_entries, list) or not any(
            isinstance(entry, dict) and entry.get("name") == plugin_name
            for entry in plugin_entries
        ):
            failures.append(
                _failure(
                    root,
                    "manifest_mismatch",
                    root / MARKETPLACE_PATH,
                    f"marketplace must contain a plugin entry named {plugin_name!r}",
                )
            )
    return plugin_name if isinstance(plugin_name, str) else None, version, failures


def _check_artifact_files(root: Path, relative_paths: Iterable[Path]) -> list[Failure]:
    failures: list[Failure] = []
    for relative_path in relative_paths:
        path = root / relative_path
        if not path.is_file():
            failures.append(
                _failure(
                    root,
                    "artifact_missing",
                    path,
                    f"required artifact {relative_path.as_posix()} is missing",
                )
            )
    return failures


def _artifact_paths_from_contract(
    root: Path, contract: dict[str, Any]
) -> tuple[list[Path], list[Failure]]:
    failures: list[Failure] = []
    artifacts: list[Path] = []

    skills, skill_failures = _normalize_skill_entries(root, contract)
    failures.extend(skill_failures)
    for skill in skills:
        for file_name in skill["files"]:
            artifacts.append(Path("skills") / skill["name"] / file_name)

    agents, agent_failures = _require_string_list(root, contract, "agents")
    failures.extend(agent_failures)
    artifacts.extend(Path("agents") / f"{agent}.md" for agent in agents)

    templates, template_failures = _require_string_list(root, contract, "templates")
    failures.extend(template_failures)
    artifacts.extend(Path("templates") / template for template in templates)

    hooks, hook_failures = _require_string_list(root, contract, "hooks")
    failures.extend(hook_failures)
    artifacts.extend(Path("hooks") / "scripts" / hook for hook in hooks)

    scripts, script_failures = _require_string_list(root, contract, "scripts")
    failures.extend(script_failures)
    artifacts.extend(Path("scripts") / script for script in scripts)

    return artifacts, failures


def verify_plugin(root: Path | str) -> VerificationResult:
    """Verify a servo plugin root against `.claude-plugin/install-contract.json`."""
    root_path = Path(root).resolve()
    contract, failures = _load_contract(root_path)
    if contract is None:
        return VerificationResult(
            mode="plugin",
            plugin_name=None,
            version=None,
            failures=tuple(failures),
        )

    plugin_name, version, manifest_failures = _validate_manifests(root_path, contract)
    failures.extend(manifest_failures)
    artifacts, artifact_contract_failures = _artifact_paths_from_contract(root_path, contract)
    failures.extend(artifact_contract_failures)
    if not artifact_contract_failures:
        failures.extend(_check_artifact_files(root_path, artifacts))

    return VerificationResult(
        mode="plugin",
        plugin_name=plugin_name,
        version=version,
        failures=tuple(failures),
    )


def _zip_failure(zip_path: Path, reason: str, member: str, message: str) -> Failure:
    path = f"{zip_path}:{member}" if member else str(zip_path)
    return Failure(reason=reason, path=path, message=message)


def _zip_member_is_unsafe(name: str) -> bool:
    path = Path(name)
    windows_path = PureWindowsPath(name)
    return (
        not name
        or name.startswith("/")
        or "\\" in name
        or bool(windows_path.drive)
        or windows_path.is_absolute()
        or path.is_absolute()
        or any(part == ".." for part in Path(name).parts)
    )


def _matches_glob(path: str, pattern: str) -> bool:
    normalized = path.strip("/")
    normalized_pattern = pattern.strip("/")
    if fnmatch.fnmatchcase(normalized, normalized_pattern):
        return True
    if normalized_pattern.startswith("**/"):
        return fnmatch.fnmatchcase(normalized, normalized_pattern[3:])
    return False


def _zip_forbidden_failures(
    zip_path: Path,
    names: Iterable[str],
    contract: dict[str, Any],
) -> list[Failure]:
    release_zip = contract.get("release_zip")
    if not isinstance(release_zip, dict):
        return [
            _zip_failure(
                zip_path,
                "contract_malformed",
                CONTRACT_PATH.as_posix(),
                "install contract must contain a release_zip object",
            )
        ]
    raw_globs = release_zip.get("exclude_globs")
    if not isinstance(raw_globs, list) or not all(isinstance(item, str) for item in raw_globs):
        return [
            _zip_failure(
                zip_path,
                "contract_malformed",
                CONTRACT_PATH.as_posix(),
                "release_zip.exclude_globs must be a list of strings",
            )
        ]
    failures: list[Failure] = []
    for name in sorted(names):
        if name.endswith("/"):
            continue
        for pattern in raw_globs:
            if _matches_glob(name, pattern):
                failures.append(
                    _zip_failure(
                        zip_path,
                        "artifact_forbidden",
                        name,
                        f"zip entry {name!r} matches forbidden pattern {pattern!r}",
                    )
                )
                break
    return failures


def _read_contract_from_zip(
    zip_path: Path,
    zf: zipfile.ZipFile,
) -> tuple[dict[str, Any] | None, list[Failure]]:
    try:
        data = zf.read(CONTRACT_PATH.as_posix())
    except KeyError:
        return None, [
            _zip_failure(
                zip_path,
                "contract_missing",
                CONTRACT_PATH.as_posix(),
                f"{CONTRACT_PATH.as_posix()} is missing",
            )
        ]
    contract, failure = _parse_json_bytes(
        zip_path,
        CONTRACT_PATH,
        data,
        malformed_reason="contract_malformed",
    )
    if failure is not None:
        return None, [failure]
    assert contract is not None
    if contract.get("schema_version") != CONTRACT_SCHEMA_VERSION:
        return None, [
            _zip_failure(
                zip_path,
                "contract_malformed",
                CONTRACT_PATH.as_posix(),
                "install contract must have schema_version=1",
            )
        ]
    return contract, []


def verify_zip(zip_path: Path | str) -> VerificationResult:
    """Verify a release zip, then smoke-check it as an extracted plugin root."""
    path = Path(zip_path).resolve()
    failures: list[Failure] = []
    if not path.is_file():
        return VerificationResult(
            mode="zip",
            plugin_name=None,
            version=None,
            failures=(
                Failure(
                    reason="zip_invalid",
                    path=str(path),
                    message="zip file is missing",
                ),
            ),
        )

    try:
        with zipfile.ZipFile(path) as zf:
            infos = zf.infolist()
            names = [info.filename for info in infos]
            for name in names:
                if _zip_member_is_unsafe(name):
                    failures.append(
                        _zip_failure(
                            path,
                            "zip_invalid",
                            name,
                            "zip entry uses an unsafe path",
                        )
                    )
            if failures:
                return VerificationResult(
                    mode="zip",
                    plugin_name=None,
                    version=None,
                    failures=tuple(failures),
                )

            contract, contract_failures = _read_contract_from_zip(path, zf)
            failures.extend(contract_failures)
            if contract is not None:
                failures.extend(_zip_forbidden_failures(path, names, contract))
            if failures:
                return VerificationResult(
                    mode="zip",
                    plugin_name=contract.get("plugin_name") if contract else None,
                    version=None,
                    failures=tuple(failures),
                )

            with tempfile.TemporaryDirectory(prefix="servo-zip-verify-") as tmp:
                extract_root = Path(tmp)
                zf.extractall(extract_root)
                plugin_result = verify_plugin(extract_root)
    except zipfile.BadZipFile:
        return VerificationResult(
            mode="zip",
            plugin_name=None,
            version=None,
            failures=(
                Failure(
                    reason="zip_invalid",
                    path=str(path),
                    message="zip file cannot be opened",
                ),
            ),
        )

    return VerificationResult(
        mode="zip",
        plugin_name=plugin_result.plugin_name,
        version=plugin_result.version,
        failures=plugin_result.failures,
    )


def _source_root() -> Path:
    """Servo source checkout that owns the install contract.

    `scripts/verify_install.py` sits one directory below the repo root, so the
    contract describing required artifacts lives at `<source>/.claude-plugin/`.
    The scaffold verifier inspects a target's vendored copy against that
    contract; the target itself does not carry the contract file.
    """
    return Path(__file__).resolve().parents[1]


def _scaffold_artifact_paths(
    target: Path,
    contract: dict[str, Any],
) -> tuple[list[Path], Path, list[Failure]]:
    """Return target-relative paths for managed scaffold artifacts.

    Also returns the scaffold manifest path (separately, so the verifier can
    distinguish a missing manifest from a missing artifact) and any contract
    malformations encountered while reading the scaffold/required blocks.
    """
    failures: list[Failure] = []
    scaffold = contract.get("scaffold")
    if not isinstance(scaffold, dict):
        failures.append(
            _failure(
                target,
                "contract_malformed",
                _source_root() / CONTRACT_PATH,
                "install contract must contain a scaffold object",
            )
        )
        return [], target, failures
    skill_prefix = scaffold.get("skill_prefix")
    agent_prefix = scaffold.get("agent_prefix")
    runtime_root = scaffold.get("runtime_root")
    for key, value in (
        ("skill_prefix", skill_prefix),
        ("agent_prefix", agent_prefix),
        ("runtime_root", runtime_root),
    ):
        if not isinstance(value, str) or not value:
            failures.append(
                _failure(
                    target,
                    "contract_malformed",
                    _source_root() / CONTRACT_PATH,
                    f"scaffold.{key} must be a non-empty string",
                )
            )
    if failures:
        return [], target, failures

    artifacts: list[Path] = []
    skills, skill_failures = _normalize_skill_entries(target, contract)
    failures.extend(skill_failures)
    for skill in skills:
        for file_name in skill["files"]:
            artifacts.append(
                Path(".claude") / "skills" / f"{skill_prefix}{skill['name']}" / file_name
            )

    agents, agent_failures = _require_string_list(target, contract, "agents")
    failures.extend(agent_failures)
    artifacts.extend(
        Path(".claude") / "agents" / f"{agent_prefix}{agent}.md" for agent in agents
    )

    templates, template_failures = _require_string_list(target, contract, "templates")
    failures.extend(template_failures)
    artifacts.extend(Path(runtime_root) / "templates" / template for template in templates)

    manifest_path = Path(runtime_root) / "scaffold-install.json"
    return artifacts, manifest_path, failures


# Markdown link `[text](dest)`; reused to find vendored links that escape the
# scaffold target or otherwise fail to resolve under it.
_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")

# Managed markdown is every vendored SKILL.md plus every vendored agent file.
_MANAGED_MD_SUFFIXES = ("SKILL.md",)


def _managed_markdown_paths(target: Path, contract: dict[str, Any]) -> list[Path]:
    """Target-relative paths of vendored markdown the verifier should scan.

    Scaffold-prefixed `SKILL.md` files (the skill docs) plus the prefixed agent
    files. Templates and the `.py` helpers are excluded: helpers are dual-mode
    by design (their `CLAUDE_PLUGIN_ROOT` docstrings are accurate), and
    templates are shell, not docs.
    """
    scaffold = contract["scaffold"]
    skill_prefix = scaffold["skill_prefix"]
    agent_prefix = scaffold["agent_prefix"]
    paths: list[Path] = []
    for skill in _normalize_skill_entries(target, contract)[0]:
        paths.append(
            Path(".claude") / "skills" / f"{skill_prefix}{skill['name']}" / "SKILL.md"
        )
    agents, _ = _require_string_list(target, contract, "agents")
    paths.extend(
        Path(".claude") / "agents" / f"{agent_prefix}{agent}.md" for agent in agents
    )
    return paths


def _stale_link_in(text: str, md_path: Path, target: Path) -> str | None:
    """Return the first unresolved repo-relative link in `text`, else None."""
    for match in _MD_LINK_RE.finditer(text):
        dest = match.group(2)
        if dest.startswith(("http://", "https://", "mailto:", "#")):
            continue
        path_part = dest.split("#", 1)[0]
        if not path_part:
            continue
        resolved = (md_path.parent / path_part).resolve()
        try:
            resolved.relative_to(target)
        except ValueError:
            return dest
        if not resolved.exists():
            return dest
    return None


def _scaffold_stale_reference_failures(
    target: Path,
    contract: dict[str, Any],
) -> list[Failure]:
    """Flag managed markdown that points at the original servo checkout (AC6).

    Two distinct stale-source signatures, both reported as
    `stale_source_reference` (separate from `artifact_missing`):
      - a literal `${CLAUDE_PLUGIN_ROOT}` (a plugin-checkout command that will
        not run in scaffold mode);
      - a relative markdown link that escapes the target or does not resolve
        inside it (a doc reference to a source-only file).
    Only existing managed files are scanned; a missing file is `artifact_missing`.
    """
    failures: list[Failure] = []
    for rel in _managed_markdown_paths(target, contract):
        path = target / rel
        if not path.is_file():
            continue
        text = path.read_text(errors="replace")
        if "${CLAUDE_PLUGIN_ROOT}" in text:
            failures.append(
                _failure(
                    target,
                    "stale_source_reference",
                    path,
                    f"{rel.as_posix()} references ${{CLAUDE_PLUGIN_ROOT}} "
                    "(a plugin-checkout path that does not exist in scaffold mode)",
                )
            )
        stale_link = _stale_link_in(text, path, target)
        if stale_link is not None:
            failures.append(
                _failure(
                    target,
                    "stale_source_reference",
                    path,
                    f"{rel.as_posix()} links to {stale_link!r}, which does not "
                    "resolve inside the scaffold target",
                )
            )
    return failures


def verify_scaffold(target: Path | str) -> VerificationResult:
    """Verify a project-local scaffold target against the servo install contract.

    The contract is read from the servo source checkout that ships this
    verifier; the scaffolded target carries vendored, servo-prefixed copies of
    the managed artifacts rather than the contract itself.
    """
    target_path = Path(target).resolve()
    contract, contract_failures = _load_contract(_source_root())
    if contract is None:
        return VerificationResult(
            mode="scaffold",
            plugin_name=None,
            version=None,
            failures=tuple(contract_failures),
        )

    plugin_name = contract.get("plugin_name")
    artifacts, manifest_rel, failures = _scaffold_artifact_paths(target_path, contract)
    if not failures:
        failures.extend(_check_artifact_files(target_path, artifacts))
        manifest_path = target_path / manifest_rel
        if not manifest_path.is_file():
            failures.append(
                _failure(
                    target_path,
                    "manifest_missing",
                    manifest_path,
                    f"scaffold manifest {manifest_rel.as_posix()} is missing",
                )
            )
        # AC6: distinguish "artifact exists but points at the wrong source"
        # from "artifact missing". Scans only managed markdown that is present.
        failures.extend(_scaffold_stale_reference_failures(target_path, contract))

    return VerificationResult(
        mode="scaffold",
        plugin_name=plugin_name if isinstance(plugin_name, str) else None,
        version=None,
        failures=tuple(failures),
    )


def _write_human(result: VerificationResult, out: TextIO) -> None:
    label = f"{result.mode} {result.plugin_name or '<unknown>'}"
    if result.ok:
        print(f"PASS {label} version={result.version or '<unknown>'}", file=out)
        return
    print(f"FAIL {label} version={result.version or '<unknown>'}", file=out)
    for failure in result.failures:
        print(
            f"{failure.reason}: {failure.path}: {failure.message}",
            file=out,
        )


def run_plugin(root: Path | str, *, json_output: bool = False, out: TextIO | None = None) -> int:
    if out is None:
        out = sys.stdout
    result = verify_plugin(root)
    if result.ok and result.version:
        write_availability_marker(root, "verify-plugin", result.version)
    if json_output:
        print(json.dumps(result.to_json(), sort_keys=True), file=out)
    else:
        _write_human(result, out)
    return 0 if result.ok else 1


def run_zip(zip_path: Path | str, *, json_output: bool = False, out: TextIO | None = None) -> int:
    if out is None:
        out = sys.stdout
    result = verify_zip(zip_path)
    if json_output:
        print(json.dumps(result.to_json(), sort_keys=True), file=out)
    else:
        _write_human(result, out)
    return 0 if result.ok else 1


def run_scaffold(
    target: Path | str, *, json_output: bool = False, out: TextIO | None = None
) -> int:
    if out is None:
        out = sys.stdout
    result = verify_scaffold(target)
    if json_output:
        print(json.dumps(result.to_json(), sort_keys=True), file=out)
    else:
        _write_human(result, out)
    return 0 if result.ok else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify servo install surfaces.")
    subparsers = parser.add_subparsers(dest="mode", required=True)

    plugin = subparsers.add_parser("plugin", help="verify a servo plugin root")
    plugin.add_argument("root", help="path to the plugin root")
    plugin.add_argument("--json", action="store_true", help="emit machine-readable JSON")

    zip_parser = subparsers.add_parser("zip", help="verify a servo release zip")
    zip_parser.add_argument("zip_path", help="path to the release zip")
    zip_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")

    scaffold = subparsers.add_parser("scaffold", help="verify a project-local scaffold target")
    scaffold.add_argument("target", help="path to the scaffolded target project")
    scaffold.add_argument("--json", action="store_true", help="emit machine-readable JSON")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    ns = parser.parse_args(argv)
    if ns.mode == "plugin":
        return run_plugin(ns.root, json_output=ns.json)
    if ns.mode == "zip":
        return run_zip(ns.zip_path, json_output=ns.json)
    if ns.mode == "scaffold":
        return run_scaffold(ns.target, json_output=ns.json)
    parser.error(f"unsupported mode: {ns.mode}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
