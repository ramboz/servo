"""Bounded native/startup closure and invocation helpers; no evaluation policy."""

import os
import platform
import site
import subprocess
import sys
import uuid
from pathlib import Path

import evidence_io as bundle
from evidence_io import require


def _native_dependencies(files, programs):
    """Close non-OS absolute linkage; browser assets are separately inventoried."""
    require(
        platform.system() == "Darwin" and Path("/usr/bin/otool").is_file(),
        "this bounded native-linkage preparation requires the pinned macOS runtime",
    )
    pending = {Path(path).resolve() for path in programs}
    pending.update(
        Path(module.__file__).resolve()
        for module in list(sys.modules.values())
        if getattr(module, "__file__", None) and Path(module.__file__).suffix in (".so", ".dylib")
    )
    pending.update(path for path in files if path.name == "node")
    pending.update(path for path in files if path.suffix == ".so")
    seen, resolutions = set(), {}
    while pending:
        path = pending.pop()
        if path in seen:
            continue
        seen.add(path)
        require(path in files, "unlisted native module: " + str(path))
        process = subprocess.run(
            ["/usr/bin/otool", "-L", str(path)],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        require(process.returncode == 0, "native linkage unavailable: " + str(path))
        for line in process.stdout.splitlines()[1:]:
            if not line.strip() or (line.startswith(str(path)) and line.rstrip().endswith(":")):
                continue
            name = line.strip().split(" (compatibility", 1)[0]
            if name.startswith(("/usr/lib/", "/System/Library/")):
                continue
            if name.startswith("@loader_path/"):
                name = os.path.normpath(str(path.parent / name.removeprefix("@loader_path/")))
            require(name.startswith("/"), "unsupported relative native linkage: " + name)
            dependency = Path(name).resolve()
            require(
                dependency in files or name.startswith(("/opt/homebrew/", "/usr/local/")),
                "unapproved native dependency location: " + name,
            )
            require(dependency.is_file(), "native dependency unavailable: " + name)
            files.add(dependency)
            resolutions[name] = {
                "path": name,
                "resolved": str(dependency),
                "hash": bundle.file_hash(dependency),
            }
            if dependency not in seen:
                pending.add(dependency)
    return [resolutions[name] for name in sorted(resolutions)]


def check_startup_environment(prefix, roots):
    prefix = Path(prefix).resolve()
    require(
        (prefix / "pyvenv.cfg").is_file() and site.ENABLE_USER_SITE is False,
        "closed virtualenv startup configuration required",
    )
    customization = sys.modules.get("sitecustomize")
    origin = getattr(customization, "__file__", None)
    require(
        (
            customization is None
            or (
                origin is not None
                and Path(origin).resolve().is_relative_to(Path(sys.base_prefix).resolve())
            )
        )
        and "usercustomize" not in sys.modules,
        "unsupported executable Python startup customization",
    )
    for directory in roots:
        root = Path(directory).resolve()
        require(root.is_relative_to(prefix), "unapproved startup package root")
        require(
            not list(root.glob("*.pth"))
            and not (root / "sitecustomize.py").exists()
            and not (root / "usercustomize.py").exists(),
            "unsupported executable startup files",
        )
    require(
        not any(
            value
            for key, value in os.environ.items()
            if key.startswith("DYLD_") or key in ("LD_PRELOAD", "LD_LIBRARY_PATH")
        ),
        "unsupported native loader environment",
    )
    require(
        not any(
            os.environ.get(name)
            for name in ("PLAYWRIGHT_NODEJS_PATH", "NODE_OPTIONS", "NODE_PATH")
        ),
        "unsupported Playwright Node startup override",
    )


def _run_id(target):
    run_id = os.environ.get("SERVO_GATE_RUN_ID", "")
    require(str(uuid.UUID(run_id)) == run_id, "invalid current gate run")
    invocation = target / ".servo" / "gate-runs" / run_id
    require(
        Path(os.environ.get("SERVO_GATE_RESULT_DIR", "")).resolve() == invocation.resolve(),
        "unbound current gate invocation",
    )
    require(
        bundle.load(invocation / "invocation.json")
        == {
            "schema_version": 1,
            "kind": "gate_invocation",
            "run_id": run_id,
        },
        "missing current invocation ownership",
    )
    return run_id


def _summary(rows):
    groups = {
        status: [r["id"] for r in rows if r["status"] == status]
        for status in ("pass", "fail", "unknown")
    }
    status = "unknown" if groups["unknown"] else "fail" if groups["fail"] else "pass"
    return {
        "status": "env_error" if status == "unknown" else status,
        "required_status": status,
        "passed": groups["pass"],
        "failed": groups["fail"],
        "unknown": groups["unknown"],
        "counts": {status: len(values) for status, values in groups.items()},
    }
