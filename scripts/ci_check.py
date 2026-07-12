"""Run Servo's GitHub CI checks locally, in the same order."""

from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, TextIO

ROOT = Path(__file__).resolve().parent.parent
RUFF_COMMAND = ("pipx", "run", "--spec", "ruff==0.15.17", "ruff", "check", ".")


@dataclass(frozen=True)
class CheckStep:
    name: str
    argv: tuple[str, ...]


def ci_steps(python: str = sys.executable) -> tuple[CheckStep, ...]:
    return (
        CheckStep("Run test suite", (python, "scripts/run_tests.py")),
        CheckStep("Validate manifests", (python, "scripts/validate_manifests.py")),
        CheckStep("Code-health floor", RUFF_COMMAND),
        CheckStep("Verify install surfaces", ("bash", "scripts/verify_install_surfaces.sh")),
        CheckStep(
            "Host-package drift guard",
            (python, "scripts/build_host_packages.py", "--check"),
        ),
    )


def dependencies_available(
    which: Callable[[str], str | None] = shutil.which,
    stderr: TextIO = sys.stderr,
) -> bool:
    launcher = RUFF_COMMAND[0]
    if which(launcher):
        return True
    stderr.write(
        f"missing local CI dependency: {launcher!r} is not on PATH\n"
    )
    return False


def run_steps(
    steps: tuple[CheckStep, ...],
    root: Path = ROOT,
    run: Callable[..., subprocess.CompletedProcess[bytes]] = subprocess.run,
) -> int:
    for step in steps:
        print(f"\n==> {step.name}", flush=True)
        result = run(step.argv, cwd=str(root))
        if result.returncode != 0:
            return result.returncode
    return 0


def main() -> int:
    if not dependencies_available():
        return 2
    return run_steps(ci_steps())


if __name__ == "__main__":
    raise SystemExit(main())
