"""
Tests for slice 007-02 (`scripts/build_release_zip.py`).

Run from the repo root:
    python3 scripts/test_build_release_zip.py
or with unittest discovery:
    python3 -m unittest discover -s scripts -p 'test_*.py'
"""

import io
import json
import shutil
import sys
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import build_release_zip  # noqa: E402
import verify_install  # noqa: E402

PLUGIN_VERSION = json.loads((REPO_ROOT / ".claude-plugin" / "plugin.json").read_text())["version"]


def _build_once(*, name: str | None = None, smoke: bool = True) -> Path:
    tmpdir = Path(tempfile.mkdtemp(prefix="servo-release-zip-"))
    out = tmpdir / (name or f"servo-v{PLUGIN_VERSION}.zip")
    sink = io.StringIO()
    rc = build_release_zip.build(
        source_root=REPO_ROOT,
        output_path=out,
        smoke=smoke,
        out=sink,
    )
    if rc != 0:
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise RuntimeError(f"build failed with rc={rc}: {sink.getvalue()}")
    return out


def _zip_names(zip_path: Path) -> set[str]:
    with zipfile.ZipFile(zip_path) as zf:
        return set(zf.namelist())


class BuildOutputTests(unittest.TestCase):
    """007-02 AC #1: the builder writes a flat, non-empty zip."""

    def test_build_writes_nonempty_zip(self):
        zip_path = _build_once()
        self.addCleanup(shutil.rmtree, zip_path.parent, True)
        self.assertTrue(zip_path.is_file())
        self.assertGreater(zip_path.stat().st_size, 0)

    def test_zip_has_no_wrapping_directory(self):
        zip_path = _build_once()
        self.addCleanup(shutil.rmtree, zip_path.parent, True)
        names = _zip_names(zip_path)
        self.assertIn(".claude-plugin/plugin.json", names)
        self.assertFalse(any(name.startswith("servo/") for name in names))


class InventoryTests(unittest.TestCase):
    """007-02 AC #1: required runtime inventory is present."""

    def setUp(self):
        self.zip_path = _build_once()
        self.addCleanup(shutil.rmtree, self.zip_path.parent, True)
        self.names = _zip_names(self.zip_path)

    def test_plugin_metadata_present(self):
        self.assertIn(".claude-plugin/plugin.json", self.names)
        self.assertIn(".claude-plugin/marketplace.json", self.names)
        self.assertIn(".claude-plugin/install-contract.json", self.names)

    def test_agents_present(self):
        self.assertIn("agents/runner.md", self.names)
        self.assertIn("agents/judge.md", self.names)

    def test_skill_runtime_files_present(self):
        self.assertIn("skills/scaffold-init/SKILL.md", self.names)
        self.assertIn("skills/scaffold-init/scaffold.py", self.names)
        self.assertIn("skills/quality-gate/SKILL.md", self.names)
        self.assertIn("skills/quality-gate/gate.py", self.names)
        self.assertIn("skills/agent-loop/SKILL.md", self.names)
        self.assertIn("skills/agent-loop/loop.py", self.names)

    def test_templates_and_top_level_docs_present(self):
        self.assertIn("templates/oracle.sh.template", self.names)
        self.assertIn("templates/components/pytest.sh.fragment", self.names)
        self.assertIn("README.md", self.names)
        self.assertIn("LICENSE", self.names)


class ExclusionTests(unittest.TestCase):
    """007-02 AC #3: forbidden dev/test artifacts are excluded."""

    def setUp(self):
        self.zip_path = _build_once()
        self.addCleanup(shutil.rmtree, self.zip_path.parent, True)
        self.names = _zip_names(self.zip_path)

    def test_test_files_excluded(self):
        offenders = [name for name in self.names if Path(name).name.startswith("test_")]
        self.assertEqual(offenders, [])

    def test_caches_and_pyc_excluded(self):
        offenders = [
            name for name in self.names
            if "__pycache__" in Path(name).parts
            or ".pytest_cache" in Path(name).parts
            or name.endswith(".pyc")
            or Path(name).name == ".DS_Store"
        ]
        self.assertEqual(offenders, [])

    def test_development_roots_excluded(self):
        forbidden_prefixes = (".git/", "docs/", "dist/", "scripts/")
        offenders = [
            name for name in self.names
            if name.startswith(forbidden_prefixes) or name == "mcp-server.log"
        ]
        self.assertEqual(offenders, [])

    def test_gitkeep_and_crew_postmortem_excluded(self):
        self.assertNotIn("hooks/.gitkeep", self.names)
        self.assertNotIn("skills/.gitkeep", self.names)
        self.assertNotIn("templates/crew-postmortem.md", self.names)


