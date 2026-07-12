"""Contract tests for Servo's CI-equivalent local gate."""

from __future__ import annotations

import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ci_check


class CiCheckTests(unittest.TestCase):
    def test_step_roster_matches_ci_order(self) -> None:
        steps = ci_check.ci_steps("python3")
        self.assertEqual(
            [step.name for step in steps],
            [
                "Run test suite",
                "Validate manifests",
                "Code-health floor",
                "Verify install surfaces",
                "Host-package drift guard",
            ],
        )
        self.assertEqual(steps[0].argv, ("python3", "scripts/run_tests.py"))
        self.assertEqual(
            steps[-1].argv,
            ("python3", "scripts/build_host_packages.py", "--check"),
        )

    def test_github_workflow_uses_the_same_commands_in_the_same_order(self) -> None:
        workflow = (Path(__file__).resolve().parents[1] / ".github/workflows/ci.yml").read_text(
            encoding="utf-8"
        )
        expected = [" ".join(step.argv) for step in ci_check.ci_steps("python3")]
        positions = [workflow.index(command) for command in expected]
        self.assertEqual(positions, sorted(positions))

    def test_run_steps_stops_at_first_failure(self) -> None:
        calls: list[tuple[tuple[str, ...], str]] = []

        def fake_run(argv: tuple[str, ...], cwd: str):
            calls.append((argv, cwd))
            return SimpleNamespace(returncode=9)

        with redirect_stdout(io.StringIO()):
            result = ci_check.run_steps(
                ci_check.ci_steps("python3"),
                root=Path("/tmp/servo"),
                run=fake_run,
            )

        self.assertEqual(result, 9)
        self.assertEqual(len(calls), 1)

    def test_dependency_preflight_checks_the_pinned_lint_launcher(self) -> None:
        stderr = io.StringIO()
        result = ci_check.dependencies_available(
            which=lambda _name: None,
            stderr=stderr,
        )
        self.assertFalse(result)
        self.assertIn("pipx", stderr.getvalue())

    def test_pinned_lint_command_is_code_owned(self) -> None:
        self.assertEqual(
            ci_check.RUFF_COMMAND,
            ("pipx", "run", "--spec", "ruff==0.15.17", "ruff", "check", "."),
        )


if __name__ == "__main__":
    unittest.main()
