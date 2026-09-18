"""Guards for dual-host manifest and release-please coherence."""

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import validate_manifests  # noqa: E402


class ManifestValidationTests(unittest.TestCase):
    def test_validator_accepts_committed_tree(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "validate_manifests.py")],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("four plugin manifests agree", proc.stdout)

    def test_release_please_tracks_every_manifest(self) -> None:
        config = json.loads((ROOT / ".github" / "release-please-config.json").read_text())
        paths = {
            item["path"]
            for item in config["packages"]["."]["extra-files"]
            if item.get("type") == "json" and item.get("jsonpath") == "$.version"
        }
        self.assertEqual(
            paths,
            {
                ".claude-plugin/plugin.json",
                ".codex-plugin/plugin.json",
                "hosts/claude/.claude-plugin/plugin.json",
                "hosts/codex/plugins/servo/.codex-plugin/plugin.json",
            },
        )

    def test_root_codex_marketplace_points_to_committed_plugin(self) -> None:
        marketplace = json.loads(
            (ROOT / ".agents" / "plugins" / "marketplace.json").read_text()
        )
        source = marketplace["plugins"][0]["source"]
        self.assertEqual(
            source,
            {"source": "local", "path": "./hosts/codex/plugins/servo"},
        )

    def test_copilot_marketplace_descriptor_uses_relative_string_source(self) -> None:
        # AC5 (bug 035): Copilot's own marketplace descriptor lives at its
        # higher-precedence path and carries a relative-string source, not the
        # git-subdir object dialect Copilot rejects.
        marketplace = json.loads(
            (ROOT / ".github" / "plugin" / "marketplace.json").read_text()
        )
        entry = next(e for e in marketplace["plugins"] if e.get("name") == "servo")
        self.assertEqual(entry["source"], "./hosts/copilot")
        self.assertEqual(validate_manifests._copilot_marketplace_errors(marketplace), [])

    def test_copilot_marketplace_rejects_object_source(self) -> None:
        # AC5 (teeth): an object source (Claude's dialect) is flagged for Copilot.
        bad = {
            "name": "servo",
            "owner": {"name": "ramboz"},
            "plugins": [
                {"name": "servo", "source": {"source": "git-subdir", "path": "hosts/copilot"}}
            ],
        }
        self.assertTrue(validate_manifests._copilot_marketplace_errors(bad))


if __name__ == "__main__":
    unittest.main()
