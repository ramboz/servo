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

    def test_documented_zip_artifact_name_is_version_neutral(self) -> None:
        # Spec 010: releases are automated and release-please bumps
        # .claude-plugin/plugin.json on every release WITHOUT touching the
        # README. So the README must document the artifact *shape*
        # (servo-v<version>.zip), not a pinned concrete version — a pinned
        # version would go stale and redden the release PR's own CI on the
        # first bump. (Supersedes the earlier exact-version guard from 007-05,
        # which was correct only while the version was hand-edited.)
        self.assertIn(
            "servo-v<version>.zip",
            self.readme,
            "README should document the version-neutral artifact name "
            "servo-v<version>.zip (it survives release-please version bumps)",
        )
        pinned = re.search(r"servo-v\d+\.\d+\.\d+\.zip", self.readme)
        self.assertIsNone(
            pinned,
            f"README pins a concrete version ({pinned.group(0) if pinned else ''}); use the "
            "servo-v<version>.zip placeholder so docs survive release-please bumps",
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
