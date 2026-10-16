"""Quality provenance and allowance controls, without live model invocations."""

import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import card_quality


class QualityControls(unittest.TestCase):
    def test_native_judge_command_is_context_isolated_read_only_and_subscription_compatible(self):
        command = card_quality.judge_command(
            Path("/native/claude"), "approved rubric only", "claude-opus-5"
        )
        for flag in (
            "--safe-mode",
            "--restricted",
            "--strict-mcp-config",
            "--tools",
            "--allowedTools",
            "--permission-mode",
        ):
            self.assertIn(flag, command)
        for forbidden in ("--bare", "--fallback-model", "--dangerously-skip-permissions"):
            self.assertNotIn(forbidden, command)
        self.assertIn("dontAsk", command)
        self.assertEqual(command[command.index("--model") + 1], "claude-opus-5")

    def test_unrelated_tokens_are_not_forwarded_and_unselected_provider_refuses(self):
        with patch.dict(
            "os.environ",
            {
                "HOME": "/unit-home",
                "GH_TOKEN": "unit-not-secret",
                "GITHUB_TOKEN": "unit-not-secret",
                "OPENAI_API_KEY": "unit-not-secret",
                "AWS_SECRET_ACCESS_KEY": "unit-not-secret",
                "CLAUDE_CODE_OAUTH_TOKEN": "unit-normal-auth",
            },
            clear=True,
        ):
            env = card_quality.judge_environment()
            self.assertNotIn("GH_TOKEN", env)
            self.assertNotIn("GITHUB_TOKEN", env)
            self.assertNotIn("OPENAI_API_KEY", env)
            self.assertNotIn("AWS_SECRET_ACCESS_KEY", env)
            self.assertEqual(env["CLAUDE_CODE_OAUTH_TOKEN"], "unit-normal-auth")
            self.assertEqual(env["HOME"], "/unit-home")
        for key, value in (
            ("CLAUDE_CODE_USE_BEDROCK", "1"),
            ("ANTHROPIC_BASE_URL", "https://unselected.invalid"),
            ("ANTHROPIC_API_KEY", "unit-not-secret"),
        ):
            with patch.dict("os.environ", {key: value}, clear=True):
                with self.assertRaisesRegex(ValueError, "provider|subscription|auth"):
                    card_quality.judge_environment()

    def test_script_cli_entrypoint_is_not_silently_treated_as_native_closure(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "claude"
            path.write_text("#!/bin/sh\nprintf 'unapproved wrapper'\n")
            with self.assertRaisesRegex(ValueError, "native|script|entrypoint"):
                card_quality.assert_native_cli(path)

    def test_rewritten_sealed_image_is_detected_even_if_bytes_are_restored(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.png"
            path.write_bytes(b"original-image")
            original = card_quality.input_identity(path)
            path.write_bytes(b"changed-image")
            path.write_bytes(b"original-image")
            self.assertNotEqual(card_quality.input_identity(path), original)

    def test_later_state_cannot_rewrite_an_earlier_states_sealed_image(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            refs, destination = root / "refs", root / "run"
            refs.mkdir()
            destination.mkdir()
            binary = root / "claude"
            binary.write_bytes(b"\xcf\xfa\xed\xfe")
            shots = {}
            for state in ("normal", "open"):
                shots[state] = root / f"{state}.png"
                shots[state].write_bytes(b"unit-actual-" + state.encode())
                (refs / f"{state}.png").write_bytes(b"unit-reference-" + state.encode())
            config = {
                "schema_version": 2,
                "approval_provenance": "reviewed",
                "approved_content_hash": "unit-only",
                "judge": {
                    "execution_mode": "safe-restricted-read-only",
                    "auth_mode": "claude-subscription",
                    "batch_purpose": "unit-only",
                    "calibration_limit": 8,
                    "transport": "cli",
                    "decoding_mode": "native-default",
                    "model": "opus",
                    "runtime": {
                        "binary": str(binary),
                        "hash": card_quality.file_hash(binary),
                        "version": "unit-only",
                    },
                },
                "samples": {"n": 4, "k": 1.0, "delta": 0.03},
                "threshold": 0.8,
                "viewport": {"width": 800, "height": 600, "deviceScaleFactor": 1},
                "screens": [
                    {"id": state, "reference": f"refs/{state}.png", "weight": 1.0}
                    for state in shots
                ],
                "hashes": {
                    f"refs/{state}.png": card_quality.file_hash(refs / f"{state}.png")
                    for state in shots
                },
            }
            path = root / "config.json"
            path.write_text(json.dumps(config))
            calls = []

            def native(command, **kwargs):
                if "--version" in command:
                    return SimpleNamespace(returncode=0, stdout="unit-only")
                calls.append(command)
                if len(calls) == 5:
                    earlier = destination / "judge-inputs/normal-actual.png"
                    data = earlier.read_bytes()
                    earlier.write_bytes(b"changed-during-open")
                    earlier.write_bytes(data)
                return SimpleNamespace(
                    returncode=0, stdout=b'{"result":"{\\"score\\":0.9}"}', stderr=b""
                )

            with (
                patch.dict("os.environ", {}, clear=True),
                patch.object(card_quality.scoring, "_require_schema_v2"),
                patch.object(card_quality.scoring, "validate_freeze"),
                patch.object(card_quality.scoring, "_validate_policy"),
                patch.object(card_quality.scoring, "_scoring_prompt", return_value="unit-rubric"),
                patch.object(card_quality.subprocess, "run", side_effect=native),
            ):
                with self.assertRaisesRegex(ValueError, "sealed judge input changed"):
                    card_quality.run(
                        path, shots, destination, root / "allowance",
                        capture_hashes={s: card_quality.file_hash(p) for s, p in shots.items()},
                    )

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

    def quality_fixture(self, root, limit=16, prior=None):
        refs = root / "refs"
        refs.mkdir()
        binary = root / "claude"
        binary.write_bytes(b"\xcf\xfa\xed\xfe")
        shots = {}
        for state in ("normal", "open"):
            shots[state] = root / f"{state}.png"
            shots[state].write_bytes(b"unit-actual-" + state.encode())
            (refs / f"{state}.png").write_bytes(b"unit-reference-" + state.encode())
        config = {
            "schema_version": 2,
            "approval_status": "approved",
            "approval_provenance": "reviewed",
            "approved_content_hash": "unit-only",
            "judge": {
                "execution_mode": "safe-restricted-read-only",
                "auth_mode": "claude-subscription",
                "batch_purpose": "explicit two-run A/B unit control; no live calls",
                "calibration_limit": limit,
                "prior_attempts": prior or [],
                "transport": "cli",
                "decoding_mode": "native-default",
                "model": "opus",
                "runtime": {
                    "binary": str(binary),
                    "hash": card_quality.file_hash(binary),
                    "version": "unit-only",
                },
            },
            "samples": {"n": 4, "k": 1.0, "delta": 0.03},
            "threshold": 0.8,
            "viewport": {"width": 800, "height": 600, "deviceScaleFactor": 1},
            "screens": [
                {"id": state, "reference": f"refs/{state}.png", "weight": 1.0}
                for state in shots
            ],
            "hashes": {
                f"refs/{state}.png": card_quality.file_hash(refs / f"{state}.png")
                for state in shots
            },
        }
        config["hashes"] = card_quality.scoring.artifact_hashes(config, root)
        config["approved_content_hash"] = card_quality.scoring.definition_hash(config)
        path = root / "config.json"
        path.write_text(json.dumps(config))
        return path, shots

    def mocked_quality(self, path, shots, destination, allowance, calls, on_reply=None):
        def native(command, **kwargs):
            if "--version" in command:
                return SimpleNamespace(returncode=0, stdout="unit-only")
            calls.append(command)
            if on_reply is not None:
                on_reply(len(calls), allowance)
            return SimpleNamespace(
                returncode=0, stdout=b'{"result":"{\\"score\\":0.9}"}', stderr=b""
            )

        destination.mkdir(exist_ok=True)
        with (
            patch.dict("os.environ", {}, clear=True),
            patch.object(card_quality.scoring, "_require_schema_v2"),
            patch.object(card_quality.scoring, "_validate_policy"),
            patch.object(card_quality.scoring, "_scoring_prompt", return_value="unit-rubric"),
            patch.object(card_quality.subprocess, "run", side_effect=native),
        ):
            return card_quality.run(
                path, shots, destination, allowance,
                capture_hashes={state: card_quality.file_hash(p) for state, p in shots.items()},
            )

    def test_explicit_whole_batches_preserve_inherited_history(self):
        for spent in (0, 1, 9, 49):
            with self.subTest(spent=spent), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                old, new = root / "old", root / "new"
                old.mkdir()
                for _ in range(spent):
                    card_quality.reserve(old, spent)
                rows = card_quality.inherit_attempts(old, new, spent + 16)
                self.assertEqual(len(rows), spent)
                self.assertEqual(
                    [card_quality.reserve(new, spent + 16) for _ in range(16)],
                    list(range(spent + 1, spent + 17)),
                )
                with self.assertRaisesRegex(ValueError, "allowance"):
                    card_quality.reserve(new, spent + 16)

    def test_two_runs_share_one_unchanged_explicitly_approved_definition(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path, shots = self.quality_fixture(root)
            original = path.read_bytes()
            calls = []
            results = [
                self.mocked_quality(path, shots, root / f"run-{i}", root / "allowance", calls)
                for i in range(2)
            ]
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(len(calls), 16)
            self.assertEqual(
                [[row["invocation"] for row in result["invocations"]] for result in results],
                [list(range(1, 9)), list(range(9, 17))],
            )
            self.assertEqual(results[0]["config_hash"], results[1]["config_hash"])
            self.assertEqual(results[0]["definition_hash"], results[1]["definition_hash"])
            with self.assertRaisesRegex(ValueError, "remaining allowance"):
                self.mocked_quality(path, shots, root / "exhausted", root / "allowance", calls)
            self.assertEqual(len(calls), 16)

    def test_default_one_batch_and_frozen_cap_drift_still_refuse_more_calls(self):
        for limit, expand in ((8, False), (16, True)):
            with self.subTest(limit=limit), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                path, shots = self.quality_fixture(root, limit=limit)
                calls = []
                self.mocked_quality(path, shots, root / "first", root / "allowance", calls)
                if expand:
                    config = json.loads(path.read_text())
                    config["judge"]["calibration_limit"] = 24
                    path.write_text(json.dumps(config))
                    with self.assertRaises(card_quality.scoring.StaleError):
                        self.mocked_quality(path, shots, root / "second", root / "allowance", calls)
                else:
                    with self.assertRaisesRegex(ValueError, "remaining allowance"):
                        self.mocked_quality(path, shots, root / "second", root / "allowance", calls)
                self.assertEqual(len(calls), 8)

    def test_invalid_batch_caps_refuse_before_judging_or_copying_history(self):
        for limit in (True, False, 0, -8, 7, 9, 15, 17, "16", 16.0, float("inf"), float("nan")):
            with self.subTest(limit=limit), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                old = root / "old"
                old.mkdir()
                with self.assertRaisesRegex(ValueError, "allowance|eight|batch"):
                    card_quality.inherit_attempts(old, root / "copied", limit)
                self.assertFalse((root / "copied").exists())
                path, shots = self.quality_fixture(root, limit=limit)
                calls = []
                with self.assertRaisesRegex(ValueError, "allowance|eight|batch|non-finite"):
                    self.mocked_quality(path, shots, root / "run", root / "allowance", calls)
                self.assertEqual(calls, [])
                self.assertFalse((root / "allowance").exists())

    def test_second_run_refuses_changed_or_partial_history_and_output_replay(self):
        for mutation in ("prior", "consumed", "gap", "tail", "extra", "remaining", "replay"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                old, allowance = root / "old", root / "allowance"
                card_quality.reserve(old, 1)
                prior = card_quality.inherit_attempts(old, allowance, 17)
                path, shots = self.quality_fixture(root, limit=17, prior=prior)
                calls = []
                self.mocked_quality(path, shots, root / "first", allowance, calls)
                if mutation in ("prior", "consumed"):
                    (allowance / ("1.claim" if mutation == "prior" else "2.claim")).write_bytes(
                        b"changed consumed history"
                    )
                elif mutation == "gap":
                    (allowance / "2.claim").unlink()
                elif mutation == "tail":
                    (allowance / "9.claim").unlink()
                elif mutation == "extra":
                    (allowance / "unexpected.claim").write_bytes(b"untracked")
                elif mutation == "remaining":
                    card_quality._reserve_attempt(
                        allowance, 17, prior, card_quality._attempt_history(allowance)
                    )
                destination = root / ("first" if mutation == "replay" else "second")
                if mutation == "replay":
                    with self.assertRaises(FileExistsError):
                        self.mocked_quality(path, shots, destination, allowance, calls)
                else:
                    with self.assertRaises(ValueError):
                        self.mocked_quality(path, shots, destination, allowance, calls)
                self.assertEqual(len(calls), 8)

    def test_deleting_newest_claim_during_reply_never_refunds_a_judgment(self):
        for invocation in (1, 8):
            with self.subTest(invocation=invocation), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                path, shots = self.quality_fixture(root)
                calls = []

                def remove_tail(number, allowance, invocation=invocation):
                    if number == invocation:
                        (allowance / f"{number}.claim").unlink()

                with self.assertRaisesRegex(ValueError, "history|consumed|claim"):
                    self.mocked_quality(
                        path, shots, root / "run", root / "allowance", calls, remove_tail
                    )
                self.assertEqual(len(calls), invocation)

    def test_initialized_counter_loss_corruption_or_rewind_never_refunds_claims(self):
        for mutation in ("missing", "corrupt", "rewind", "boolean"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                path, shots = self.quality_fixture(root)
                calls = []
                allowance = root / "allowance"
                self.mocked_quality(path, shots, root / "first", allowance, calls)
                counter = card_quality._consumed_state(allowance) / "counter.json"
                if mutation == "missing":
                    counter.unlink()
                elif mutation == "corrupt":
                    counter.write_text("not-json")
                else:
                    counter.write_text(
                        json.dumps({"consumed": True if mutation == "boolean" else 0})
                    )
                with self.assertRaises((ValueError, OSError)):
                    self.mocked_quality(path, shots, root / "second", allowance, calls)
                self.assertEqual(len(calls), 8)

    def test_failed_atomic_counter_update_is_not_reconstructed_as_lower_consumption(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path, shots = self.quality_fixture(root)
            calls = []
            allowance = root / "allowance"
            self.mocked_quality(path, shots, root / "first", allowance, calls)
            with patch.object(card_quality.os, "replace", side_effect=OSError("unit disk failure")):
                with self.assertRaisesRegex(OSError, "unit disk failure"):
                    self.mocked_quality(path, shots, root / "second", allowance, calls)
            with self.assertRaisesRegex(ValueError, "high-water"):
                self.mocked_quality(path, shots, root / "third", allowance, calls)
            self.assertEqual(len(calls), 8)

    def test_stale_admission_never_reserves_past_the_locked_cap(self):
        with tempfile.TemporaryDirectory() as directory:
            allowance = Path(directory) / "allowance"
            observed = []
            for _ in range(8):
                _, observed = card_quality._reserve_attempt(allowance, 8, [], observed)
            original = card_quality.reserve

            def lose_tail_then_reserve(path, limit):
                (path / "8.claim").unlink()
                return original(path, limit)

            with patch.object(
                card_quality, "reserve", side_effect=lose_tail_then_reserve
            ) as reserve:
                with self.assertRaisesRegex(ValueError, "exhausted|allowance"):
                    card_quality._reserve_attempt(allowance, 8, [], [])
                reserve.assert_not_called()

    def test_non_next_reservation_cannot_reuse_an_observed_claim_before_judging(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path, shots = self.quality_fixture(root)
            allowance, calls = root / "allowance", []
            self.mocked_quality(path, shots, root / "first", allowance, calls)
            original = card_quality.reserve

            def lose_tail_then_reserve(directory, limit):
                (directory / "8.claim").unlink()
                return original(directory, limit)

            with patch.object(card_quality, "reserve", side_effect=lose_tail_then_reserve):
                with self.assertRaisesRegex(ValueError, "monotonic|claim"):
                    self.mocked_quality(path, shots, root / "second", allowance, calls)
            self.assertEqual(len(calls), 8)

    def test_claim_and_counter_commit_sync_files_and_directory_entries(self):
        with tempfile.TemporaryDirectory() as directory:
            allowance = Path(directory) / "allowance"
            opened, directories, files = {}, set(), []
            original_open, original_sync = os.open, os.fsync

            def record_open(path, *args, **kwargs):
                descriptor = original_open(path, *args, **kwargs)
                opened[descriptor] = Path(path).resolve()
                return descriptor

            def record_sync(descriptor):
                if stat.S_ISDIR(os.fstat(descriptor).st_mode):
                    directories.add(opened[descriptor])
                else:
                    files.append(descriptor)
                return original_sync(descriptor)

            with (
                patch.object(card_quality.os, "open", side_effect=record_open),
                patch.object(card_quality.os, "fsync", side_effect=record_sync),
            ):
                card_quality._reserve_attempt(allowance, 8, [], [])
            expected = {
                path.resolve()
                for path in (
                    allowance, allowance.parent, card_quality._consumed_state(allowance)
                )
            }
            self.assertTrue(expected.issubset(directories))
            self.assertGreaterEqual(len(files), 3)


if __name__ == "__main__":
    unittest.main()
