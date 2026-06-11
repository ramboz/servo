"""
Tests for slice 007-05 (docs-and-ci).

Automates "docs reviewed for stale path examples": asserts that every script
path the README install section references actually exists on disk, and that
the README documents all three runtime-install surfaces plus the manual
release recipe. A renamed or deleted install helper makes these fail.

Run from the repo root:
    python3 scripts/test_docs_install.py
or with discovery:
    python3 -m unittest discover -s scripts -p 'test_*.py'
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
README = REPO_ROOT / "README.md"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"

# Every script path the README install section hands the reader. If any of
# these is renamed or removed, the docs go stale silently — this list is the
# guard.
REFERENCED_SCRIPTS = (
    "scripts/verify_install.py",
    "scripts/build_release_zip.py",
    "scripts/scaffold_runtime.py",
    "scripts/verify_install_surfaces.sh",
)


class ReadmeInstallSectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.readme = README.read_text()

    def test_install_section_present(self) -> None:
        self.assertIn("## Installing servo", self.readme)

    def test_three_runtime_surfaces_documented(self) -> None:
        for heading in (
            "### Plugin install",
            "### Release zip install",
            "### Project-local scaffold install",
        ):
            self.assertIn(heading, self.readme, f"missing README heading: {heading}")

    def test_two_layer_distinction_stated(self) -> None:
        # AC1/AC2: runtime install vs project oracle install must be explicit.
        self.assertIn("Servo runtime install", self.readme)
        self.assertIn("Project oracle install", self.readme)

    def test_release_recipe_present(self) -> None:
        self.assertIn("### Release recipe", self.readme)
        # AC5: the recipe must name the produced artifact shape.
        self.assertIn("dist/servo-v", self.readme)

    def test_verification_command_documented(self) -> None:
        # AC3: the single verification command is documented.
        self.assertIn("bash scripts/verify_install_surfaces.sh", self.readme)

    def test_referenced_scripts_exist(self) -> None:
        # "Docs reviewed for stale path examples": every script the install
        # section mentions must be present in the README *and* on disk.
        for rel in REFERENCED_SCRIPTS:
            with self.subTest(script=rel):
                self.assertIn(rel, self.readme, f"README does not reference {rel}")
                self.assertTrue(
                    (REPO_ROOT / rel).is_file(),
                    f"referenced script does not exist: {rel}",
                )

    def test_documented_zip_command_matches_real_output_name(self) -> None:
        # AC5: the `verify_install.py zip <path>` example in the README must
        # use the real default builder output name, not an invented one. Read
        # the plugin version and assert the example zip path matches.
        plugin_version = re.search(
            r'"version"\s*:\s*"([^"]+)"',
            (REPO_ROOT / ".claude-plugin" / "plugin.json").read_text(),
        )
        self.assertIsNotNone(plugin_version, "plugin.json has no version")
        expected = f"dist/servo-v{plugin_version.group(1)}.zip"
        self.assertIn(
            expected,
            self.readme,
            f"README zip example should reference {expected}",
        )


class CiWorkflowTests(unittest.TestCase):
    # Spec 009-01 retired verify.yml in favour of a single ci.yml (test matrix +
    # install-surfaces job). These guards still assert the same thing — the
    # install-surface verification command runs in CI on push and PR — they
    # just point at the new workflow file.
    def test_workflow_file_exists(self) -> None:
        # AC4: the install-surface gate is still wired into CI.
        self.assertTrue(WORKFLOW.is_file(), "missing .github/workflows/ci.yml")

    def test_workflow_runs_verification_command(self) -> None:
        text = WORKFLOW.read_text()
        self.assertIn("bash scripts/verify_install_surfaces.sh", text)
        # Triggers on push and pull_request.
        self.assertIn("push:", text)
        self.assertIn("pull_request:", text)


if __name__ == "__main__":
    unittest.main()
