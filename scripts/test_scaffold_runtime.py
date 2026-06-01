"""
Tests for slice 007-03 (`scripts/scaffold_runtime.py`).

Run from the repo root:
    python3 scripts/test_scaffold_runtime.py
or with pytest:
    uvx pytest -q scripts/test_scaffold_runtime.py

These tests intentionally exercise the project-local scaffold mode without
touching `scaffold.py`'s default oracle-install behavior (regression below).
"""

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
SCAFFOLD_INIT_DIR = REPO_ROOT / "skills" / "scaffold-init"
sys.path.insert(0, str(SCRIPTS_DIR))

import scaffold_runtime  # noqa: E402


CONTRACT = json.loads(
    (REPO_ROOT / ".claude-plugin" / "install-contract.json").read_text()
)
PLUGIN_VERSION = json.loads(
    (REPO_ROOT / ".claude-plugin" / "plugin.json").read_text()
)["version"]
SCAFFOLD_CFG = CONTRACT["scaffold"]
SKILL_PREFIX = SCAFFOLD_CFG["skill_prefix"]
AGENT_PREFIX = SCAFFOLD_CFG["agent_prefix"]
RUNTIME_ROOT = SCAFFOLD_CFG["runtime_root"]
MANAGED_MARKER = SCAFFOLD_CFG["managed_marker"]


def _new_target() -> Path:
    return Path(tempfile.mkdtemp(prefix="servo-scaffold-runtime-"))


class ScaffoldSkillsTests(unittest.TestCase):
    """AC2: skills are copied with the servo- prefix and their helper files."""

    def setUp(self):
        self.target = _new_target()
        self.addCleanup(shutil.rmtree, self.target, True)
        scaffold_runtime.scaffold_runtime(self.target)

    def test_each_required_skill_dir_is_prefixed(self):
        skills_root = self.target / ".claude" / "skills"
        for skill in CONTRACT["required"]["skills"]:
            skill_dir = skills_root / f"{SKILL_PREFIX}{skill['name']}"
            self.assertTrue(
                skill_dir.is_dir(),
                f"missing prefixed skill dir {skill_dir}",
            )

    def test_required_skill_files_present(self):
        skills_root = self.target / ".claude" / "skills"
        for skill in CONTRACT["required"]["skills"]:
            for file_name in skill["files"]:
                path = skills_root / f"{SKILL_PREFIX}{skill['name']}" / file_name
                self.assertTrue(path.is_file(), f"missing skill file {path}")

    def test_unprefixed_skill_dirs_not_created(self):
        skills_root = self.target / ".claude" / "skills"
        for skill in CONTRACT["required"]["skills"]:
            bare = skills_root / skill["name"]
            self.assertFalse(bare.exists(), f"unexpected bare skill dir {bare}")


class ScaffoldAgentsTests(unittest.TestCase):
    """AC3: agents are copied with the servo- prefix."""

    def setUp(self):
        self.target = _new_target()
        self.addCleanup(shutil.rmtree, self.target, True)
        scaffold_runtime.scaffold_runtime(self.target)

    def test_prefixed_agents_present(self):
        agents_root = self.target / ".claude" / "agents"
        for agent in CONTRACT["required"]["agents"]:
            path = agents_root / f"{AGENT_PREFIX}{agent}.md"
            self.assertTrue(path.is_file(), f"missing prefixed agent {path}")

    def test_unprefixed_agents_not_created(self):
        agents_root = self.target / ".claude" / "agents"
        for agent in CONTRACT["required"]["agents"]:
            bare = agents_root / f"{agent}.md"
            self.assertFalse(bare.exists(), f"unexpected bare agent {bare}")


class ScaffoldTemplatesTests(unittest.TestCase):
    """AC4: templates are copied under the runtime_root."""

    def setUp(self):
        self.target = _new_target()
        self.addCleanup(shutil.rmtree, self.target, True)
        scaffold_runtime.scaffold_runtime(self.target)

    def test_all_required_templates_present(self):
        templates_root = self.target / RUNTIME_ROOT / "templates"
        for template in CONTRACT["required"]["templates"]:
            path = templates_root / template
            self.assertTrue(path.is_file(), f"missing template {path}")

    def test_component_fragments_present(self):
        templates_root = self.target / RUNTIME_ROOT / "templates"
        self.assertTrue(
            (templates_root / "components" / "pytest.sh.fragment").is_file()
        )


class ScaffoldManifestTests(unittest.TestCase):
    """AC5: a scaffold manifest records version, marker, and copied artifacts."""

    def setUp(self):
        self.target = _new_target()
        self.addCleanup(shutil.rmtree, self.target, True)
        scaffold_runtime.scaffold_runtime(self.target)
        self.manifest_path = self.target / RUNTIME_ROOT / "scaffold-install.json"
        self.manifest = json.loads(self.manifest_path.read_text())

    def test_manifest_written(self):
        self.assertTrue(self.manifest_path.is_file())

    def test_manifest_has_schema_version(self):
        self.assertIn("schema_version", self.manifest)
        self.assertIsInstance(self.manifest["schema_version"], int)

    def test_manifest_records_source_version(self):
        self.assertEqual(self.manifest["source_version"], PLUGIN_VERSION)

    def test_manifest_records_timestamp(self):
        self.assertRegex(
            self.manifest["timestamp"],
            r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$",
        )

    def test_manifest_records_managed_marker(self):
        self.assertEqual(self.manifest["managed_marker"], MANAGED_MARKER)

    def test_manifest_lists_copied_skills(self):
        expected = sorted(
            f"{SKILL_PREFIX}{skill['name']}"
            for skill in CONTRACT["required"]["skills"]
        )
        self.assertEqual(sorted(self.manifest["skills"]), expected)

    def test_manifest_lists_copied_agents(self):
        expected = sorted(
            f"{AGENT_PREFIX}{agent}" for agent in CONTRACT["required"]["agents"]
        )
        self.assertEqual(sorted(self.manifest["agents"]), expected)

    def test_manifest_lists_copied_templates(self):
        self.assertEqual(
            sorted(self.manifest["templates"]),
            sorted(CONTRACT["required"]["templates"]),
        )