class DeterminismTests(unittest.TestCase):
    """007-02 AC #2: repeated builds are byte-identical."""

    def test_two_builds_produce_identical_bytes(self):
        zip_a = _build_once(smoke=False)
        zip_b = _build_once(smoke=False)
        self.addCleanup(shutil.rmtree, zip_a.parent, True)
        self.addCleanup(shutil.rmtree, zip_b.parent, True)
        self.assertEqual(zip_a.read_bytes(), zip_b.read_bytes())


class VersionSourceTests(unittest.TestCase):
    """007-02 AC #4: manifest version is authoritative."""

    def test_requested_version_mismatch_fails(self):
        tmpdir = Path(tempfile.mkdtemp(prefix="servo-release-zip-"))
        self.addCleanup(shutil.rmtree, tmpdir, True)
        out = tmpdir / "servo-v9.9.9.zip"
        sink = io.StringIO()
        rc = build_release_zip.build(
            source_root=REPO_ROOT,
            output_path=out,
            version="9.9.9",
            smoke=False,
            out=sink,
        )
        self.assertEqual(rc, 2)
        self.assertIn("version mismatch", sink.getvalue())
        self.assertFalse(out.exists())

    def test_output_name_version_mismatch_fails(self):
        tmpdir = Path(tempfile.mkdtemp(prefix="servo-release-zip-"))
        self.addCleanup(shutil.rmtree, tmpdir, True)
        out = tmpdir / "servo-v9.9.9.zip"
        sink = io.StringIO()
        rc = build_release_zip.build(
            source_root=REPO_ROOT,
            output_path=out,
            smoke=False,
            out=sink,
        )
        self.assertEqual(rc, 2)
        self.assertIn("output filename", sink.getvalue())
        self.assertFalse(out.exists())


class UnsafeContractTests(unittest.TestCase):
    """007-02 AC #1 / #6: the builder refuses unsafe contract include paths."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="servo-release-zip-contract-"))
        self.source = self.tmpdir / "source"
        shutil.copytree(REPO_ROOT / ".claude-plugin", self.source / ".claude-plugin")
        (self.tmpdir / "outside.txt").write_text("must not ship\n")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_include(self, include: str) -> None:
        contract_path = self.source / ".claude-plugin" / "install-contract.json"
        contract = json.loads(contract_path.read_text())
        contract["release_zip"]["include"] = [include]
        contract["release_zip"]["exclude_globs"] = []
        contract_path.write_text(json.dumps(contract))

    def test_parent_traversal_include_refused_before_writing_zip(self):
        self._write_include("../outside.txt")
        out = self.tmpdir / f"servo-v{PLUGIN_VERSION}.zip"
        sink = io.StringIO()
        rc = build_release_zip.build(
            source_root=self.source,
            output_path=out,
            smoke=False,
            out=sink,
        )
        self.assertEqual(rc, 1)
        self.assertIn("unsafe", sink.getvalue())
        self.assertFalse(out.exists())

    def test_windows_drive_include_refused_before_writing_zip(self):
        self._write_include("C:/outside.txt")
        out = self.tmpdir / f"servo-v{PLUGIN_VERSION}.zip"
        sink = io.StringIO()
        rc = build_release_zip.build(
            source_root=self.source,
            output_path=out,
            smoke=False,
            out=sink,
        )
        self.assertEqual(rc, 1)
        self.assertIn("unsafe", sink.getvalue())
        self.assertFalse(out.exists())


class SmokeTests(unittest.TestCase):
    """007-02 AC #5: build and smoke-test use zip verification."""

    def test_build_smoke_test_passes_by_default(self):
        zip_path = _build_once(smoke=True)
        self.addCleanup(shutil.rmtree, zip_path.parent, True)
        result = verify_install.verify_zip(zip_path)
        self.assertTrue(result.ok, [failure.to_json() for failure in result.failures])

    def test_smoke_test_existing_zip(self):
        zip_path = _build_once(smoke=False)
        self.addCleanup(shutil.rmtree, zip_path.parent, True)
        sink = io.StringIO()
        rc = build_release_zip.smoke_test(zip_path, out=sink)
        self.assertEqual(rc, 0, sink.getvalue())

    def test_verify_zip_json_output(self):
        zip_path = _build_once(smoke=False)
        self.addCleanup(shutil.rmtree, zip_path.parent, True)
        sink = io.StringIO()
        rc = verify_install.run_zip(zip_path, json_output=True, out=sink)
        self.assertEqual(rc, 0, sink.getvalue())
        payload = json.loads(sink.getvalue())
        self.assertEqual(payload["mode"], "zip")
        self.assertEqual(payload["status"], "pass")
        self.assertEqual(payload["plugin_name"], "servo")


