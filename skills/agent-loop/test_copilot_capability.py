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
        # Spec 043-02: `--plan` is now CONSULTED under copilot (a plan can supply
        # the credit ceiling). A plan that supplies NO credit ceiling still
        # cannot satisfy the native contract, so it refuses
        # native_capability_unavailable exactly like the flag-only surfaces. The
        # plan lives OUTSIDE self.target so the no-writes assertion still holds.
        # (A missing / malformed plan now refuses as a plan error, not this
        # blanket native refusal — covered in test_loop.py's plan-under-copilot
        # tests; the invariant here is the no-dispatch/no-writes refusal.)
        plan_dir = tempfile.TemporaryDirectory(prefix="servo-native-plan-")
        self.addCleanup(plan_dir.cleanup)
        no_ceiling_plan = Path(plan_dir.name) / "plan.json"
        no_ceiling_plan.write_text(json.dumps({
            "schema_version": 1, "provenance": "compiled",
            "budget": {"max_iterations": 5},
        }))
        for flags in (
            ["--prompt", "x"],
            ["--driver", "loop", "--prompt", "x"],
            ["--driver", "goal", "--prompt", "x"],
            ["--background", "--prompt", "x"],
            ["--emit-routine-prompt", "--prompt", "x"],
            ["--resume", "native-run"],
            ["--resume", "native-run", "--resume-anyway"],
            ["--plan", str(no_ceiling_plan), "--prompt", "x"],
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

    def test_claude_state_refuses_copilot_resume(self):
        # Spec 043-03 AC4 (the new direction the narrowed guard must also refuse):
        # a persisted CLAUDE run cannot resume as copilot — a genuine backend
        # CHANGE stays refused with the existing `backend_mismatch` reason, before
        # any claude-version probe and with the state file untouched.
        run_id = "claude-run"
        state_path = self.target / ".servo/runs" / run_id / "state.json"
        state_path.parent.mkdir(parents=True)
        for fields in (
            {"backend": "claude", "state_schema_version": 1},
            {"state_schema_version": 1},  # unmarked v1 == claude
        ):
            with self.subTest(fields=fields):
                raw = json.dumps(fields)
                state_path.write_text(raw)
                stdout = io.StringIO()
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(io.StringIO()):
                    with patch.object(
                        loop, "_get_claude_version", side_effect=AssertionError("probe")
                    ):
                        rc = loop.run_loop(
                            self.target, host="copilot", prompt=None,
                            max_iterations=None, cost_ceiling=None,
                            context_fill_threshold=None, credit_ceiling=500,
                            resume_run_id=run_id, resume_anyway=True,
                        )
                self.assertEqual(rc, 2)
                self.assertEqual(
                    json.loads(stdout.getvalue())["terminal_reason"], "backend_mismatch")
                self.assertEqual(state_path.read_text(), raw)

    def test_unsound_credit_baseline_value_refuses_copilot_resume(self):
        # Spec 043-03 AC5: a same-backend copilot resume whose persisted session
        # baseline VALUE is unsound — null (a prior fail-closed halt wrote null,
        # never 0), absent, boolean, float, or negative — cannot re-establish the
        # session-delta baseline (ADR-0048 A2), so it fails closed
        # `credit_baseline_unavailable` before any probe or worker call. Each case
        # carries a CLEAN `last_terminal_reason`, so the refusal is unambiguously
        # the value check, not the staleness check below (non-vacuous isolation).
        # (A bare backend-matched copilot resume reaches THIS guard, proving the
        # backend guard was narrowed to allow copilot -> copilot.)
        run_id = "copilot-run"
        state_path = self.target / ".servo/runs" / run_id / "state.json"
        state_path.parent.mkdir(parents=True)
        clean = {"backend": "copilot", "state_schema_version": 1,
                 "last_terminal_reason": "max_iterations_reached"}
        cases = [{**clean, "cumulative_credits_nano": v} for v in (None, -5, True, 1.5)]
        cases.append(dict(clean))  # cumulative_credits_nano absent entirely
        for fields in cases:
            with self.subTest(baseline=fields.get("cumulative_credits_nano", "ABSENT")):
                raw = json.dumps(fields)
                state_path.write_text(raw)
                stdout = io.StringIO()
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(io.StringIO()):
                    with patch.object(
                        loop, "_get_claude_version", side_effect=AssertionError("probe")
                    ):
                        rc = loop.run_loop(
                            self.target, host="copilot", prompt=None,
                            max_iterations=None, cost_ceiling=None,
                            context_fill_threshold=None, credit_ceiling=500,
                            resume_run_id=run_id, resume_anyway=True,
                        )
                self.assertEqual(rc, 2)
                self.assertEqual(
                    json.loads(stdout.getvalue())["terminal_reason"],
                    "credit_baseline_unavailable")
                self.assertEqual(state_path.read_text(), raw)

    def test_interrupted_or_killed_copilot_run_refuses_resume(self):
        # Spec 043-03 AC5 (staleness — the frame-critique's load-bearing case): a
        # copilot run whose baseline VALUE is a valid non-negative int but which
        # did NOT halt on a clean, credit-accounted terminal reason cannot be
        # soundly resumed. On an interruption the credit accumulation is SKIPPED
        # (the interrupt checkpoint finalizes + bumps iteration_count BEFORE
        # `_apply_copilot_credit_iteration`), and an uncaught kill leaves the
        # in-flight invocation's spend orphaned on the billing session (ADR-0048
        # A3: a killed invocation writes no usage file). Either way the persisted
        # baseline is a STALE lower bound, so the resume fails closed
        # `credit_baseline_unavailable` rather than resuming with an unsound total
        # (whose first resumed iteration would either break the OTel-vs-delta
        # reconciliation or silently under-count). This is the slice's own
        # motivating "interrupted run" scenario, made fail-closed.
        run_id = "copilot-run"
        state_path = self.target / ".servo/runs" / run_id / "state.json"
        state_path.parent.mkdir(parents=True)
        # "" is the literal signature a killed Copilot iteration leaves on disk
        # (`_normalize_copilot_result` hardcodes terminal_reason=""); None is a
        # run killed before iteration 1 finalized; "interrupted" is the trapped
        # SIGINT/SIGTERM checkpoint; "oracle_evaluation_refused" / "completed"
        # stand in for other non-progress reasons — all disjoint from the clean
        # resumable set.
        for halt in ("interrupted", "", "completed", None, "oracle_evaluation_refused"):
            fields = {"backend": "copilot", "state_schema_version": 1,
                      "cumulative_credits_nano": 50_000_000_000,
                      "last_terminal_reason": halt}
            with self.subTest(last_terminal_reason=halt):
                raw = json.dumps(fields)
                state_path.write_text(raw)
                stdout = io.StringIO()
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(io.StringIO()):
                    with patch.object(
                        loop, "_get_claude_version", side_effect=AssertionError("probe")
                    ):
                        rc = loop.run_loop(
                            self.target, host="copilot", prompt=None,
                            max_iterations=None, cost_ceiling=None,
                            context_fill_threshold=None, credit_ceiling=500,
                            resume_run_id=run_id, resume_anyway=True,
                        )
                self.assertEqual(rc, 2)
                self.assertEqual(
                    json.loads(stdout.getvalue())["terminal_reason"],
                    "credit_baseline_unavailable")
                self.assertEqual(state_path.read_text(), raw)

    def test_sound_copilot_state_passes_backend_and_baseline_guards(self):
        # Spec 043-03 AC1: a same-backend copilot resume with a SOUND baseline (a
        # valid non-negative int AND a clean, credit-accounted halt reason) is NOT
        # refused by the narrowed backend guard or the AC5 baseline/staleness
        # guards — it proceeds past them to the claude-version forensic check
        # (proven by the patched probe firing). In-process complement to the e2e
        # cross-process resume (test_loop.py).
        run_id = "copilot-run"
        state_path = self.target / ".servo/runs" / run_id / "state.json"
        state_path.parent.mkdir(parents=True)
        for halt in ("max_iterations_reached", "credit_ceiling_reached",
                     "oracle_plateau", "context_full"):
            state_path.write_text(json.dumps({
                "backend": "copilot", "state_schema_version": 1,
                "cumulative_credits_nano": 0, "last_terminal_reason": halt,
                "driver": "loop",
            }))
            with self.subTest(last_terminal_reason=halt):
                with contextlib.redirect_stdout(io.StringIO()), \
                        contextlib.redirect_stderr(io.StringIO()):
                    with patch.object(
                        loop, "_get_claude_version",
                        side_effect=AssertionError("reached-version-check"),
                    ):
                        with self.assertRaises(AssertionError) as ctx:
                            loop.run_loop(
                                self.target, host="copilot", prompt=None,
                                max_iterations=None, cost_ceiling=None,
                                context_fill_threshold=None, credit_ceiling=500,
                                resume_run_id=run_id, resume_anyway=True,
                            )
                self.assertEqual(str(ctx.exception), "reached-version-check")

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
