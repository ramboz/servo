"""
Tests for slice 007-01 (`scripts/verify_install.py` plugin mode).

Run from the repo root:
    python3 scripts/test_verify_install.py
or with pytest once installed:
    python3 -m pytest scripts/test_verify_install.py
"""

import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import verify_install  # noqa: E402


def _copy_required_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def _make_valid_plugin_copy(tmpdir: Path) -> Path:
    """Build a compact copy with just the contract-required runtime files."""
    root = tmpdir / "servo-plugin"

    for rel in (
        ".claude-plugin/plugin.json",
        ".claude-plugin/marketplace.json",
        ".claude-plugin/install-contract.json",
    ):
        _copy_required_file(REPO_ROOT / rel, root / rel)

    contract = json.loads((REPO_ROOT / ".claude-plugin" / "install-contract.json").read_text())
    for skill in contract["required"]["skills"]:
        for file_name in skill["files"]:
            rel = Path("skills") / skill["name"] / file_name
            _copy_required_file(REPO_ROOT / rel, root / rel)
    for agent in contract["required"]["agents"]:
        rel = Path("agents") / f"{agent}.md"
        _copy_required_file(REPO_ROOT / rel, root / rel)
    for template in contract["required"]["templates"]:
        rel = Path("templates") / template
        _copy_required_file(REPO_ROOT / rel, root / rel)
    for hook in contract["required"]["hooks"]:
        rel = Path("hooks") / "scripts" / hook
        _copy_required_file(REPO_ROOT / rel, root / rel)
    for script in contract["required"]["scripts"]:
        rel = Path("scripts") / script
        _copy_required_file(REPO_ROOT / rel, root / rel)

    return root


def _failure_reasons(result: verify_install.VerificationResult) -> set[str]:
    return {failure.reason for failure in result.failures}


def _failure_paths(result: verify_install.VerificationResult) -> set[str]:
    return {failure.path for failure in result.failures}


class ContractFileTests(unittest.TestCase):
    """007-01 AC #1: the contract exists and names servo."""

    def test_contract_exists_and_names_servo(self):
        path = REPO_ROOT / ".claude-plugin" / "install-contract.json"
        payload = json.loads(path.read_text())
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["plugin_name"], "servo")
        self.assertEqual(payload["required"]["hooks"], [])


class PluginVerifierSuccessTests(unittest.TestCase):
    """007-01 AC #2, #3, #4: valid plugin roots pass verification."""

    def test_current_repo_passes(self):
        result = verify_install.verify_plugin(REPO_ROOT)
        self.assertTrue(result.ok, [failure.to_json() for failure in result.failures])
        self.assertEqual(result.plugin_name, "servo")
        self.assertEqual(result.version, "0.1.0")

    def test_compact_valid_copy_passes_without_hooks_or_settings(self):
        tmpdir = Path(tempfile.mkdtemp(prefix="servo-verify-install-"))
        try:
            root = _make_valid_plugin_copy(tmpdir)
            self.assertFalse((root / ".claude" / "settings.json").exists())
            self.assertFalse((root / "hooks" / "scripts").exists())
            result = verify_install.verify_plugin(root)
            self.assertTrue(result.ok, [failure.to_json() for failure in result.failures])
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_json_output_shape(self):
        tmpdir = Path(tempfile.mkdtemp(prefix="servo-verify-install-"))
        try:
            root = _make_valid_plugin_copy(tmpdir)
            out = io.StringIO()
            rc = verify_install.run_plugin(root, json_output=True, out=out)
            self.assertEqual(rc, 0)
            payload = json.loads(out.getvalue())
            self.assertEqual(payload["schema_version"], 1)
            self.assertEqual(payload["mode"], "plugin")
            self.assertEqual(payload["status"], "pass")
            self.assertEqual(payload["plugin_name"], "servo")
            self.assertEqual(payload["version"], "0.1.0")
            self.assertEqual(payload["failures"], [])
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


