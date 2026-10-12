from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "servo_capability_loop", Path(__file__).with_name("loop.py")
)
loop = importlib.util.module_from_spec(spec)
spec.loader.exec_module(loop)


class NativeCapabilityRefusalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="servo-native-refusal-")
        self.addCleanup(self.tmp.cleanup)
        self.target = Path(self.tmp.name)

    def _main(self, flags):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            with patch.object(loop.subprocess, "Popen", side_effect=AssertionError("dispatch")):
                with patch.object(loop.subprocess, "run", side_effect=AssertionError("dispatch")):
                    rc = loop.main([str(self.target), "--host", "copilot", *flags])
        return rc, json.loads(stdout.getvalue()), stderr.getvalue()

    def test_all_launch_surfaces_refuse_without_dispatch_or_writes(self):
        for flags in (
            ["--prompt", "x"],
            ["--driver", "loop", "--prompt", "x"],
            ["--driver", "goal", "--prompt", "x"],
            ["--background", "--prompt", "x"],
            ["--emit-routine-prompt", "--prompt", "x"],
            ["--resume", "native-run"],
            ["--resume", "native-run", "--resume-anyway"],
            ["--plan", str(self.target / "nonexistent-plan.json"), "--prompt", "x"],
            ["--cost-ceiling", "0", "--context-fill-threshold", "0", "--prompt", "x"],
            ["--max-ai-credits", "30", "--prompt", "x"],
            ["--_detached-run-id", "native-run", "--prompt", "x"],
        ):
            with self.subTest(flags=flags):
                rc, data, stderr = self._main(flags)
                self.assertEqual(rc, 2)
                self.assertEqual(data["schema_version"], 2)
                self.assertEqual(data["backend"], "copilot")
                self.assertEqual(data["final_oracle_status"], "env_error")
                self.assertEqual(data["terminal_reason"], "native_capability_unavailable")
                self.assertIsNone(data["cumulative_cost_usd"])
                self.assertIsNone(data["context_fill_ratio"])
                self.assertIn("soft", stderr)
                self.assertIn("USD", data["terminal_breadcrumb"])
                self.assertEqual(list(self.target.iterdir()), [])

    def test_explain_routes_reports_unavailable_host_without_claude_probe(self):
        rc, data, _ = self._main(["--explain-routing"])
        self.assertEqual(rc, 0)
        self.assertEqual(data["backend"], "copilot")
        self.assertFalse(data["supported"])
        self.assertIsNone(data["driver"])
        self.assertEqual(list(self.target.iterdir()), [])

    def test_direct_loop_entry_cannot_bypass_public_gate(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(io.StringIO()):
            with patch.object(
                loop, "_install_signal_handlers", side_effect=AssertionError("started")
            ):
                rc = loop.run_loop(
                    self.target, host="copilot", prompt="x", max_iterations=1,
                    cost_ceiling=0, context_fill_threshold=0,
                )
        self.assertEqual(rc, 2)
        self.assertIsNone(json.loads(stdout.getvalue())["cumulative_cost_usd"])
        self.assertEqual(list(self.target.iterdir()), [])

    def test_identified_native_state_refuses_claude_resume_anyway(self):
        run_id = "native-run"
        state_path = self.target / ".servo/runs" / run_id / "state.json"
        state_path.parent.mkdir(parents=True)
        for fields in (
            {"backend": "copilot", "state_schema_version": 1},
            {"host": "copilot", "state_schema_version": 1},
            {"backend": "copilot", "state_schema_version": 2},
            {"state_schema_version": 2},
            {"backend": "claude", "host": "copilot", "state_schema_version": 1},
            {"backend": "copilot", "host": "claude", "state_schema_version": 1},
        ):
            with self.subTest(fields=fields):
                raw = json.dumps(fields)
                state_path.write_text(raw)
                stdout = io.StringIO()
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(io.StringIO()):
                    with patch.object(
                        loop, "_get_claude_version", side_effect=AssertionError("dispatch")
                    ):
                        rc = loop.run_loop(
                            self.target, host="claude", prompt=None, max_iterations=None,
                            cost_ceiling=None, context_fill_threshold=None,
                            resume_run_id=run_id, resume_anyway=True,
                        )
                self.assertEqual(rc, 2)
                self.assertEqual(
                    json.loads(stdout.getvalue())["terminal_reason"], "backend_mismatch"
                )
                self.assertEqual(state_path.read_text(), raw)

    def test_new_foreground_and_background_goal_states_identify_claude(self):
        state = loop._build_goal_state(
            run_id="goal-run", target=self.target, prompt="x", max_turns=1,
            cost_ceiling=2, claude_version="test",
        )
        self.assertEqual(state["backend"], "claude")
        self.assertEqual(state["state_schema_version"], 1)

    def test_new_loop_state_identifies_claude(self):
        state = loop._build_initial_state(
            run_id="loop-run", target=self.target, prompt="x", max_iterations=1,
            cost_ceiling=2, context_fill_threshold=0.75, plateau_window=0,
            plateau_noise_floor=0.01, claude_version="test",
        )
        self.assertEqual(state["backend"], "claude")
        self.assertEqual(state["state_schema_version"], 1)


if __name__ == "__main__":
    unittest.main()
