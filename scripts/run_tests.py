"""Run Servo's complete pytest suite through the available local launcher."""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def pytest_command() -> tuple[str, ...] | None:
    if importlib.util.find_spec("pytest") is not None:
        return (sys.executable, "-m", "pytest")
    if shutil.which("uvx"):
        return ("uvx", "pytest")
    return None


def main() -> int:
    command = pytest_command()
    if command is None:
        sys.stderr.write("pytest is unavailable; install pytest or uvx\n")
        return 2
    return subprocess.run(command, cwd=str(ROOT)).returncode


if __name__ == "__main__":
    raise SystemExit(main())
