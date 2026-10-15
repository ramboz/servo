"""Quality provenance and allowance controls, without live model invocations."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import card_quality


class QualityControls(unittest.TestCase):
    def test_requested_alias_is_not_reported_as_observed_concrete_identity(self):
        result = card_quality.parse_reply(
            {
                "result": '{"score":0.9,"reasoning":"bounded fixture"}',
                "modelUsage": {"claude-opus-observed": {"inputTokens": 1}},
            },
            "opus",
        )
        self.assertEqual(result["requested_model"], "opus")
        self.assertEqual(result["observed_models"], ["claude-opus-observed"])
        self.assertEqual(result["score"], 0.9)
        unknown = card_quality.parse_reply({"result": '{"score":0.9}'}, "opus")
        self.assertEqual(unknown["observed_models"], [])
        self.assertIn("not exposed", unknown["identity_scope"])

    def test_invalid_scores_and_native_errors_refuse_without_clamping(self):
        for value in (
            '{"score":true}',
            '{"score":1.01}',
            '{"score":-0.1}',
            '{"score":"0.9"}',
            '{"score":NaN}',
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                card_quality.parse_reply({"result": value}, "opus")
        with self.assertRaises(ValueError):
            card_quality.parse_reply({"is_error": True, "result": "unavailable"}, "opus")

    def test_exposed_incompatible_model_is_refused_not_silently_scored(self):
        for model in ("claude-sonnet-observed", "gpt-observed"):
            with self.subTest(model=model), self.assertRaisesRegex(ValueError, "model"):
                card_quality.parse_reply(
                    {
                        "result": '{"score":0.99}',
                        "modelUsage": {model: {}},
                    },
                    "opus",
                )

    def test_allowance_is_exclusive_persistent_and_never_silently_replenished(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for index in range(1, 9):
                self.assertEqual(card_quality.reserve(root, 8), index)
            with self.assertRaisesRegex(ValueError, "allowance"):
                card_quality.reserve(root, 8)
            self.assertEqual(len(list(root.iterdir())), 8)


if __name__ == "__main__":
    unittest.main()
