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

    def test_non_recoverable_non_clean_halt_refuses_resume(self):
        # Spec 043-03 AC5 / 043-04: a copilot run that halted on a non-clean reason
        # which is NOT a recoverable interrupt/kill signature stays fail-closed
        # `credit_baseline_unavailable`. `None` is a run that committed no
        # iteration (no guaranteed resumable session — not recoverable);
        # "credit_usage_unavailable" is a killed worker / partial report that
        # always nulls its baseline, so it has no sound floor for the fork-fresh
        # guard (043-04 keeps it fail-closed, deferred); "completed" /
        # "oracle_evaluation_refused" stand in for other non-progress reasons;
        # "credit_bound_unavailable" / "credit_ceiling_insufficient" are the
        # structural/config refusals (not interrupt/kill). All carry a session id,
        # so the refusal is unambiguously the non-recoverability, not a missing
        # session. The on-disk state is unchanged by the refusal (branch C mutates
        # only the in-memory dict). (043-04 flips "interrupted" / "" to the recovery
        # path — see test_recoverable_interrupt_kill_halt_admits_resume.)
        run_id = "copilot-run"
        state_path = self.target / ".servo/runs" / run_id / "state.json"
        state_path.parent.mkdir(parents=True)
        for halt in (None, "credit_usage_unavailable", "completed",
                     "oracle_evaluation_refused", "credit_bound_unavailable",
                     "credit_ceiling_insufficient"):
            fields = {"backend": "copilot", "state_schema_version": 1,
                      "cumulative_credits_nano": 50_000_000_000,
                      "current_session_id": "sess-abc",
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

    def test_recoverable_interrupt_kill_halt_admits_resume(self):
        # Spec 043-04 AC1: a copilot run that halted on a recoverable interrupt/
        # kill reason — "interrupted" (trapped SIGINT/SIGTERM) or "" (the SIGKILL
        # kill signature) — that persisted a resumable `current_session_id` AND a
        # sound non-negative-int stale baseline is NO LONGER refused at preflight.
        # The recovery of the baseline from the resumed read R is deferred to the
        # first resumed iteration, so preflight proceeds PAST the credit guard to
        # the claude-version probe (which the patch fires). The persisted baseline
        # is a stale lower bound — recovery recovers R, but keeps it as the
        # fork-fresh floor. (credit_usage_unavailable is NOT recoverable — it
        # always nulls its baseline; see test_non_recoverable_non_clean_halt.)
        run_id = "copilot-run"
        state_path = self.target / ".servo/runs" / run_id / "state.json"
        state_path.parent.mkdir(parents=True)
        for halt in ("interrupted", ""):
            fields = {"backend": "copilot", "state_schema_version": 1,
                      "cumulative_credits_nano": 50_000_000_000,
                      "current_session_id": "sess-abc",
                      "last_terminal_reason": halt, "driver": "loop"}
            with self.subTest(last_terminal_reason=halt):
                state_path.write_text(json.dumps(fields))
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

    def test_recoverable_halt_with_unsound_baseline_refuses(self):
        # Spec 043-04 AC3 (fork-fresh guard, frame-critique R2): a recoverable
        # interrupt/kill halt whose persisted baseline is NOT a sound non-negative
        # int (null / absent / negative / bool) cannot anchor the fork-fresh floor
        # (`R − N >= baseline`), so it is refused credit_baseline_unavailable at
        # preflight rather than resuming with a blind guard — even though it has a
        # session id.
        run_id = "copilot-run"
        state_path = self.target / ".servo/runs" / run_id / "state.json"
        state_path.parent.mkdir(parents=True)
        for halt in ("interrupted", ""):
            for baseline in (None, -5, True):
                fields = {"backend": "copilot", "state_schema_version": 1,
                          "cumulative_credits_nano": baseline,
                          "current_session_id": "sess-abc",
                          "last_terminal_reason": halt}
                with self.subTest(last_terminal_reason=halt, baseline=baseline):
                    state_path.write_text(json.dumps(fields))
                    stdout = io.StringIO()
                    with contextlib.redirect_stdout(stdout), \
                            contextlib.redirect_stderr(io.StringIO()):
                        with patch.object(
                            loop, "_get_claude_version",
                            side_effect=AssertionError("probe"),
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

    def test_recoverable_halt_without_session_id_refuses(self):
        # Spec 043-04 AC3: a recoverable interrupt/kill halt whose persisted
        # `current_session_id` is empty/absent has NO reachable billing session —
        # the orphaned-spend session is unreachable, and a fresh invocation would
        # silently abandon it. So it is refused `credit_baseline_unavailable` at
        # preflight (before any worker call or version probe), not recovered.
        run_id = "copilot-run"
        state_path = self.target / ".servo/runs" / run_id / "state.json"
        state_path.parent.mkdir(parents=True)
        for halt in ("interrupted", ""):
            for sess in ("", None, "ABSENT"):
                fields = {"backend": "copilot", "state_schema_version": 1,
                          "cumulative_credits_nano": 50_000_000_000,
                          "last_terminal_reason": halt}
                if sess != "ABSENT":
                    fields["current_session_id"] = sess
                with self.subTest(last_terminal_reason=halt, session=sess):
                    state_path.write_text(json.dumps(fields))
                    stdout = io.StringIO()
                    with contextlib.redirect_stdout(stdout), \
                            contextlib.redirect_stderr(io.StringIO()):
                        with patch.object(
                            loop, "_get_claude_version",
                            side_effect=AssertionError("probe"),
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