class UnsafeZipTests(unittest.TestCase):
    """007-02 AC #6: zip verifier rejects unsafe or forbidden entries."""

    def test_zip_slip_entry_rejected(self):
        tmpdir = Path(tempfile.mkdtemp(prefix="servo-release-zip-"))
        self.addCleanup(shutil.rmtree, tmpdir, True)
        zip_path = tmpdir / "bad.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("../evil.txt", "nope")
        result = verify_install.verify_zip(zip_path)
        self.assertFalse(result.ok)
        self.assertEqual(result.failures[0].reason, "zip_invalid")
        self.assertIn("../evil.txt", result.failures[0].path)

    def test_windows_drive_absolute_entry_rejected(self):
        tmpdir = Path(tempfile.mkdtemp(prefix="servo-release-zip-"))
        self.addCleanup(shutil.rmtree, tmpdir, True)
        zip_path = tmpdir / "bad-windows.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("C:/evil.txt", "nope")
        result = verify_install.verify_zip(zip_path)
        self.assertFalse(result.ok)
        self.assertEqual(result.failures[0].reason, "zip_invalid")
        self.assertIn("C:/evil.txt", result.failures[0].path)

    def test_forbidden_entry_rejected(self):
        zip_path = _build_once(smoke=False)
        self.addCleanup(shutil.rmtree, zip_path.parent, True)
        with zipfile.ZipFile(zip_path, "a") as zf:
            zf.writestr("docs/should-not-ship.md", "dev doc")
        result = verify_install.verify_zip(zip_path)
        self.assertFalse(result.ok)
        reasons = {failure.reason for failure in result.failures}
        self.assertIn("artifact_forbidden", reasons)
        paths = {failure.path for failure in result.failures}
        self.assertTrue(any("docs/should-not-ship.md" in path for path in paths))


class CliTests(unittest.TestCase):
    """CLI coverage for the release builder."""

    def test_main_builds_zip_with_output(self):
        tmpdir = Path(tempfile.mkdtemp(prefix="servo-release-zip-"))
        self.addCleanup(shutil.rmtree, tmpdir, True)
        out = tmpdir / f"servo-v{PLUGIN_VERSION}.zip"
        with redirect_stdout(io.StringIO()):
            rc = build_release_zip.main(["--output", str(out), "--no-smoke"])
        self.assertEqual(rc, 0)
        self.assertTrue(out.is_file())

    def test_main_smoke_test_existing_zip(self):
        zip_path = _build_once(smoke=False)
        self.addCleanup(shutil.rmtree, zip_path.parent, True)
        with redirect_stdout(io.StringIO()):
            rc = build_release_zip.main(["--smoke-test", str(zip_path)])
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