class ContractFailureTests(unittest.TestCase):
    """007-01 AC #5: contract failures are actionable."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="servo-verify-install-"))
        self.root = _make_valid_plugin_copy(self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_missing_contract_reports_contract_missing(self):
        (self.root / ".claude-plugin" / "install-contract.json").unlink()
        result = verify_install.verify_plugin(self.root)
        self.assertFalse(result.ok)
        self.assertIn("contract_missing", _failure_reasons(result))
        self.assertIn(".claude-plugin/install-contract.json", _failure_paths(result))

    def test_malformed_contract_reports_contract_malformed(self):
        (self.root / ".claude-plugin" / "install-contract.json").write_text("{")
        result = verify_install.verify_plugin(self.root)
        self.assertFalse(result.ok)
        self.assertIn("contract_malformed", _failure_reasons(result))
        self.assertIn(".claude-plugin/install-contract.json", _failure_paths(result))


class ManifestFailureTests(unittest.TestCase):
    """007-01 AC #2 and #5: manifest failures are actionable."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="servo-verify-install-"))
        self.root = _make_valid_plugin_copy(self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_missing_plugin_manifest_reports_manifest_missing(self):
        (self.root / ".claude-plugin" / "plugin.json").unlink()
        result = verify_install.verify_plugin(self.root)
        self.assertFalse(result.ok)
        self.assertIn("manifest_missing", _failure_reasons(result))
        self.assertIn(".claude-plugin/plugin.json", _failure_paths(result))

    def test_corrupt_marketplace_reports_manifest_malformed(self):
        (self.root / ".claude-plugin" / "marketplace.json").write_text("{")
        result = verify_install.verify_plugin(self.root)
        self.assertFalse(result.ok)
        self.assertIn("manifest_malformed", _failure_reasons(result))
        self.assertIn(".claude-plugin/marketplace.json", _failure_paths(result))

    def test_manifest_name_mismatch_reports_manifest_mismatch(self):
        plugin_manifest = self.root / ".claude-plugin" / "plugin.json"
        payload = json.loads(plugin_manifest.read_text())
        payload["name"] = "not-servo"
        plugin_manifest.write_text(json.dumps(payload))
        result = verify_install.verify_plugin(self.root)
        self.assertFalse(result.ok)
        self.assertIn("manifest_mismatch", _failure_reasons(result))
        self.assertIn(".claude-plugin/plugin.json", _failure_paths(result))


class ArtifactFailureTests(unittest.TestCase):
    """007-01 AC #3 and #5: required runtime artifacts are contract-checked."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="servo-verify-install-"))
        self.root = _make_valid_plugin_copy(self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_missing_skill_helper_reports_artifact_missing(self):
        (self.root / "skills" / "scaffold-init" / "scaffold.py").unlink()
        result = verify_install.verify_plugin(self.root)
        self.assertFalse(result.ok)
        self.assertIn("artifact_missing", _failure_reasons(result))
        self.assertIn("skills/scaffold-init/scaffold.py", _failure_paths(result))

    def test_missing_agent_reports_artifact_missing(self):
        (self.root / "agents" / "judge.md").unlink()
        result = verify_install.verify_plugin(self.root)
        self.assertFalse(result.ok)
        self.assertIn("artifact_missing", _failure_reasons(result))
        self.assertIn("agents/judge.md", _failure_paths(result))

    def test_missing_template_reports_artifact_missing(self):
        (self.root / "templates" / "components" / "pytest.sh.fragment").unlink()
        result = verify_install.verify_plugin(self.root)
        self.assertFalse(result.ok)
        self.assertIn("artifact_missing", _failure_reasons(result))
        self.assertIn("templates/components/pytest.sh.fragment", _failure_paths(result))


class CliTests(unittest.TestCase):
    """007-01 AC #6: CLI JSON emits the stable output shape."""

    def test_cli_json_subprocess_success(self):
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS_DIR / "verify_install.py"),
                "plugin",
                "--json",
                str(REPO_ROOT),
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "pass")
        self.assertEqual(payload["plugin_name"], "servo")

    def test_main_plugin_json_failure_exit(self):
        tmpdir = Path(tempfile.mkdtemp(prefix="servo-verify-install-"))
        try:
            root = _make_valid_plugin_copy(tmpdir)
            (root / "agents" / "runner.md").unlink()
            out = io.StringIO()
            rc = verify_install.run_plugin(root, json_output=True, out=out)
            self.assertEqual(rc, 1)
            payload = json.loads(out.getvalue())
            self.assertEqual(payload["status"], "fail")
            self.assertEqual(payload["failures"][0]["reason"], "artifact_missing")
            self.assertEqual(payload["failures"][0]["path"], "agents/runner.md")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
