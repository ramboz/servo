#!/usr/bin/env python3
"""Build deterministic host-explicit Servo release archives from hosts/."""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import TextIO

ROOT = Path(__file__).resolve().parent.parent
HOSTS = ("claude", "codex")
MANIFESTS = {
    "claude": Path(".claude-plugin/plugin.json"),
    "codex": Path("plugins/servo/.codex-plugin/plugin.json"),
}
MTIME = (2026, 1, 1, 0, 0, 0)


def default_output_path(source_root: Path, host: str, version: str) -> Path:
    return source_root / "dist" / f"servo-{host}-v{version}.zip"


def _manifest_version(package_root: Path, host: str) -> str:
    manifest = package_root / MANIFESTS[host]
    data = json.loads(manifest.read_text())
    version = data.get("version")
    if not isinstance(version, str) or not version:
        raise ValueError(f"{manifest} must declare a version string")
    return version


def _files(package_root: Path) -> list[Path]:
    return sorted(
        (
            path.relative_to(package_root)
            for path in package_root.rglob("*")
            if path.is_file()
            and "__pycache__" not in path.parts
            and path.suffix != ".pyc"
            and path.name != ".DS_Store"
        ),
        key=lambda path: path.as_posix(),
    )


def _write(zf: zipfile.ZipFile, source: Path, rel: Path) -> None:
    mode = 0o755 if source.stat().st_mode & 0o111 else 0o644
    info = zipfile.ZipInfo(rel.as_posix(), MTIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = (mode & 0xFFFF) << 16
    info.create_system = 3
    zf.writestr(info, source.read_bytes())


def build(
    host: str,
    hosts_root: Path,
    version: str,
    output_path: Path,
    out: TextIO | None = None,
) -> int:
    if out is None:
        out = sys.stdout
    if host not in HOSTS:
        out.write(f"FAIL: unknown host {host!r}; expected claude or codex\n")
        return 1
    package_root = Path(hosts_root) / host
    try:
        if not package_root.is_dir():
            raise FileNotFoundError(
                f"committed {host} package missing at {package_root}; "
                "run python3 scripts/build_host_packages.py"
            )
        package_version = _manifest_version(package_root, host)
        if package_version != version:
            out.write(
                f"FAIL: version mismatch: requested {version!r}, committed {host} "
                f"package declares {package_version!r}\n"
            )
            return 2
        entries = _files(package_root)
        if not entries:
            raise ValueError(f"committed {host} package is empty")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for rel in entries:
                _write(zf, package_root / rel, rel)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        out.write(f"FAIL: {exc}\n")
        return 1
    if host == "codex":
        out.write(
            f"OK: built {output_path} ({len(entries)} entries, version {version}); "
            "Codex extract-then-add marketplace bundle.\n"
        )
    else:
        out.write(
            f"OK: built {output_path} ({len(entries)} entries, version {version}); "
            "flat Claude plugin.\n"
        )
    return 0


def _safe_names(zf: zipfile.ZipFile) -> tuple[set[str], str | None]:
    names: set[str] = set()
    for raw in zf.namelist():
        path = PurePosixPath(raw)
        windows_drive = bool(PureWindowsPath(raw).drive)
        if path.is_absolute() or windows_drive or ".." in path.parts or "\\" in raw:
            return set(), f"unsafe archive entry {raw!r}"
        names.add(raw)
    return names, None


def smoke_test(host: str, zip_path: Path, out: TextIO | None = None) -> int:
    if out is None:
        out = sys.stdout
    if host not in HOSTS:
        out.write(f"FAIL smoke[{host}]: unknown host\n")
        return 1
    try:
        with zipfile.ZipFile(zip_path) as zf:
            names, error = _safe_names(zf)
            if error:
                raise ValueError(error)
            committed_root = ROOT / "hosts" / host
            if not committed_root.is_dir():
                raise ValueError(
                    f"committed {host} package is unavailable; run "
                    "python3 scripts/build_host_packages.py"
                )
            expected = {rel.as_posix() for rel in _files(committed_root)}
            missing_runtime = sorted(expected - names)
            extra_runtime = sorted(names - expected)
            if missing_runtime:
                raise ValueError(
                    "missing committed runtime entries: "
                    + ", ".join(missing_runtime[:8])
                )
            if extra_runtime:
                raise ValueError(
                    "unexpected runtime entries: " + ", ".join(extra_runtime[:8])
                )
            modified = [
                name
                for name in sorted(expected)
                if zf.read(name) != (committed_root / name).read_bytes()
            ]
            if modified:
                raise ValueError(
                    "runtime entries differ from committed package: "
                    + ", ".join(modified[:8])
                )
            plugin_prefix = "" if host == "claude" else "plugins/servo/"
            required = {
                MANIFESTS[host].as_posix(),
                f"{plugin_prefix}README.md",
                f"{plugin_prefix}LICENSE",
                f"{plugin_prefix}servo.jpg",
            }
            if host == "codex":
                required.add(".agents/plugins/marketplace.json")
            missing = sorted(required - names)
            if missing:
                raise ValueError(f"missing required entries: {', '.join(missing)}")
            forbidden = (
                any(name.startswith("hosts/") for name in names)
                or (
                    host == "claude"
                    and any(
                        name.startswith((".codex-plugin/", ".agents/"))
                        for name in names
                    )
                )
                or (host == "codex" and any(name.startswith(".claude-plugin/") for name in names))
            )
            if forbidden:
                raise ValueError("archive contains content for the wrong host")
            manifest = json.loads(zf.read(MANIFESTS[host].as_posix()))
            if manifest.get("name") != "servo" or not manifest.get("version"):
                raise ValueError("plugin manifest is invalid")
    except (OSError, ValueError, KeyError, json.JSONDecodeError, zipfile.BadZipFile) as exc:
        out.write(f"FAIL smoke[{host}]: {exc}\n")
        return 1
    shape = "extract-then-add marketplace bundle" if host == "codex" else "flat plugin"
    out.write(f"PASS smoke[{host}]: validated {shape}.\n")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a Servo host release zip.")
    parser.add_argument("--host", required=True, choices=HOSTS)
    parser.add_argument("--version")
    parser.add_argument("--output")
    parser.add_argument("--hosts-root", default=str(ROOT / "hosts"))
    parser.add_argument("--smoke-test")
    parser.add_argument("--no-smoke", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv[1:]
    ns = _parser().parse_args(args)
    if ns.smoke_test:
        return smoke_test(ns.host, Path(ns.smoke_test))
    if not ns.version:
        _parser().error("--version is required when building")
    output = Path(ns.output) if ns.output else default_output_path(ROOT, ns.host, ns.version)
    rc = build(ns.host, Path(ns.hosts_root), ns.version, output)
    if rc == 0 and not ns.no_smoke:
        return smoke_test(ns.host, output)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
