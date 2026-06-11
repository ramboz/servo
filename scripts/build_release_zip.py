#!/usr/bin/env python3
"""Build a deterministic runtime-only servo release zip.

The zip is flat at archive root and is verified by `verify_install.py zip`
by default after every build.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
import zipfile
from pathlib import Path, PureWindowsPath
from typing import Any, Iterable, TextIO

CONTRACT_PATH = Path(".claude-plugin") / "install-contract.json"
PLUGIN_MANIFEST_PATH = Path(".claude-plugin") / "plugin.json"
DEFAULT_MTIME = (2026, 1, 1, 0, 0, 0)


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def plugin_version(source_root: Path) -> str:
    manifest = _read_json(source_root / PLUGIN_MANIFEST_PATH)
    version = manifest.get("version")
    if not isinstance(version, str) or not version:
        raise ValueError(f"{PLUGIN_MANIFEST_PATH.as_posix()} must contain a version string")
    return version


def load_contract(source_root: Path) -> dict[str, Any]:
    contract = _read_json(source_root / CONTRACT_PATH)
    if contract.get("schema_version") != 1:
        raise ValueError("install contract must have schema_version=1")
    release_zip = contract.get("release_zip")
    if not isinstance(release_zip, dict):
        raise ValueError("install contract must contain release_zip")
    for key in ("include", "exclude_globs"):
        value = release_zip.get(key)
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise ValueError(f"release_zip.{key} must be a list of strings")
    return contract


def _matches_glob(path: str, pattern: str) -> bool:
    normalized = path.strip("/")
    normalized_pattern = pattern.strip("/")
    if fnmatch.fnmatchcase(normalized, normalized_pattern):
        return True
    if normalized_pattern.startswith("**/"):
        return fnmatch.fnmatchcase(normalized, normalized_pattern[3:])
    return False


def _is_excluded(rel: Path, exclude_globs: Iterable[str]) -> bool:
    rel_text = rel.as_posix()
    return any(_matches_glob(rel_text, pattern) for pattern in exclude_globs)


def _release_path_is_unsafe(path: str) -> bool:
    candidate = path.rstrip("/")
    posix_path = Path(candidate)
    windows_path = PureWindowsPath(candidate)
    return (
        not candidate
        or candidate.startswith("/")
        or "\\" in candidate
        or bool(windows_path.drive)
        or windows_path.is_absolute()
        or posix_path.is_absolute()
        or any(part == ".." for part in posix_path.parts)
    )


def iter_release_files(source_root: Path, contract: dict[str, Any]) -> list[Path]:
    """Return sorted source-relative file paths for the release archive."""
    release_zip = contract["release_zip"]
    includes = release_zip["include"]
    exclude_globs = release_zip["exclude_globs"]
    entries: set[Path] = set()

    for include in includes:
        if _release_path_is_unsafe(include):
            raise ValueError(f"release include path is unsafe: {include!r}")
        include_path = Path(include.rstrip("/"))
        source_path = source_root / include_path
        if not source_path.exists():
            raise FileNotFoundError(f"release include path is missing: {include_path.as_posix()}")
        if source_path.is_file():
            if not _is_excluded(include_path, exclude_globs):
                entries.add(include_path)
            continue
        if source_path.is_dir():
            for path in source_path.rglob("*"):
                if not path.is_file():
                    continue
                rel = path.relative_to(source_root)
                if _is_excluded(rel, exclude_globs):
                    continue
                entries.add(rel)
            continue
        raise ValueError(
            f"release include path is neither file nor directory: {include_path.as_posix()}"
        )

    sorted_entries = sorted(entries, key=lambda rel: rel.as_posix())
    for rel in sorted_entries:
        if _release_path_is_unsafe(rel.as_posix()):
            raise ValueError(f"release archive path is unsafe: {rel.as_posix()!r}")
    return sorted_entries


def _version_from_output_name(output_path: Path) -> str | None:
    match = re.fullmatch(r"servo-v(.+)\.zip", output_path.name)
    return match.group(1) if match else None


def _validate_requested_version(
    manifest_version: str,
    requested_version: str | None,
    output_path: Path,
    out: TextIO,
) -> int:
    if requested_version is not None and requested_version != manifest_version:
        out.write(
            f"FAIL: version mismatch: requested {requested_version!r} "
            f"but {PLUGIN_MANIFEST_PATH.as_posix()} declares {manifest_version!r}\n"
        )
        return 2
    output_version = _version_from_output_name(output_path)
    if output_version is not None and output_version != manifest_version:
        out.write(
            f"FAIL: output filename {output_path.name!r} declares version "
            f"{output_version!r} but {PLUGIN_MANIFEST_PATH.as_posix()} declares "
            f"{manifest_version!r}\n"
        )
        return 2
    return 0


def _write_zip_entry(zf: zipfile.ZipFile, source_path: Path, rel: Path) -> None:
    mode = 0o755 if source_path.stat().st_mode & 0o111 else 0o644
    info = zipfile.ZipInfo(filename=rel.as_posix(), date_time=DEFAULT_MTIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = (mode & 0xFFFF) << 16
    info.create_system = 3
    zf.writestr(info, source_path.read_bytes())


def smoke_test(zip_path: Path, out: TextIO | None = None) -> int:
    if out is None:
        out = sys.stdout
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import verify_install  # noqa: E402

    return verify_install.run_zip(zip_path, out=out)


def build(
    source_root: Path,
    output_path: Path | None = None,
    *,
    version: str | None = None,
    smoke: bool = True,
    out: TextIO | None = None,
) -> int:
    """Build a release zip.

    Returns 0 on success, 1 on build/smoke failure, 2 on version mismatch.
    """
    if out is None:
        out = sys.stdout
    source_root = source_root.resolve()
    try:
        manifest_version = plugin_version(source_root)
        contract = load_contract(source_root)
        output = (
            output_path
            if output_path is not None
            else source_root / "dist" / f"servo-v{manifest_version}.zip"
        )
        output = output.resolve()
        version_rc = _validate_requested_version(manifest_version, version, output, out)
        if version_rc != 0:
            return version_rc
        entries = iter_release_files(source_root, contract)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        out.write(f"FAIL: {exc}\n")
        return 1

    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel in entries:
            _write_zip_entry(zf, source_root / rel, rel)

    out.write(f"OK: built {output} ({len(entries)} entries, version {manifest_version})\n")

    if smoke:
        smoke_rc = smoke_test(output, out=out)
        if smoke_rc != 0:
            return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a servo release zip.")
    parser.add_argument(
        "--source-root",
        default=str(Path(__file__).resolve().parent.parent),
        help="path to servo source root",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="output zip path (default: dist/servo-v<plugin-version>.zip)",
    )
    parser.add_argument(
        "--version",
        default=None,
        help="optional requested version; must match .claude-plugin/plugin.json",
    )
    parser.add_argument(
        "--no-smoke",
        action="store_true",
        help="skip post-build zip verification",
    )
    parser.add_argument(
        "--smoke-test",
        metavar="ZIP",
        default=None,
        help="verify an existing zip instead of building",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    ns = parser.parse_args(argv)
    if ns.smoke_test is not None:
        return smoke_test(Path(ns.smoke_test))
    return build(
        source_root=Path(ns.source_root),
        output_path=Path(ns.output) if ns.output else None,
        version=ns.version,
        smoke=not ns.no_smoke,
    )


if __name__ == "__main__":
    raise SystemExit(main())
