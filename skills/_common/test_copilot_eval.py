import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent


class CopilotReplyTests(unittest.TestCase):
    def runtime(self):
        path = ROOT / "copilot_eval.py"
        self.assertTrue(path.is_file(), "native evaluation runtime must be shipped")
        spec = importlib.util.spec_from_file_location("copilot_eval_test", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_text_comes_from_completed_message_not_terminal_result(self):
        runtime = self.runtime()
        events = [
            {"type": "assistant.message_delta", "data": {"deltaContent": "partial"}},
            {
                "type": "assistant.message",
                "data": {
                    "content": '{"score":0.8}',
                    "model": "pinned-model",
                    "phase": "final_answer",
                },
            },
            {"type": "assistant.idle"},
            {"type": "result", "exitCode": 0, "sessionId": "fresh-session"},
        ]
        reply = runtime.parse_response(
            "\n".join(json.dumps(event) for event in events),
            expected_model="pinned-model",
        )
        self.assertEqual(
            reply,
            {"text": '{"score":0.8}', "model": "pinned-model",
             "session_id": "fresh-session", "usage": None},
        )

    def test_malformed_failed_or_unpinned_responses_refuse(self):
        runtime = self.runtime()
        message = {
            "type": "assistant.message",
            "data": {"content": '{"score":0.8}', "model": "pinned", "phase": "final_answer"},
        }
        terminal = {"type": "result", "exitCode": 0, "sessionId": "fresh"}
        bad_cases = [
            "not JSON",
            json.dumps(message),
            json.dumps(terminal),
            "\n".join(map(json.dumps, [message, dict(terminal, exitCode=1)])),
            "\n".join(map(json.dumps, [message, dict(terminal, exitCode=True)])),
            "\n".join(map(json.dumps, [message, terminal, {"type": "session.error"}])),
        ]
        for body in bad_cases:
            with self.subTest(body=body), self.assertRaises(runtime.CopilotError):
                runtime.parse_response(body, expected_model="pinned")
        with self.assertRaises(runtime.CopilotError):
            runtime.parse_response(
                "\n".join(map(json.dumps, [message, terminal])), expected_model="different"
            )

    def test_native_definition_requires_explicit_defaults_and_runtime(self):
        runtime = self.runtime()
        valid = {
            "transport": "copilot",
            "model": "pinned",
            "decoding_mode": "native-default",
            "runtime_version": "1.0.96-2",
        }
        runtime.validate_judge(valid)
        for field in ("temperature", "max_tokens", "seed", "top_p", "unknown_control"):
            with self.subTest(field=field), self.assertRaises(runtime.CopilotError):
                runtime.validate_judge(dict(valid, **{field: None}))
        for field in ("model", "decoding_mode", "runtime_version"):
            missing = dict(valid)
            missing.pop(field)
            with self.subTest(field=field), self.assertRaises(runtime.CopilotError):
                runtime.validate_judge(missing)
        with self.assertRaises(runtime.CopilotError):
            runtime.validate_judge(dict(valid, model="auto"))

    def test_native_usage_is_preserved_without_dollar_conversion(self):
        runtime = self.runtime()
        usage = {"premiumRequests": 0.25, "durations": {"apiMs": 120}}
        events = [
            {"type": "assistant.message", "data": {
                "content": "public", "model": "pinned", "phase": "final_answer",
            }},
            {"type": "result", "exitCode": 0, "sessionId": "fresh", "usage": usage},
        ]
        reply = runtime.parse_response("\n".join(map(json.dumps, events)), expected_model="pinned")
        self.assertEqual(reply["usage"], usage)
        self.assertNotIn("cost_usd", reply)

    def test_invocation_is_fresh_readonly_pinned_and_image_bearing(self):
        runtime = self.runtime()
        output = "\n".join(map(json.dumps, [
            {"type": "assistant.message", "data": {
                "content": '{"score":0.8}', "model": "pinned", "phase": "final_answer",
            }},
            {"type": "result", "exitCode": 0, "sessionId": "fresh"},
        ]))
        version = subprocess.CompletedProcess([], 0, "GitHub Copilot CLI 1.0.96-2.\n", "")
        answer = subprocess.CompletedProcess([], 0, output, "")
        with tempfile.TemporaryDirectory() as temporary, \
                mock.patch.dict(runtime.os.environ, {}, clear=True), \
                mock.patch.object(runtime.shutil, "which", return_value="/fake/copilot"), \
                mock.patch.object(runtime.subprocess, "run", side_effect=[version, answer]) as run:
            directory = Path(temporary)
            images = [directory / "first.png", directory / "second.png"]
            for image in images:
                image.write_bytes(b"fixture image")
            reply = runtime.invoke(
                "prompt", model="pinned", frozen_version="1.0.96-2",
                attachments=images, cwd=directory,
            )
        command = run.call_args_list[-1].args[0]
        for flag in (
            "--no-auto-update", "--no-custom-instructions", "--available-tools=view",
            "--deny-tool=write", "--deny-tool=shell", "--disable-builtin-mcps",
            "--model=pinned", "--output-format=json",
        ):
            self.assertIn(flag, command)
        self.assertNotIn("--resume", command)
        self.assertFalse(any("allow-all" in item for item in command))
        self.assertEqual(sum(item.startswith("--attachment=") for item in command), 2)
        self.assertEqual(reply["runtime_version"], "1.0.96-2")
        self.assertEqual(run.call_args.kwargs["cwd"], str(directory))

    def test_runtime_mismatch_refuses_before_model_call(self):
        runtime = self.runtime()
        version = subprocess.CompletedProcess([], 0, "GitHub Copilot CLI 1.0.97-1.\n", "")
        with mock.patch.dict(runtime.os.environ, {}, clear=True), \
                mock.patch.object(runtime.shutil, "which", return_value="/fake/copilot"), \
                mock.patch.object(runtime.subprocess, "run", return_value=version) as run:
            with self.assertRaises(runtime.CopilotError):
                runtime.invoke("prompt", model="pinned", frozen_version="1.0.96-2")
        self.assertEqual(run.call_count, 1)

    def test_native_score_rejects_boolean_nonfinite_and_out_of_range(self):
        runtime = self.runtime()
        self.assertEqual(runtime.parse_score('{"score":0.8}')["score"], 0.8)
        for score in (True, "0.8", float("nan"), float("inf"), -0.1, 1.1):
            with self.subTest(score=score), self.assertRaises(runtime.CopilotError):
                runtime.parse_score(json.dumps({"score": score}))


if __name__ == "__main__":
    unittest.main()
