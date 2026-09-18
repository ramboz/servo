from __future__ import annotations

import io
import json
import shutil
import sys
import tempfile
import unittest
import zipfile
from contextlib import redirect_stderr
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS.parent
HOSTS_ROOT = REPO_ROOT / "hosts"
sys.path.insert(0, str(SCRIPTS))

import build_release_zip  # noqa: E402

VERSION = json.loads((REPO_ROOT / ".claude-plugin/plugin.json").read_text())["version"]


class ReleaseZipTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="servo-release-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def build(self, host: str, name: str = "out.zip") -> tuple[Path, str]:
        target = self.tmp / name
        out = io.StringIO()
        rc = build_release_zip.build(host, HOSTS_ROOT, VERSION, target, out=out)
        self.assertEqual(rc, 0, out.getvalue())
        return target, out.getvalue()

    def test_claude_zip_is_flat_runtime_package(self):
        archive, _ = self.build("claude")
        with zipfile.ZipFile(archive) as zf:
            names = set(zf.namelist())
        self.assertIn(".claude-plugin/plugin.json", names)
        self.assertIn("skills/spec-oracle/SKILL.md", names)
        self.assertNotIn(".claude-plugin/marketplace.json", names)
        self.assertFalse(any(name.startswith(("hosts/", ".codex-plugin/")) for name in names))

    def test_codex_zip_is_marketplace_bundle(self):
        archive, output = self.build("codex")
        with zipfile.ZipFile(archive) as zf:
            names = set(zf.namelist())
        self.assertIn(".agents/plugins/marketplace.json", names)
        self.assertIn("plugins/servo/.codex-plugin/plugin.json", names)
        self.assertFalse(any(name.startswith("hosts/") for name in names))
        self.assertIn("extract-then-add", output)

    def test_copilot_zip_is_flat_plugin_package(self):
        # AC1: the copilot zip archives hosts/copilot/ with the legacy manifest
        # at the zip root and the .github/ config tree beside it — no wrong-host
        # content (no hosts/ prefix, no Claude/Codex descriptors).
        archive, output = self.build("copilot")
        with zipfile.ZipFile(archive) as zf:
            names = set(zf.namelist())
        self.assertIn(".plugin/plugin.json", names)
        self.assertIn(".github/skills/spec-oracle/SKILL.md", names)
        self.assertIn(".github/agents/runner.agent.md", names)
        self.assertFalse(any(name.startswith("hosts/") for name in names))
        self.assertFalse(
            any(
                name.startswith(
                    (".claude-plugin/", ".codex-plugin/", ".agents/", "plugins/")
                )
                for name in names
            )
        )
        self.assertIn("copilot", output.lower())

    def test_default_names_are_host_specific(self):
        self.assertEqual(
            build_release_zip.default_output_path(REPO_ROOT, "claude", VERSION),
            REPO_ROOT / f"dist/servo-claude-v{VERSION}.zip",
        )
        self.assertEqual(
            build_release_zip.default_output_path(REPO_ROOT, "codex", VERSION),
            REPO_ROOT / f"dist/servo-codex-v{VERSION}.zip",
        )
        self.assertEqual(
            build_release_zip.default_output_path(REPO_ROOT, "copilot", VERSION),
            REPO_ROOT / f"dist/servo-copilot-v{VERSION}.zip",
        )

    def test_builds_are_deterministic_per_host(self):
        for host in ("claude", "codex", "copilot"):
            first, _ = self.build(host, f"{host}-1.zip")
            second, _ = self.build(host, f"{host}-2.zip")
            self.assertEqual(first.read_bytes(), second.read_bytes())

    def test_version_mismatch_refuses_archive(self):
        for host in ("claude", "codex", "copilot"):
            target = self.tmp / f"{host}.zip"
            out = io.StringIO()
            rc = build_release_zip.build(host, HOSTS_ROOT, "9.9.9", target, out=out)
            self.assertEqual(rc, 2)
            self.assertIn("version mismatch", out.getvalue())
            self.assertFalse(target.exists())

    def test_host_specific_smoke_validation(self):
        for host in ("claude", "codex", "copilot"):
            archive, _ = self.build(host, f"{host}.zip")
            out = io.StringIO()
            self.assertEqual(build_release_zip.smoke_test(host, archive, out), 0, out.getvalue())
            self.assertIn(host, out.getvalue().lower())

    def test_copilot_smoke_rejects_tampered_zip(self):
        # AC2 teeth (mutation-verify): _smoke_copilot extracts + runs
        # validate_copilot_package. Green on the honest artifact; red when the
        # manifest gains a forbidden `hooks` field (servo's copilot package is
        # hook-free), proving the smoke actually inspects the extracted tree.
        source, _ = self.build("copilot", "copilot-ok.zip")
        out_ok = io.StringIO()
        self.assertEqual(
            build_release_zip.smoke_test("copilot", source, out_ok), 0, out_ok.getvalue()
        )
        tampered = self.tmp / "copilot-tampered.zip"
        with zipfile.ZipFile(source) as src, zipfile.ZipFile(tampered, "w") as dst:
            for info in src.infolist():
                data = src.read(info.filename)
                if info.filename == ".plugin/plugin.json":
                    manifest = json.loads(data)
                    manifest["hooks"] = ".github/hooks"
                    data = (json.dumps(manifest, indent=2) + "\n").encode("utf-8")
                dst.writestr(info, data)
        out = io.StringIO()
        self.assertEqual(build_release_zip.smoke_test("copilot", tampered, out), 1)
        self.assertIn("hooks", out.getvalue().lower())

    def test_smoke_rejects_archive_missing_runtime_inventory(self):
        for host in ("claude", "codex"):
            source, _ = self.build(host, f"{host}-complete.zip")
            broken = self.tmp / f"{host}-missing-skills.zip"
            with zipfile.ZipFile(source) as src, zipfile.ZipFile(broken, "w") as dst:
                for info in src.infolist():
                    if "/skills/" in info.filename or info.filename.startswith("skills/"):
                        continue
                    dst.writestr(info, src.read(info.filename))
            out = io.StringIO()
            self.assertEqual(build_release_zip.smoke_test(host, broken, out), 1)
            self.assertIn("missing", out.getvalue())

    def test_archive_path_safety_rejects_hostile_names(self):
        for raw in (
            "/absolute",
            "../escape",
            "C:/windows",
            "C:relative",
            "dir\\escape",
        ):
            with self.subTest(raw=raw):
                archive = self.tmp / "hostile.zip"
                with zipfile.ZipFile(archive, "w") as zf:
                    zf.writestr(raw, b"unsafe")
                with zipfile.ZipFile(archive) as zf:
                    names, error = build_release_zip._safe_names(zf)
                self.assertEqual(names, set())
                self.assertIn("unsafe archive entry", error or "")

    def test_host_is_required_by_cli(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            build_release_zip.main(["build_release_zip.py", "--version", VERSION])


if __name__ == "__main__":
    unittest.main()
