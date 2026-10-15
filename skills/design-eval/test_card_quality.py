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

    def test_explicit_one_replacement_extends_existing_history_by_only_one(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for _ in range(8):
                card_quality.reserve(root, 8)
            self.assertEqual(card_quality.reserve(root, 9), 9)
            with self.assertRaisesRegex(ValueError, "allowance"):
                card_quality.reserve(root, 9)
            for invalid in (True, 0, -1, "10", float("inf")):
                with self.assertRaisesRegex(ValueError, "allowance"):
                    card_quality.reserve(root, invalid)

    def test_new_checkpoint_copies_consumed_attempt_instead_of_resetting_budget(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original, checkpoint = root / "original", root / "checkpoint"
            card_quality.reserve(original, 8)
            rows = card_quality.inherit_attempts(original, checkpoint, 9)
            self.assertEqual([row["path"] for row in rows], ["1.claim"])
            self.assertEqual(
                (original / "1.claim").read_bytes(), (checkpoint / "1.claim").read_bytes()
            )
            self.assertEqual(
                [card_quality.reserve(checkpoint, 9) for _ in range(8)], list(range(2, 10))
            )
            with self.assertRaisesRegex(ValueError, "allowance"):
                card_quality.reserve(checkpoint, 9)
            with self.assertRaises(FileExistsError):
                card_quality.inherit_attempts(original, checkpoint, 9)

    def test_new_approved_batch_carries_all_nine_spent_attempts_and_adds_exactly_eight(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old, new = root / "old", root / "new"
            for _ in range(9):
                card_quality.reserve(old, 9)
            rows = card_quality.inherit_attempts(old, new, 17)
            self.assertEqual(len(rows), 9)
            self.assertEqual([card_quality.reserve(new, 17) for _ in range(8)], list(range(10, 18)))
            with self.assertRaisesRegex(ValueError, "allowance"):
                card_quality.reserve(new, 17)
            with self.assertRaisesRegex(ValueError, "eight|history|allowance"):
                card_quality.inherit_attempts(old, root / "too-many", 18)
            next_epoch = root / "next-epoch"
            history = card_quality.inherit_attempts(new, next_epoch, 25)
            self.assertEqual([row["path"] for row in history], [f"{n}.claim" for n in range(1, 18)])
            self.assertEqual(card_quality.reserve(next_epoch, 25), 18)


if __name__ == "__main__":
    unittest.main()
