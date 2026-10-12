"""033-01: generated runtime fixtures, not evidence of a native CLI install."""

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))

import build_host_packages  # noqa: E402


class CopilotInstalledRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build_tmp = tempfile.TemporaryDirectory(prefix="servo generated hosts ")
        cls.hosts = Path(cls.build_tmp.name).resolve() / "hosts"
        out = io.StringIO()
        if build_host_packages.build_all(REPO_ROOT, cls.hosts, out) != 0:
            cls.build_tmp.cleanup()
            raise AssertionError(out.getvalue())

    @classmethod
    def tearDownClass(cls):
        cls.build_tmp.cleanup()

    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="servo installed runtime ")
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name).resolve()
        self.home = self.tmp / "custom copilot home"
        self.target = self.tmp / "clean consumer"
        self.target.mkdir()
        self.tools = self.tmp / "tools"
        self.tools.mkdir()
        for name in ("awk", "bash", "dirname", "sleep"):
            executable = shutil.which(name)
            self.assertIsNotNone(executable, f"missing fixture tool: {name}")
            (self.tools / name).symlink_to(executable)
        (self.tools / "python3").symlink_to(sys.executable)
        self.env = {
            "HOME": str(self.tmp / "user home"),
            "COPILOT_HOME": str(self.home),
            "XDG_STATE_HOME": str(self.tmp / "state"),
            "PATH": str(self.tools),
        }
        self.package = self._install("team marketplace", "renamed package", "7.12.3")
        self.runtime = self.package / ".github"

    def _install(self, marketplace, directory, version, *, name="servo"):
        package = self.home / "installed-plugins" / marketplace / directory
        shutil.copytree(self.hosts / "copilot", package)
        manifest = package / ".plugin/plugin.json"
        data = json.loads(manifest.read_text())
        data.update(name=name, version=version)
        manifest.write_text(json.dumps(data))
        return package

    def _run(self, script, *args, env=None, cwd=None):
        return subprocess.run(
            [sys.executable, str(script), *map(str, args)],
            cwd=cwd or self.target,
            env=env or self.env,
            capture_output=True,
            text=True,
            timeout=15,
        )

    def _locator(self, *, script=None, cwd=None):
        return self._run(script or SCRIPTS / "servo_root.py", cwd=cwd)

    def _documented_locator(self, *, cwd=None):
        # Execute the exact builder-injected shell command. Python must be
        # available, but neither Claude nor Jig is on this isolated PATH.
        command = (
            build_host_packages._SERVO_ROOT_LOCATOR
            + '; rc=$?; [ "$rc" -eq 0 ] && printf "%s\\n" "$SERVO_ROOT"; exit "$rc"'
        )
        return subprocess.run(
            ["/bin/sh", "-c", command],
            cwd=cwd or self.target,
            env=self.env,
            capture_output=True,
            text=True,
            timeout=15,
        )

    def _scaffold(self, *, env=None, script=None):
        return self._run(
            script or self.runtime / "skills/scaffold-init/scaffold.py",
            self.target,
            env=env,
        )

    def _scaffold_ok(self):
        result = self._scaffold()
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def _marker(self):
        path = Path(self.env["XDG_STATE_HOME"]) / "servo/available.json"
        self.assertTrue(path.is_file(), "native availability marker was not written")
        return json.loads(path.read_text())

    def _gate(self, *args):
        return self._run(
            self.runtime / "skills/quality-gate/gate.py",
            self.target, "--json", *args,
        )

    def _pytest_tool(self, body):
        tool = self.tools / "pytest"
        tool.write_text("#!/bin/sh\n" + body + "\n")
        tool.chmod(0o755)

    # AC1: installed-store discovery is manifest-based, quoted and ordered.
    def test_custom_home_spaces_and_marketplace_names(self):
        result = self._locator()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), str(self.runtime))
        documented = self._documented_locator()
        self.assertEqual(documented.returncode, 0, documented.stderr)
        self.assertEqual(documented.stdout.strip(), str(self.runtime))

    def test_multiple_installs_choose_numeric_version_then_mtime(self):
        shutil.rmtree(self.package)
        low = self._install("zzz low", "servo", "0.9.0") / ".github"
        old = self._install("aaa high", "first", "0.10.0") / ".github"
        newest = self._install("bbb high", "second", "0.10.0") / ".github"
        os.utime(low, (300, 300))
        os.utime(old, (100, 100))
        os.utime(newest, (200, 200))
        self._install("foreign", "servo", "99.0.0", name="not-servo")
        broken = self._install("broken", "servo", "100.0.0")
        (broken / ".github/skills/agent-loop/loop.py").unlink()
        malformed = self._install("malformed", "servo", "101.0.0")
        (malformed / ".plugin/plugin.json").write_text("[]")
        result = self._locator()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), str(newest))
        # Invoking an older installed locator must still choose the newest,
        # rather than accidentally pinning the first script in the shell glob.
        result = self._locator(script=old / "scripts/servo_root.py")
        self.assertEqual(result.stdout.strip(), str(newest))
        documented = self._documented_locator()
        self.assertEqual(documented.returncode, 0, documented.stderr)
        self.assertEqual(documented.stdout.strip(), str(newest))

    def test_project_owned_runtime_wins_from_nested_directory(self):
        owned = self.target / ".github"
        shutil.copytree(self.runtime, owned)
        nested = self.target / "src/nested directory"
        nested.mkdir(parents=True)
        result = self._locator(cwd=nested)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), str(owned))
        # No installed script is needed to bootstrap a project-owned locator.
        shutil.rmtree(self.home)
        result = self._documented_locator(cwd=nested)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), str(owned))

    def test_absent_runtime_has_explicit_diagnostic(self):
        shutil.rmtree(self.home)
        for result in (self._locator(), self._documented_locator()):
            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, "")
            self.assertIn("servo_root: no servo runtime found", result.stderr)

    def test_live_package_locator_at_own_script_path(self):
        # This is a generated fixture, not proof of marketplace copy semantics.
        shutil.rmtree(self.home)
        runtime = self.hosts / "copilot/.github"
        result = self._locator(script=runtime / "scripts/servo_root.py")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), str(runtime))

    # AC2: the executing native runtime owns templates and marker metadata.
    def test_native_templates_ignore_unrelated_host_roots(self):
        unrelated = self.tmp / "unrelated root"
        unrelated.mkdir()
        env = dict(
            self.env,
            CLAUDE_PLUGIN_ROOT=str(unrelated),
            SERVO_ROOT=str(unrelated),
        )
        result = self._scaffold(env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("oracle: composite=", (self.target / "oracle.sh").read_text())
        marker = self._marker()
        self.assertEqual(marker["source_path"], str(self.runtime))
        self.assertEqual(marker["source_version"], "7.12.3")

    def test_native_marker_uses_parent_manifest_not_claude_version(self):
        env = dict(
            self.env,
            CLAUDE_PLUGIN_ROOT=str(self.hosts / "claude"),
            SERVO_ROOT=str(self.hosts / "codex/plugins/servo"),
        )
        result = self._scaffold(env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        marker = self._marker()
        self.assertEqual(marker["schema_version"], 1)
        self.assertEqual(marker["plugin_name"], "servo")
        self.assertEqual(marker["source_kind"], "scaffold-init")
        self.assertEqual(marker["source_path"], str(self.runtime))
        self.assertEqual(marker["source_version"], "7.12.3")
        self.assertRegex(marker["updated_at"], r"^\d{4}-\d{2}-\d{2}T.*Z$")
        self.assertFalse((self.runtime / ".claude-plugin").exists())
        self.assertFalse((self.package / ".claude-plugin").exists())

    def test_clean_native_scaffold_emits_oracle_manifest_notes_and_marker(self):
        self._scaffold_ok()
        self.assertTrue(os.access(self.target / "oracle.sh", os.X_OK))
        manifest = json.loads((self.target / ".servo/install.json").read_text())
        self.assertEqual(manifest["installed_tier"], "tier-0")
        self.assertEqual(manifest["components"], [])
        notes = (self.target / ".servo/refinement-todo.md").read_text()
        self.assertIn("## Threshold", notes)
        self.assertIn("Resolution trigger", notes)
        self.assertEqual(self._marker()["source_version"], "7.12.3")
        self.assertFalse((self.target / ".claude").exists())
        self.assertFalse((self.target / "CLAUDE.md").exists())

    def test_native_manifest_identity_and_version_are_required(self):
        path = self.package / ".plugin/plugin.json"
        for data in ({"name": "other", "version": "99"}, {"name": "servo"}, []):
            with self.subTest(manifest=data):
                path.write_text(json.dumps(data))
                result = self._scaffold()
                self.assertEqual(result.returncode, 0, result.stderr)
                (self.target / "oracle.sh").unlink()
                self.assertIn("skipping availability marker", result.stderr)
                marker = Path(self.env["XDG_STATE_HOME"]) / "servo/available.json"
                self.assertFalse(marker.exists())

    def test_project_owned_scaffold_does_not_publish_unrelated_global_marker(self):
        owned = self.target / ".github"
        shutil.copytree(self.runtime, owned)
        env = dict(self.env, CLAUDE_PLUGIN_ROOT=str(self.hosts / "claude"))
        result = self._scaffold(
            script=owned / "skills/scaffold-init/scaffold.py", env=env,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        marker = Path(self.env["XDG_STATE_HOME"]) / "servo/available.json"
        self.assertFalse(marker.exists())

    def test_claude_and_codex_scaffold_and_marker_compatibility(self):
        for host, package, writes_marker in (
            ("claude", self.hosts / "claude", True),
            ("codex", self.hosts / "codex/plugins/servo", False),
        ):
            with self.subTest(host=host):
                env = dict(self.env, XDG_STATE_HOME=str(self.tmp / host))
                result = self._scaffold(
                    script=package / "skills/scaffold-init/scaffold.py", env=env,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                (self.target / "oracle.sh").unlink()
                marker = Path(env["XDG_STATE_HOME"]) / "servo/available.json"
                self.assertEqual(marker.exists(), writes_marker)
                if writes_marker:
                    payload = json.loads(marker.read_text())
                    self.assertEqual(payload["source_path"], str(package))
                    version = json.loads((package / ".claude-plugin/plugin.json").read_text())
                    self.assertEqual(payload["source_version"], version["version"])
                self.assertTrue((self.target / ".servo/refinement-todo.md").is_file())

    # AC3: one scaffolded project oracle is the gate's unchanged authority.
    def _seed_pytest_project(self):
        (self.target / "pytest.ini").write_text("[pytest]\n")
        self._scaffold_ok()
        manifest = json.loads((self.target / ".servo/install.json").read_text())
        self.assertEqual(manifest["components"], ["pytest"])

    def test_packaged_gate_pass_and_below_threshold_use_same_oracle(self):
        self._seed_pytest_project()
        oracle = (self.target / "oracle.sh").read_bytes()
        for tool_exit, status, score in (
            (0, "pass", 1.0), (1, "below_threshold", 0.0),
        ):
            with self.subTest(status=status):
                self._pytest_tool(f"exit {tool_exit}")
                result = self._gate()
                self.assertEqual(result.returncode, tool_exit, result.stderr)
                payload = json.loads(result.stdout)
                self.assertEqual(payload["schema_version"], 1)
                self.assertEqual(payload["exit_code"], tool_exit)
                self.assertEqual(payload["status"], status)
                self.assertEqual(payload["composite"], score)
                self.assertEqual(payload["threshold"], 0.5)
                self.assertEqual((self.target / "oracle.sh").read_bytes(), oracle)

    def test_packaged_gate_environment_error(self):
        self._seed_pytest_project()
        result = self._gate()
        self.assertEqual(result.returncode, 2, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["exit_code"], 2)
        self.assertEqual(payload["status"], "env_error")
        self.assertEqual(payload["missing"], ["pytest"])

    def test_packaged_gate_timeout(self):
        self._seed_pytest_project()
        self._pytest_tool("exec sleep 10")
        result = self._gate("--timeout", "0.1")
        self.assertEqual(result.returncode, 2, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["exit_code"], 2)
        self.assertEqual(payload["status"], "env_error")
        self.assertEqual(payload["reason"], "timeout")
        self.assertEqual(payload["timeout_seconds"], 0.1)

    # AC4's static arm only; live CLI/install/zip evidence belongs to the parent.
    def test_generated_package_inventory_and_manifest_validity(self):
        self.assertEqual(build_host_packages.validate_copilot_package(self.package), [])
        public = {p.parent.name for p in (REPO_ROOT / "skills").glob("*/SKILL.md")}
        self.assertEqual(
            {p.parent.name for p in (self.runtime / "skills").glob("*/SKILL.md")}, public,
        )
        self.assertTrue((self.runtime / "skills/_common").is_dir())
        self.assertTrue((self.runtime / "templates/oracle.sh.template").is_file())
        self.assertEqual(
            {p.name for p in (self.runtime / "agents").glob("*.agent.md")},
            {f"{p.stem}.agent.md" for p in (REPO_ROOT / "agents").glob("*.md")},
        )

    # AC5: no mandatory Jig, Claude or pre-rendered consumer tree.
    def test_packaged_helpers_work_without_claude_or_jig(self):
        audit = self._run(
            self.runtime / "skills/scaffold-init/scaffold.py", "detect", self.target,
        )
        self.assertEqual(audit.returncode, 0, audit.stderr)
        self.assertEqual(json.loads(audit.stdout)["detector"], "built-in")
        self.assertFalse((self.runtime / "jig").exists())
        self.assertFalse((self.runtime / "hooks").exists())
        for tool in ("claude", "jig"):
            self.assertIsNone(shutil.which(tool, path=self.env["PATH"]))
        self.assertEqual(
            (self.runtime / "templates/oracle.sh.template").read_bytes(),
            (REPO_ROOT / "templates/oracle.sh.template").read_bytes(),
        )


if __name__ == "__main__":
    unittest.main()
