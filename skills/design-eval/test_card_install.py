"""Installation must consume reviewed bytes without granting approval itself."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import card_install
import design_eval


class InstallationTests(unittest.TestCase):
    def test_preparation_selects_the_resolved_native_cli_not_its_launcher_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            (target / "oracle.sh").write_text("unit-only")
            native = target / "native-claude"
            native.write_bytes(b"\xcf\xfa\xed\xfe")
            launcher = target / "claude"
            launcher.symlink_to(native)
            with (
                patch.object(card_install, "producer_at"),
                patch.object(card_install, "packages_at"),
                patch.object(
                    card_install, "_runtime", side_effect=ValueError("unit-stop-runtime")
                ) as runtime,
            ):
                with self.assertRaisesRegex(ValueError, "unit-stop-runtime"):
                    card_install.prepare(
                        target, target, target, target, sys.executable, target, launcher
                    )
            self.assertEqual(runtime.call_args.args[2], native.resolve())

    def test_unimported_native_extension_closes_its_non_os_linkage(self):
        with tempfile.TemporaryDirectory() as directory:
            extension = Path(directory).resolve() / "_sqlite3.so"
            extension.write_bytes(b"unit-extension")
            library = Path("/opt/homebrew/opt/sqlite/lib/libsqlite3.dylib")

            def linkage(command, **kwargs):
                dependency = (
                    str(library) if command[-1] == str(extension) else "/usr/lib/libSystem.B.dylib"
                )
                return SimpleNamespace(
                    returncode=0,
                    stdout=f"{command[-1]}:\n\t{dependency} (compatibility version 1.0.0)\n",
                )

            files = {extension}
            with (
                patch.object(card_install.sys, "modules", {}),
                patch.object(card_install.platform, "system", return_value="Darwin"),
                patch.object(Path, "is_file", return_value=True),
                patch.object(card_install.bundle, "file_hash", return_value="unit-hash"),
                patch.object(card_install.subprocess, "run", side_effect=linkage),
            ):
                resolutions = card_install._native_dependencies(files, [])
            self.assertIn(library.resolve(), files)
            self.assertEqual(resolutions[0]["path"], str(library))

    def test_native_linkage_handles_fat_binary_architecture_headers(self):
        with tempfile.TemporaryDirectory() as directory:
            native = Path(directory).resolve() / "native.so"
            native.write_bytes(b"unit-native-code")
            output = (f"{native} (architecture x86_64):\n"
                      "\t/usr/lib/libSystem.B.dylib (compatibility version 1.0.0)\n\n"
                      f"{native} (architecture arm64):\n"
                      "\t/usr/lib/libSystem.B.dylib (compatibility version 1.0.0)\n")
            with (
                patch.object(card_install.sys, "modules", {}),
                patch.object(card_install.platform, "system", return_value="Darwin"),
                patch.object(Path, "is_file", return_value=True),
                patch.object(card_install.subprocess, "run",
                             return_value=SimpleNamespace(returncode=0, stdout=output)),
            ):
                self.assertEqual(card_install._native_dependencies({native}, [native]), [])

    def write_checks(self, target, sealed):
        path = target / "spec/oracle/card/checks.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "approval_status": "approved",
                    "checks": [{"evaluator_artifacts": ["oracle.sh"] if sealed else []}],
                    "approved_required_binding": {
                        "evaluator_artifacts": [
                            {
                                "path": "oracle.sh",
                                "hash": card_install.bundle.file_hash(target / "oracle.sh"),
                            }
                        ]
                        if sealed
                        else []
                    },
                }
            )
        )
        return path

    def test_install_never_generates_or_approves_reviewed_policy(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            config = target / "quality.json"
            config.write_text(json.dumps({"approval_provenance": "reviewed", "threshold": 0.8}))
            (target / "oracle.sh").write_text(
                'THRESHOLD="${THRESHOLD:-0.8}"\nCOMPONENTS=(\n)\nweighted_sum="0"\n'
            )
            self.write_checks(target, True)
            with (
                patch.object(
                    card_install,
                    "validated_policy",
                    return_value={
                        "quality": {"config": str(config)},
                    },
                ),
                patch.object(design_eval._score, "validate_freeze"),
                patch.object(design_eval._fe, "register_manifest"),
                patch.object(
                    card_install.subprocess,
                    "run",
                    return_value=SimpleNamespace(returncode=0, stderr=""),
                ) as command,
            ):
                card_install.install(target)
            operations = [call.args[0][2] for call in command.call_args_list]
            self.assertEqual(operations, ["install"])

    def test_generation_binds_reviewed_quality_threshold_not_scaffold_default(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            config = target / "quality.json"
            config.write_text(json.dumps({"approval_provenance": "reviewed", "threshold": 0.8}))
            (target / "oracle.sh").write_text(
                'THRESHOLD="${THRESHOLD:-0.5}"\nCOMPONENTS=(\n)\nweighted_sum="0"\n'
            )
            self.write_checks(target, False)
            with (
                patch.object(
                    card_install,
                    "validated_policy",
                    return_value={
                        "quality": {"config": str(config)},
                    },
                ),
                patch.object(design_eval._score, "validate_freeze"),
                patch.object(design_eval._fe, "register_manifest"),
                patch.object(
                    card_install.subprocess,
                    "run",
                    return_value=SimpleNamespace(returncode=0, stderr=""),
                ) as command,
            ):
                card_install.generate(target)
            self.assertIn('THRESHOLD="${THRESHOLD:-0.8}"', (target / "oracle.sh").read_text())
            self.assertEqual([call.args[0][2] for call in command.call_args_list], ["generate"])

    def test_staging_never_approves_and_draft_driver_cannot_run_or_install(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            config = target / "quality.json"
            config.write_text(json.dumps({"approval_provenance": "reviewed", "threshold": 0.8}))
            (target / "oracle.sh").write_text('THRESHOLD="${THRESHOLD:-0.8}"\n')
            path = self.write_checks(target, False)
            with (
                patch.object(
                    card_install,
                    "validated_policy",
                    return_value={"quality": {"config": str(config)}},
                ),
                patch.object(design_eval._score, "validate_freeze"),
                patch.object(
                    card_install.subprocess,
                    "run",
                    return_value=SimpleNamespace(returncode=0, stderr=""),
                ) as command,
            ):
                with self.assertRaisesRegex(ValueError, "oracle|seal"):
                    card_install.install(target)
                self.assertEqual(command.call_count, 0)
                card_install.seal_driver(target)
                self.assertEqual(
                    [call.args[0][2] for call in command.call_args_list], ["install", "generate"]
                )
                plan = json.loads(path.read_bytes())
                self.assertEqual(plan["approval_status"], "draft")
                self.assertIn("oracle.sh", plan["checks"][0]["evaluator_artifacts"])
                with self.assertRaisesRegex(ValueError, "approval|seal"):
                    card_install.install(target)


if __name__ == "__main__":
    unittest.main()
