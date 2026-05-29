#!/usr/bin/env python3
"""Verify servo install surfaces.

Slices 007-01 and 007-02 implement plugin-root and release-zip
verification. Scaffold verification lands in slice 007-03.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from json import JSONDecodeError
from pathlib import Path, PureWindowsPath
from typing import Any, Iterable, TextIO


OUTPUT_SCHEMA_VERSION = 1
CONTRACT_SCHEMA_VERSION = 1
CONTRACT_PATH = Path(".claude-plugin") / "install-contract.json"
PLUGIN_MANIFEST_PATH = Path(".claude-plugin") / "plugin.json"
MARKETPLACE_PATH = Path(".claude-plugin") / "marketplace.json"


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


def _normalize_skill_entries(root: Path, contract: dict[str, Any]) -> tuple[list[dict[str, Any]], list[Failure]]:
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


def _require_string_list(root: Path, contract: dict[str, Any], key: str) -> tuple[list[str], list[Failure]]:
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


def _validate_manifests(root: Path, contract: dict[str, Any]) -> tuple[str | None, str | None, list[Failure]]:
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
                    f"marketplace name {marketplace_name!r} does not match contract {plugin_name!r}",
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


def _artifact_paths_from_contract(root: Path, contract: dict[str, Any]) -> tuple[list[Path], list[Failure]]:
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


def _write_human(result: VerificationResult, out: TextIO) -> None:
    if result.ok:
        print(
            f"PASS plugin {result.plugin_name or '<unknown>'} "
            f"version={result.version or '<unknown>'}",
            file=out,
        )
        return
    print(
        f"FAIL plugin {result.plugin_name or '<unknown>'} "
        f"version={result.version or '<unknown>'}",
        file=out,
    )
    for failure in result.failures:
        print(
            f"{failure.reason}: {failure.path}: {failure.message}",
            file=out,
        )


def run_plugin(root: Path | str, *, json_output: bool = False, out: TextIO | None = None) -> int:
    if out is None:
        out = sys.stdout
    result = verify_plugin(root)
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify servo install surfaces.")
    subparsers = parser.add_subparsers(dest="mode", required=True)

    plugin = subparsers.add_parser("plugin", help="verify a servo plugin root")
    plugin.add_argument("root", help="path to the plugin root")
    plugin.add_argument("--json", action="store_true", help="emit machine-readable JSON")

    zip_parser = subparsers.add_parser("zip", help="verify a servo release zip")
    zip_parser.add_argument("zip_path", help="path to the release zip")
    zip_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    ns = parser.parse_args(argv)
    if ns.mode == "plugin":
        return run_plugin(ns.root, json_output=ns.json)
    if ns.mode == "zip":
        return run_zip(ns.zip_path, json_output=ns.json)
    parser.error(f"unsupported mode: {ns.mode}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
