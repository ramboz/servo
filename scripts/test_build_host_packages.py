from __future__ import annotations

import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))

import build_host_packages  # noqa: E402


def file_map(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
    }


class HostPackageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="servo-host-packages-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.hosts = self.tmp / "hosts"
        out = io.StringIO()
        self.assertEqual(
            build_host_packages.build_all(REPO_ROOT, self.hosts, out=out),
            0,
            out.getvalue(),
        )

    def test_builds_flat_claude_and_codex_marketplace(self):
        self.assertTrue((self.hosts / "claude/.claude-plugin/plugin.json").is_file())
        self.assertTrue((self.hosts / "codex/.agents/plugins/marketplace.json").is_file())
        self.assertTrue(
            (self.hosts / "codex/plugins/servo/.codex-plugin/plugin.json").is_file()
        )

    def test_manifests_share_canonical_version(self):
        canonical = json.loads((REPO_ROOT / ".claude-plugin/plugin.json").read_text())
        claude = json.loads(
            (self.hosts / "claude/.claude-plugin/plugin.json").read_text()
        )
        codex = json.loads(
            (self.hosts / "codex/plugins/servo/.codex-plugin/plugin.json").read_text()
        )
        self.assertEqual(claude["version"], canonical["version"])
        self.assertEqual(codex["version"], canonical["version"])

    def test_runtime_inventory_and_exclusions(self):
        for plugin in (
            self.hosts / "claude",
            self.hosts / "codex/plugins/servo",
        ):
            self.assertTrue((plugin / "README.md").is_file())
            self.assertTrue((plugin / "LICENSE").is_file())
            self.assertTrue((plugin / "servo.jpg").is_file())
            self.assertTrue((plugin / "agents/runner.md").is_file())
            self.assertTrue((plugin / "templates/oracle.sh.template").is_file())
            source_skills = {
                p.parent.name for p in (REPO_ROOT / "skills").glob("*/SKILL.md")
            }
            packaged_skills = {p.parent.name for p in (plugin / "skills").glob("*/SKILL.md")}
            self.assertEqual(packaged_skills, source_skills)
            offenders = [
                p.relative_to(plugin).as_posix()
                for p in plugin.rglob("*")
                if p.is_file()
                and (
                    p.name.startswith("test_")
                    or p.suffix == ".pyc"
                    or "__pycache__" in p.parts
                    or ".pytest_cache" in p.parts
                )
            ]
            self.assertEqual(offenders, [])

    def test_host_specific_content_is_not_leaked(self):
        claude = self.hosts / "claude"
        self.assertFalse((claude / ".codex-plugin").exists())
        self.assertFalse((claude / ".claude-plugin/marketplace.json").exists())
        self.assertFalse((claude / ".agents").exists())
        codex_plugin = self.hosts / "codex/plugins/servo"
        self.assertFalse((codex_plugin / ".claude-plugin").exists())

    def test_codex_rewrites_only_skill_plugin_root_paths(self):
        codex = self.hosts / "codex/plugins/servo"
        skill_text = "\n".join(p.read_text() for p in (codex / "skills").glob("*/SKILL.md"))
        self.assertNotIn("${CLAUDE_PLUGIN_ROOT}", skill_text)
        self.assertIn("${PLUGIN_ROOT}/skills/", skill_text)
        # Genuine host/runtime discussion remains truthful.
        self.assertIn("Claude Code", (codex / "skills/agent-loop/SKILL.md").read_text())

    def test_codex_skill_names_rely_on_plugin_namespace_once(self):
        codex = self.hosts / "codex/plugins/servo/skills"
        for skill in codex.glob("*/SKILL.md"):
            with self.subTest(skill=skill.parent.name):
                name_line = next(
                    line for line in skill.read_text().splitlines() if line.startswith("name:")
                )
                self.assertEqual(name_line, f"name: {skill.parent.name}")

    def test_codex_skill_descriptions_fit_discovery_metadata(self):
        codex = self.hosts / "codex/plugins/servo/skills"
        for skill in codex.glob("*/SKILL.md"):
            with self.subTest(skill=skill.parent.name):
                frontmatter = skill.read_text().split("---", 2)[1]
                self.assertIn("description: >-", frontmatter)
                description = frontmatter.split("description: >-", 1)[1].strip()
                self.assertLessEqual(len(description), 1024)

    def test_eval_authoring_discovery_description_preserves_routing_boundary(self):
        source = (REPO_ROOT / "skills/eval-authoring/SKILL.md").read_bytes()
        first = build_host_packages._render_codex_skill(source, "eval-authoring")
        second = build_host_packages._render_codex_skill(source, "eval-authoring")
        self.assertEqual(first, second)
        description = first.decode().split("---", 2)[1].split("description: >-", 1)[1].strip()
        self.assertLessEqual(len(description), 1024)
        self.assertIn("free-form goal", description)
        self.assertIn("Do NOT use", description)
        self.assertIn("design/content fidelity", description)
        self.assertIn("generic surface", description)

    def test_overlong_codex_description_refuses_instead_of_truncating_semantics(self):
        source = b"---\nname: servo:example\ndescription: >-\n  " + b"x" * 1025 + b"\n---\nbody\n"
        with self.assertRaisesRegex(ValueError, "shorten its first paragraph"):
            build_host_packages._render_codex_skill(source, "example")

    def test_repeated_builds_are_identical_and_replace_stale_files(self):
        other = self.tmp / "other"
        self.assertEqual(build_host_packages.build_all(REPO_ROOT, other, io.StringIO()), 0)
        self.assertEqual(file_map(self.hosts), file_map(other))
        stale = self.hosts / "claude/STALE"
        stale.write_text("stale")
        self.assertEqual(build_host_packages.build_all(REPO_ROOT, self.hosts, io.StringIO()), 0)
        self.assertFalse(stale.exists())


class DriftTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="servo-host-drift-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.hosts = self.tmp / "hosts"
        self.assertEqual(build_host_packages.build_all(REPO_ROOT, self.hosts, io.StringIO()), 0)

    def test_check_passes_in_sync_without_mutation(self):
        before = file_map(self.hosts)
        out = io.StringIO()
        self.assertEqual(build_host_packages.check_drift(REPO_ROOT, self.hosts, out), 0)
        self.assertEqual(file_map(self.hosts), before)

    def test_check_names_drift_and_regeneration_command(self):
        stale = self.hosts / "claude/.claude-plugin/plugin.json"
        stale.write_text("stale")
        out = io.StringIO()
        self.assertEqual(build_host_packages.check_drift(REPO_ROOT, self.hosts, out), 1)
        self.assertIn("claude/.claude-plugin/plugin.json", out.getvalue())
        self.assertIn("python3 scripts/build_host_packages.py", out.getvalue())


if __name__ == "__main__":
    unittest.main()