class IdempotencyTests(unittest.TestCase):
    """AC1/idempotency: re-running updates managed files without duplication."""

    def test_rerun_does_not_error_or_duplicate(self):
        target = _new_target()
        self.addCleanup(shutil.rmtree, target, True)
        scaffold_runtime.scaffold_runtime(target)
        first = sorted(p.relative_to(target).as_posix()
                       for p in (target / ".claude").rglob("*") if p.is_file())
        # second run must not raise and must not change the managed file set
        scaffold_runtime.scaffold_runtime(target)
        second = sorted(p.relative_to(target).as_posix()
                        for p in (target / ".claude").rglob("*") if p.is_file())
        self.assertEqual(first, second)

    def test_rerun_refreshes_managed_file_content(self):
        target = _new_target()
        self.addCleanup(shutil.rmtree, target, True)
        scaffold_runtime.scaffold_runtime(target)
        helper = (
            target / ".claude" / "skills"
            / f"{SKILL_PREFIX}scaffold-init" / "scaffold.py"
        )
        helper.write_text("# tampered\n")
        scaffold_runtime.scaffold_runtime(target)
        self.assertNotEqual(helper.read_text(), "# tampered\n")
        self.assertEqual(
            helper.read_text(),
            (SCAFFOLD_INIT_DIR / "scaffold.py").read_text(),
        )


class NoHookEntriesTests(unittest.TestCase):
    """DoD: no real .claude/settings.json hook entries while hooks list is empty."""

    def test_no_settings_json_written(self):
        target = _new_target()
        self.addCleanup(shutil.rmtree, target, True)
        scaffold_runtime.scaffold_runtime(target)
        settings = target / ".claude" / "settings.json"
        self.assertFalse(
            settings.exists(),
            "scaffold must not write .claude/settings.json while hooks are empty",
        )


class SelfContainedSmokeTests(unittest.TestCase):
    """AC6: a vendored helper runs using only files under the target."""

    def _run_vendored_detect(self, target: Path, env: dict[str, str]) -> subprocess.CompletedProcess:
        vendored = (
            target / ".claude" / "skills"
            / f"{SKILL_PREFIX}scaffold-init" / "scaffold.py"
        )
        return subprocess.run(
            [sys.executable, str(vendored), "detect", str(target)],
            capture_output=True,
            text=True,
            env=env,
        )

    def test_detect_runs_with_plugin_root_unset(self):
        target = _new_target()
        self.addCleanup(shutil.rmtree, target, True)
        scaffold_runtime.scaffold_runtime(target)
        env = dict(os.environ)
        env.pop("CLAUDE_PLUGIN_ROOT", None)
        result = self._run_vendored_detect(target, env)
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertIn("components", payload)

    def test_detect_runs_with_plugin_root_invalid(self):
        target = _new_target()
        self.addCleanup(shutil.rmtree, target, True)
        scaffold_runtime.scaffold_runtime(target)
        env = dict(os.environ)
        env["CLAUDE_PLUGIN_ROOT"] = str(target / "does-not-exist-xyz")
        result = self._run_vendored_detect(target, env)
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertIn("components", payload)


class OracleInstallRegressionTests(unittest.TestCase):
    """Regression: scaffold.py <target> oracle-install is unchanged."""

    def test_oracle_install_still_writes_expected_shape(self):
        target = _new_target()
        self.addCleanup(shutil.rmtree, target, True)
        env = dict(os.environ)
        env["CLAUDE_PLUGIN_ROOT"] = str(REPO_ROOT)
        result = subprocess.run(
            [sys.executable, str(SCAFFOLD_INIT_DIR / "scaffold.py"), str(target)],
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((target / "oracle.sh").is_file())
        self.assertTrue((target / ".servo" / "install.json").is_file())
        manifest = json.loads((target / ".servo" / "install.json").read_text())
        self.assertEqual(manifest["installed_tier"], "tier-0")
        # oracle-install must not create the runtime scaffold layout
        self.assertFalse((target / ".claude" / "skills").exists())
        self.assertFalse((target / RUNTIME_ROOT / "scaffold-install.json").exists())


class CliTests(unittest.TestCase):
    """AC1: documented command copies runtime machinery into <target>/.claude/."""

    def test_main_scaffolds_target(self):
        target = _new_target()
        self.addCleanup(shutil.rmtree, target, True)
        with redirect_stdout(io.StringIO()):
            rc = scaffold_runtime.main([str(target)])
        self.assertEqual(rc, 0)
        self.assertTrue((target / RUNTIME_ROOT / "scaffold-install.json").is_file())

    def test_cli_subprocess_scaffolds_target(self):
        target = _new_target()
        self.addCleanup(shutil.rmtree, target, True)
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "scaffold_runtime.py"), str(target)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(
            (target / ".claude" / "agents" / f"{AGENT_PREFIX}runner.md").is_file()
        )


if __name__ == "__main__":
    unittest.main()
