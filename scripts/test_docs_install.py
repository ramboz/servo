"""Regression guards for Servo's public install and contributor docs."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
CONTRIBUTING = ROOT / "CONTRIBUTING.md"


class PublicInstallDocsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.readme = README.read_text(encoding="utf-8")

    def test_remote_marketplace_install_is_the_public_path(self) -> None:
        for command in (
            "/plugin marketplace add ramboz/servo",
            "/plugin install servo@servo",
            "codex plugin marketplace add ramboz/servo",
            "codex plugin add servo@servo",
        ):
            with self.subTest(command=command):
                self.assertIn(command, self.readme)

    def test_public_install_continues_with_project_setup(self) -> None:
        self.assertIn("Set up Servo for this project", self.readme)
        self.assertIn("/servo:scaffold-init", self.readme)
        self.assertIn("oracle.sh", self.readme)
        self.assertIn(".servo/install.json", self.readme)

    def test_readme_does_not_promote_maintainer_install_paths(self) -> None:
        for stale in (
            "Host-explicit release zip install",
            "scripts/scaffold_runtime.py",
            "scripts/build_release_zip.py",
            "scripts/verify_install_surfaces.sh",
            "<absolute-path-to-checkout>",
        ):
            with self.subTest(stale=stale):
                self.assertNotIn(stale, self.readme)

    def test_install_section_stays_compact(self) -> None:
        start = self.readme.index("### Install")
        end = self.readme.index("\n## ", start + len("### Install"))
        install = self.readme[start:end]
        self.assertLessEqual(len(install.splitlines()), 35)

    def test_reading_order_matches_the_dual_host_plugin_family(self) -> None:
        headings = (
            "## Why Servo",
            "## What it does",
            "## Principles Servo encodes",
            "## Start here",
            "### Install",
            "## Extension points",
            "## Verifying a host install",
            "## Getting started",
            "## Repository structure (for contributors)",
            "## Contributing",
            "## Status",
        )
        positions = [self.readme.index(heading) for heading in headings]
        self.assertEqual(positions, sorted(positions))

    def test_packaged_readme_links_survive_without_repository_docs(self) -> None:
        self.assertNotIn("](docs/", self.readme)
        self.assertNotIn("](CONTRIBUTING.md)", self.readme)
        self.assertNotIn("](LICENSE)", self.readme)


class ContributorDocsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contributing = CONTRIBUTING.read_text(encoding="utf-8")

    def test_local_ci_has_one_canonical_entry_point(self) -> None:
        self.assertIn("python3 scripts/ci_check.py", self.contributing)

    def test_claude_local_development_loads_the_generated_package(self) -> None:
        self.assertIn('claude --plugin-dir "$(pwd)/hosts/claude"', self.contributing)
        self.assertNotIn("/plugin marketplace add .", self.contributing)

    def test_maintainer_docs_own_package_and_release_details(self) -> None:
        for text in (
            "scripts/build_host_packages.py",
            "scripts/build_release_zip.py --host claude",
            "scripts/build_release_zip.py --host codex",
            "servo-claude-v<version>.zip",
            "servo-codex-v<version>.zip",
        ):
            with self.subTest(text=text):
                self.assertIn(text, self.contributing)


if __name__ == "__main__":
    unittest.main()
