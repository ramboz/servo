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
    def test_install_never_generates_or_approves_reviewed_policy(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            config = target / "quality.json"
            config.write_text(json.dumps({"approval_provenance": "reviewed", "threshold": 0.8}))
            (target / "oracle.sh").write_text(
                'THRESHOLD="${THRESHOLD:-0.8}"\nCOMPONENTS=(\n)\nweighted_sum="0"\n'
            )
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


if __name__ == "__main__":
    unittest.main()
