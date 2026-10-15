"""035-02: installed overall authority across the bounded consumer inventory."""
import copy
import importlib.util
import io
import json
import os
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]


def module(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    obj = importlib.util.module_from_spec(spec)
    sys.modules[name] = obj
    spec.loader.exec_module(obj)
    return obj


fixtures = module("installed_consumer_fixtures", "skills/spec-oracle/test_required_gate.py")
loop_fixtures = module("loop_consumer_fixtures", "skills/agent-loop/test_loop.py")


class ConsumerTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.InstalledRequiredGateTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.target = self.fixture.target
        self.fixture.install_required()
        self.loop = module("consumer_loop", "skills/agent-loop/loop.py")
        self.heartbeat = module("consumer_heartbeat", "skills/heartbeat/heartbeat.py")
        self.bindir = self.target / "bin"
        loop_fixtures._mock_claude_constant(
            self.bindir, loop_fixtures._claude_json_payload(), self.target / "model-calls")
        self.env = {
            "PATH": str(self.bindir) + os.pathsep + os.environ["PATH"],
            "SERVO_READINESS_GATE": "0", "SERVO_MANAGED_SETTINGS_PATH": "",
            "THRESHOLD": "0",
        }

    def reader(self):
        return module("gate_consumer", "skills/quality-gate/gate_consumer.py")

    def run_loop(self, *extra, goal=False):
        if goal:
            return loop_fixtures._run_goal(
                self.target, "--prompt", "repair", "--allow-dirty", *extra,
                mock_bindir=self.bindir, extra_env=self.env)
        return loop_fixtures._run_loop(
            self.target, "--prompt", "repair", "--allow-dirty", *extra,
            mock_bindir=self.bindir, extra_env=self.env)

    def summary(self, proc):
        self.assertIn(proc.returncode, (0, 2), proc.stderr)
        return json.loads(proc.stdout.splitlines()[-1])

    def recorded(self, payload):
        path = self.target / ".servo/gate-runs" / payload["run_id"] / "gate.json"
        runtime = fixtures.load_runtime()
        return {"oracle": payload,
                "gate_ref": {"path": str(path), "hash": runtime.file_hash(path)}}

    def test_ac1_loop_history_checkpoint_resume_and_overall_authority(self):
        proc = self.run_loop("--max-iterations", "1")
        summary = self.summary(proc)
        self.assertEqual(summary["final_oracle_status"], "fail")
        self.assertEqual(summary["oracle"]["reason"], "required_constraints_failed")
        self.assertEqual(summary["oracle"]["composite"], 1.0)
        entry = summary["oracle_score_history"][-1]
        self.assertEqual(entry["oracle"], summary["oracle"])
        self.assertEqual(entry["gate_ref"], summary["gate_ref"])
        state_path = self.target / ".servo/runs" / summary["run_id"] / "state.json"
        state = json.loads(state_path.read_text())
        self.assertEqual(state["gate_ref"], summary["gate_ref"])
        component = next(c["result"] for c in summary["oracle"]["components"] if c["result"])
        self.assertEqual(json.loads(Path(component["path"]).read_text())["run_id"],
                         summary["oracle"]["run_id"])
        # Resume revalidates exact bytes before spending, even --resume-anyway.
        Path(component["path"]).write_text("{}")
        resumed = loop_fixtures._run_loop(
            self.target, "--resume", summary["run_id"], "--resume-anyway",
            "--max-iterations", "2", mock_bindir=self.bindir, extra_env=self.env)
        refused = self.summary(resumed)
        self.assertEqual(resumed.returncode, 2)
        self.assertEqual(refused["final_oracle_status"], "env_error")
        self.assertEqual((self.target / "model-calls").read_text().strip(), "1")

    def test_ac1_goal_disagreement_and_caps_keep_oracle_cause_separate(self):
        for subtype, terminal in (("success", "oracle_disagreement"),
                                  ("error_max_turns", "iteration_cap_reached"),
                                  ("error_max_budget_usd", "cost_ceiling_reached")):
            with self.subTest(subtype=subtype):
                loop_fixtures._mock_claude_goal(
                    self.bindir, loop_fixtures._goal_stream_jsonl(
                        assistant_text=loop_fixtures.GOAL_PASS_SENTINEL,
                        result_event=loop_fixtures._goal_result_event(subtype=subtype)))
                summary = self.summary(self.run_loop(goal=True))
                self.assertEqual(summary["terminal_reason"], terminal)
                self.assertEqual(summary["final_oracle_status"], "fail")
                self.assertEqual(summary["oracle_reason"], "required_constraints_failed")
                self.assertEqual(summary["oracle"]["required"]["failed"], ["assertion"])
                self.assertTrue(summary["gate_ref"]["hash"].startswith("sha256:"))

    def test_ac1_resume_does_not_trust_history_scalar_status(self):
        summary = self.summary(self.run_loop("--max-iterations", "1"))
        state_path = self.target / ".servo/runs" / summary["run_id"] / "state.json"
        state = json.loads(state_path.read_text())
        state["oracle_score_history"][-1]["status"] = "pass"
        state_path.write_text(json.dumps(state))
        resumed = loop_fixtures._run_loop(
            self.target, "--resume", summary["run_id"], "--resume-anyway",
            "--max-iterations", "1", mock_bindir=self.bindir, extra_env=self.env)
        report = self.summary(resumed)
        self.assertEqual(report["final_oracle_status"], "fail")
        self.assertEqual(report["oracle_score_history"][-1]["status"], "fail")
        self.assertEqual((self.target / "model-calls").read_text().strip(), "1")

    def test_ac1_refusal_halts_not_convergence_and_keeps_known_failure(self):
        self.fixture.plan["checks"].append({
            "id": "capture", "family": "unsupported", "required": True})
        self.fixture.write_plan()
        self.fixture.install_required()
        proc = self.run_loop("--max-iterations", "4", "--plateau-window", "1")
        summary = self.summary(proc)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(summary["iterations_completed"], 1)
        self.assertEqual(summary["terminal_reason"], "oracle_evaluation_refused")
        self.assertEqual(summary["oracle"]["required"]["failed"], ["assertion"])
        self.assertEqual(summary["oracle"]["required"]["unknown"], ["capture"])

    def test_ac2_high_flat_quality_plateau_is_not_pass(self):
        summary = self.summary(self.run_loop(
            "--max-iterations", "8", "--plateau-window", "2"))
        self.assertEqual(summary["terminal_reason"], "oracle_plateau")
        self.assertEqual(summary["final_oracle_status"], "fail")
        self.assertEqual(summary["oracle"]["required"]["failed"], ["assertion"])
        self.assertTrue(all(e["composite"] == 1.0 for e in summary["oracle_score_history"]))
        self.assertNotIn("oracle_pass", summary["terminal_reason"])

    def test_ac1_actual_pass_is_overall_and_carried_to_summary(self):
        (self.target / "subject").touch()
        proc = self.run_loop("--max-iterations", "3")
        summary = self.summary(proc)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(summary["terminal_reason"], "oracle_passed")
        self.assertEqual(summary["oracle"]["status"], "pass")
        self.assertEqual(summary["iterations_completed"], 1)
        self.assertEqual(self.reader().read(self.target, summary)["exit_code"], 0)

    def test_ac3_actual_installed_hook_veto_and_refusal_fail_open(self):
        proc = self.fixture.cli("oracle-hook/hook.py", "install", str(self.target))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        script = self.target / ".servo/hooks/meta-judge.sh"

        def hook():
            return subprocess.run(
                ["sh", str(script)], input="{}", text=True, capture_output=True,
                env={**os.environ, "CLAUDE_PROJECT_DIR": str(self.target), "THRESHOLD": "0"},
                timeout=30)

        result = hook()
        self.assertEqual(result.returncode, 0)
        block = json.loads(result.stdout)
        self.assertEqual(block["decision"], "block")
        self.assertIn("required_constraints_failed", block["reason"])
        self.assertIn("assertion", block["reason"])
        self.assertNotIn("raise the oracle score", block["reason"])
        self.assertIn("gate.json", block["reason"])
        # A published refusal can legitimately lack component refs.
        fragment = self.fixture.out / "oracle.sh.fragment"
        fragment.write_text(fragment.read_text() + "\n# honest drift\n")
        warning = json.loads(hook().stdout)
        self.assertNotIn("decision", warning)
        self.assertIn("required_evidence_unavailable", warning["systemMessage"])
        self.assertIn("not gating this turn", warning["systemMessage"])

    def test_ac3_custom_hook_not_replaced_and_migration_is_explicit(self):
        script = self.target / ".servo/hooks/meta-judge.sh"
        script.parent.mkdir(parents=True)
        script.write_text("# customized\n")
        result = self.fixture.cli("oracle-hook/hook.py", "install", str(self.target))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(script.read_text(), "# customized\n")
        self.assertIn("migration", (result.stdout + result.stderr).lower())

    def test_ac3_installed_hook_quotes_runtime_paths_with_spaces(self):
        hook = module("spaced_consumer_hook", "skills/oracle-hook/hook.py")
        runtime = self.target / "runtime's space/quality-gate"
        runtime.mkdir(parents=True)
        for name in ("gate.py", "required_runtime.py", "gate_consumer.py"):
            (runtime / name).write_bytes((ROOT / "skills/quality-gate" / name).read_bytes())
        with patch.object(hook, "_servo_gate_py", return_value=runtime / "gate.py"), \
                redirect_stdout(io.StringIO()):
            self.assertEqual(hook.cmd_install(self.target), 0)
        result = subprocess.run(
            ["sh", str(self.target / ".servo/hooks/meta-judge.sh")],
            input="{}", text=True, capture_output=True,
            env={**os.environ, "CLAUDE_PROJECT_DIR": str(self.target), "THRESHOLD": "0"},
            timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("required_constraints_failed", result.stdout)
        self.assertEqual(json.loads(result.stdout)["decision"], "block")

    def test_ac3_nonobject_gate_json_warns_without_blocking_or_attesting(self):
        self.assertEqual(
            self.fixture.cli("oracle-hook/hook.py", "install", str(self.target)).returncode, 0)
        stub = self.target / "nonobject-gate.py"
        stub.write_text('import os\nprint(os.environ["NONOBJECT_GATE_JSON"])\n')
        for payload in ([], None, "bad", 42, True):
            with self.subTest(payload=payload):
                result = subprocess.run(
                    ["sh", str(self.target / ".servo/hooks/meta-judge.sh")],
                    input="{}", text=True, capture_output=True,
                    env={**os.environ, "CLAUDE_PROJECT_DIR": str(self.target),
                         "SERVO_GATE_PY": str(stub), "NONOBJECT_GATE_JSON": json.dumps(payload)},
                    timeout=30)
                self.assertEqual(result.returncode, 0, result.stderr)
                warning = json.loads(result.stdout)
                self.assertNotIn("decision", warning)
                self.assertIn("required_evidence_unavailable", warning["systemMessage"])
                self.assertIn("not gating this turn", warning["systemMessage"])

    def test_ac3_installed_copilot_adapter_forwards_advice_not_autonomy(self):
        result = self.fixture.cli(
            "oracle-hook/hook.py", "install", str(self.target), "--host", "copilot")
        self.assertEqual(result.returncode, 0, result.stderr)
        adapter = self.target / ".servo/hooks/copilot_hook_adapter.py"
        script = self.target / ".servo/hooks/meta-judge.sh"
        output = subprocess.run(
            [sys.executable, str(adapter), "Stop", str(script)],
            input=json.dumps({"cwd": str(self.target), "stop_hook_active": False}),
            env={**os.environ, "THRESHOLD": "0"}, capture_output=True, text=True, timeout=30)
        self.assertEqual(output.returncode, 0)
        self.assertIn("required_constraints_failed", json.loads(output.stdout)["reason"])
        # Static advisory forwarding does not enable the unsupported native driver.
        refused = loop_fixtures._run_loop(
            self.target, "--host", "copilot", "--prompt", "repair",
            mock_bindir=self.bindir, extra_env=self.env)
        self.assertEqual(refused.returncode, 2)
        self.assertEqual(self.summary(refused)["terminal_reason"], "native_capability_unavailable")

    def test_ac4_planner_references_policy_config_source_not_build(self):
        planner = module("consumer_plan", "skills/execution-planner/execution_plan.py")
        oracle = planner._load_oracle(self.target)
        self.assertIn("required_policy", oracle)
        model = planner._load_evaluation_model(self.target, self.fixture.spec, "demo")
        self.assertEqual(model["required_binding"]["source_identity"],
                         self.fixture.plan.get("source_identity") or {
                             "path": "spec/spec.md", "hash": self.fixture.plan["source_hash"]})
        self.assertIn("gate-runs/<run_id>/gate.json", oracle["completion_authority"])
        self.assertNotIn("build_identity", model["required_binding"])

    def test_ac4_planner_malformed_policy_pin_uses_structured_refusal(self):
        planner = module("malformed_consumer_plan", "skills/execution-planner/execution_plan.py")
        manifest = self.target / ".servo/install.json"
        original = json.loads(manifest.read_text())
        for pin in (None, [], {}, {"schema_version": 999, "hash": "sha256:" + "0" * 64},
                    {"schema_version": True, "hash": "sha256:" + "0" * 64},
                    {"schema_version": 1, "hash": "missing"}):
            with self.subTest(pin=pin):
                manifest.write_text(json.dumps({**original, "required_policy": pin}))
                with self.assertRaises(planner.EnvError) as refusal:
                    planner._load_oracle(self.target)
                self.assertEqual(refusal.exception.reason, "manifest_malformed")
        manifest.write_text(json.dumps(original))

    def test_ac4_heartbeat_overall_quality_fail_not_component_pass_or_scalar_summary(self):
        (self.target / "subject").touch()
        proc, payload = self.fixture.gate(THRESHOLD="1.1")
        self.assertEqual(proc.returncode, 1)
        record = self.recorded(payload)
        summary = {**record, "final_oracle_status": "pass", "run_id": "loop",
                   "terminal_reason": "iteration_cap_reached", "oracle_composite": 1.0}
        outcome = self.heartbeat._outcome_from_summary(summary, target=self.target)
        self.assertEqual(outcome["oracle_status"], "fail")
        self.assertEqual(outcome["oracle_reason"], "quality_below_threshold")
        self.assertEqual(outcome["terminal_reason"], "iteration_cap_reached")
        self.assertEqual(outcome["oracle"], payload)
        self.assertEqual(outcome["gate_ref"], record["gate_ref"])
        summary.pop("gate_ref")
        refused = self.heartbeat._outcome_from_summary(summary, target=self.target)
        self.assertEqual(refused["oracle_status"], "env_error")

    def test_ac4_enabled_dispatch_cannot_trust_unbound_scalar_summary(self):
        outcome = self.heartbeat._outcome_from_summary({
            "schema_version": 1, "final_oracle_status": "pass", "oracle_composite": 1.0,
        }, target=self.target)
        self.assertEqual(outcome["oracle_status"], "env_error")
        self.assertIsNone(outcome["oracle_composite"])
        outcome = self.heartbeat._outcome_from_summary({
            "oracle": {"schema_version": 1, "exit_code": 0, "status": "pass",
                       "composite": 1.0},
            "final_oracle_status": "pass",
        }, target=self.target)
        self.assertEqual(outcome["oracle_status"], "env_error")

    def test_ac5_report_missing_overall_payload_cannot_keep_passed(self):
        (self.target / "subject").touch()
        _, payload = self.fixture.gate()
        outcome = self.heartbeat._outcome_from_summary({
            **self.recorded(payload), "final_oracle_status": "pass",
        }, target=self.target)
        outcome.pop("oracle")
        record = {
            "schema_version": self.heartbeat.SCHEMA_VERSION,
            "status": "passed", "outcome": outcome,
        }
        inbox = self.target / ".servo/triage/inbox.jsonl"
        inbox.parent.mkdir()
        inbox.write_text(json.dumps(record) + "\n")
        records, cause = self.heartbeat._read_inbox_for_status(inbox)
        self.assertIsNone(cause)
        self.assertEqual(records[0]["status"], "tried")
        self.assertEqual(records[0]["outcome"]["oracle_status"], "env_error")
        self.assertIsNone(records[0]["outcome"]["oracle_composite"])
        self.assertEqual(json.loads(inbox.read_text()), record)

    def test_ac5_legacy_checkpoint_cannot_attest_new_enabled_policy_without_evaluation(self):
        (self.target / "subject").touch()
        summary = self.summary(self.run_loop("--max-iterations", "1"))
        state_path = self.target / ".servo/runs" / summary["run_id"] / "state.json"
        state = json.loads(state_path.read_text())
        for key in ("oracle", "gate_ref", "oracle_reason", "final_oracle_status"):
            state.pop(key, None)
            state["oracle_score_history"][-1].pop(key, None)
        state["last_oracle_json"] = {
            "schema_version": 1, "status": "pass", "exit_code": 0,
            "composite": 1.0, "threshold": 0,
        }
        state_path.write_text(json.dumps(state))
        result = loop_fixtures._run_loop(
            self.target, "--resume", summary["run_id"], "--resume-anyway",
            "--max-iterations", "1", mock_bindir=self.bindir, extra_env=self.env)
        report = self.summary(result)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(report["final_oracle_status"], "env_error")
        self.assertEqual((self.target / "model-calls").read_text().strip(), "1")

    def test_ac4_report_readback_preserves_dispatch_time_and_cost(self):
        _, payload = self.fixture.gate()
        record = {
            "schema_version": self.heartbeat.SCHEMA_VERSION,
            "status": "tried", "outcome": {
                **self.recorded(payload), "oracle_status": "fail", "cost_usd": 0.25,
                "dispatched_at": "2026-01-01T00:00:00+00:00",
            },
        }
        inbox = self.target / ".servo/triage/inbox.jsonl"
        inbox.parent.mkdir()
        inbox.write_text(json.dumps(record) + "\n")
        records, cause = self.heartbeat._read_inbox_for_status(inbox)
        self.assertIsNone(cause)
        self.assertEqual(records[0]["outcome"]["dispatched_at"], record["outcome"]["dispatched_at"])
        self.assertEqual(records[0]["outcome"]["cost_usd"], 0.25)
        self.assertEqual(json.loads(inbox.read_text()), record)  # read-only

    def test_ac4_final_unavailability_survives_prior_evidence_and_report_rereads(self):
        for interrupted in (False, True):
            with self.subTest(interrupted=interrupted):
                invoke = self.loop._invoke_gate
                calls = []
                stopped = [False]

                def gate(target, invoke=invoke, calls=calls,
                         stopped=stopped, interrupted=interrupted):
                    calls.append(target)
                    if len(calls) == 1:
                        return invoke(target)
                    stopped[0] = interrupted
                    return None

                def was_stopped(stopped=stopped):
                    return stopped[0]

                output = io.StringIO()
                with patch.dict(os.environ, self.env), redirect_stdout(output), \
                        patch.object(self.loop, "_install_signal_handlers"), \
                        patch.object(self.loop, "_was_interrupted", side_effect=was_stopped), \
                        patch.object(self.loop, "_invoke_gate", side_effect=gate):
                    self.loop.run_loop(
                        self.target, prompt="repair", max_iterations=2,
                        cost_ceiling=1, context_fill_threshold=0, plateau_window=0,
                        allow_dirty=True)
                summary = json.loads(output.getvalue().splitlines()[-1])
                status = "unknown_interrupted" if interrupted else "env_error"
                self.assertEqual(summary["final_oracle_status"], status)
                self.assertEqual(summary["oracle"]["status"], "fail")
                state_path = self.target / ".servo/runs" / summary["run_id"] / "state.json"
                self.assertEqual(json.loads(state_path.read_text())["final_oracle_status"], status)
                if interrupted:
                    resumed = loop_fixtures._run_loop(
                        self.target, "--resume", summary["run_id"], "--resume-anyway",
                        "--max-iterations", "2", mock_bindir=self.bindir, extra_env=self.env)
                    summary = self.summary(resumed)
                    self.assertEqual(resumed.returncode, 2)
                    self.assertEqual(summary["final_oracle_status"], status)
                    self.assertEqual(summary["oracle"]["status"], "fail")
                    (self.target / "subject").touch()
                    recovered = loop_fixtures._run_loop(
                        self.target, "--resume", summary["run_id"], "--resume-anyway",
                        "--max-iterations", "3", mock_bindir=self.bindir, extra_env=self.env)
                    report = self.summary(recovered)
                    self.assertEqual(recovered.returncode, 0)
                    self.assertEqual(report["final_oracle_status"], "pass")
                    self.assertNotEqual(report["oracle"]["run_id"], summary["oracle"]["run_id"])
                    (self.target / "subject").unlink()
                outcome = self.heartbeat._outcome_from_summary(summary, target=self.target)
                self.assertEqual(outcome["oracle_status"], status)
                self.assertIsNone(outcome["oracle_composite"])
                self.assertEqual(outcome["oracle"], summary["oracle"])
                self.assertEqual(outcome["gate_ref"], summary["gate_ref"])
                inbox = self.target / ".servo/triage/inbox.jsonl"
                inbox.parent.mkdir(exist_ok=True)
                record = {
                    "schema_version": self.heartbeat.SCHEMA_VERSION,
                    "status": "tried", "outcome": outcome,
                }
                inbox.write_text(json.dumps(record) + "\n")
                for _ in range(2):
                    records, cause = self.heartbeat._read_inbox_for_status(inbox)
                    self.assertIsNone(cause)
                    self.assertEqual(records[0]["outcome"]["oracle_status"], status)
                    self.assertIsNone(records[0]["outcome"]["oracle_composite"])
                    self.assertEqual(json.loads(inbox.read_text()), record)

    def test_ac1_model_error_or_bad_verdict_after_edits_leaves_evaluation_unavailable(self):
        for bad_verdict in (False, True):
            with self.subTest(bad_verdict=bad_verdict):
                (self.target / "subject").unlink(missing_ok=True)
                calls = []
                payload = json.loads(loop_fixtures._claude_json_payload())

                def model(*args, calls=calls, payload=payload, bad_verdict=bad_verdict, **kwargs):
                    calls.append(args)
                    if len(calls) == 1:
                        return payload, None
                    (self.target / "subject").touch()
                    return (payload, None) if bad_verdict else (None, "model invocation failed")

                verdicts = ([(None, None), (None, "malformed verdict")]
                            if bad_verdict else [(None, None)])
                output = io.StringIO()
                with patch.dict(os.environ, self.env), redirect_stdout(output), \
                        patch.object(self.loop, "_install_signal_handlers"), \
                        patch.object(self.loop, "_was_interrupted", return_value=False), \
                        patch.object(self.loop, "_invoke_claude", side_effect=model), \
                        patch.object(self.loop, "_parse_verdict_block", side_effect=verdicts):
                    rc = self.loop.run_loop(
                        self.target, prompt="repair", max_iterations=2,
                        cost_ceiling=1, context_fill_threshold=0, plateau_window=0,
                        allow_dirty=True)
                summary = json.loads(output.getvalue().splitlines()[-1])
                self.assertEqual(rc, 2)
                self.assertEqual(summary["final_oracle_status"], "env_error")
                self.assertEqual(summary["oracle"]["status"], "fail")
                self.assertEqual(summary["terminal_reason"],
                                 "verdict_schema_mismatch" if bad_verdict
                                 else "claude_invocation_failed")
                outcome = self.heartbeat._outcome_from_summary(summary, target=self.target)
                self.assertEqual(outcome["oracle_status"], "env_error")
                self.assertIsNone(outcome["oracle_composite"])
                self.assertEqual((self.target / "calls").read_text().count("x"),
                                 2 if bad_verdict else 1)

    def test_ac4_verification_refusal_retains_published_evidence(self):
        worktree = self.target / ".servo/dispatch/fixture"

        def provision(source, destination):
            self.heartbeat._provision_oracle_original(source, destination)
            fragment = destination / "spec/oracle/demo/oracle.sh.fragment"
            fragment.write_text(fragment.read_text() + "\n# drift\n")

        self.heartbeat._provision_oracle_original = self.heartbeat._provision_oracle
        with patch.object(self.heartbeat, "_is_git_work_tree", return_value=True), \
                patch.object(self.heartbeat, "_remove_worktree_if_present"), \
                patch.object(self.heartbeat, "_create_worktree",
                             side_effect=lambda *a: (worktree.mkdir(parents=True) or True, "")), \
                patch.object(self.heartbeat, "_provision_oracle", side_effect=provision), \
                patch.object(self.heartbeat, "_run_loop", side_effect=AssertionError("model ran")):
            outcome, _ = self.heartbeat._dispatch_one(
                self.target, {"finding_id": "fixture"}, worktree.parent,
                cost_ceiling=1, max_iterations=1)
        self.assertEqual(outcome["oracle_status"], "env_error")
        self.assertEqual(outcome["oracle"]["reason"], "required_evidence_unavailable")
        self.assertIn("fragment", str(outcome["oracle"]["required"]))
        self.assertTrue(Path(outcome["gate_ref"]["path"]).is_file())

    def test_ac4_preflight_refusal_surfaces_carrier_without_dispatch_or_inbox_edits(self):
        self.fixture.plan["checks"].append({
            "id": "capture", "family": "unsupported", "required": True})
        self.fixture.write_plan()
        self.fixture.install_required()
        inbox = self.target / ".servo/triage/inbox.jsonl"
        inbox.parent.mkdir()
        original = json.dumps({
            "schema_version": self.heartbeat.SCHEMA_VERSION, "finding_id": "refused",
            "status": "open", "actionable": True,
        }) + "\n"
        inbox.write_text(original)
        output = io.StringIO()
        with redirect_stdout(output), patch.object(
                self.heartbeat, "_dispatch_one", side_effect=AssertionError("dispatched")):
            rc = self.heartbeat.run_dispatch(self.target)
        self.assertEqual(rc, 2)
        record = json.loads(output.getvalue())["oracle_preflight"]
        self.assertEqual(record["oracle"]["required"]["failed"], ["assertion"])
        self.assertEqual(record["oracle"]["required"]["unknown"], ["capture"])
        self.assertTrue(Path(record["gate_ref"]["path"]).is_file())
        self.assertEqual(inbox.read_text(), original)

    def test_ac4_heartbeat_provision_preserves_policy_without_old_runs(self):
        self.fixture.gate()
        worktree = self.target / "isolated"
        worktree.mkdir()
        self.heartbeat._provision_oracle(self.target, worktree)
        self.assertFalse((worktree / ".servo/gate-runs").exists())
        self.assertFalse((worktree / "spec/oracle/demo/runs").exists())
        self.assertTrue((worktree / "spec/oracle/demo/checks.json").is_file())
        result = self.heartbeat._run_gate_json(worktree)
        self.assertEqual(result["status"], "fail", result)
        self.assertEqual(result["oracle"]["required"]["failed"], ["assertion"])
        self.assertEqual(Path(result["gate_ref"]["path"]).parents[3], worktree.resolve())

    def test_ac4_real_dispatch_quality_failure_cannot_be_passed(self):
        (self.target / "subject").touch()
        loop_fixtures._git_init(self.target)
        loop_fixtures._git_commit_all(self.target)
        inbox = self.target / ".servo/triage/inbox.jsonl"
        inbox.parent.mkdir()
        inbox.write_text(json.dumps({
            "schema_version": self.heartbeat.SCHEMA_VERSION, "finding_id": "quality",
            "status": "open", "actionable": True, "source": "issue", "title": "repair",
            "attempts": 0, "outcome": None,
        }) + "\n")
        # Real preflight, worktree provision, verification, loop and final report;
        # only the model executable is a deterministic fixture.
        with patch.dict(os.environ, {**self.env, "THRESHOLD": "1.1"}), \
                redirect_stdout(io.StringIO()):
            rc = self.heartbeat.run_dispatch(
                self.target, cost_ceiling=1, max_iterations=1, max_candidates=1)
        self.assertEqual(rc, 0)
        record = json.loads(inbox.read_text())
        self.assertEqual(record["status"], "tried")
        self.assertEqual(record["outcome"]["oracle_status"], "fail")
        self.assertEqual(record["outcome"]["oracle_reason"], "quality_below_threshold")
        self.assertEqual(record["outcome"]["oracle"]["required"]["status"], "pass")
        records, cause = self.heartbeat._read_inbox_for_status(inbox)
        self.assertIsNone(cause)
        self.assertEqual(records[0]["outcome"]["oracle_status"], "fail")

    def test_ac5_bindings_mutation_missing_unknown_stale_replay_and_v1(self):
        reader = self.reader()
        (self.target / "subject").touch()
        with patch.dict(os.environ, {}, clear=False):
            run_id, env = reader.request(self.target)
            proc = self.fixture.cli("quality-gate/gate.py", str(self.target), "--json", env={
                **os.environ, **env})
        payload = json.loads(proc.stdout)
        accepted = reader.accept(self.target, payload, proc.returncode, run_id)
        self.assertEqual(accepted["status"], "pass")
        self.assertEqual(reader.read(self.target, accepted)["status"], "pass")
        self.assertEqual(reader.read(self.target, accepted)["status"], "pass")  # report rereads
        self.assertEqual(reader.accept(self.target, payload, 0, run_id)["exit_code"], 2)
        self.assertEqual(reader.accept(self.target, payload, 0, "stale")["exit_code"], 2)
        self.assertEqual(reader.accept(self.target, payload, 1, run_id)["exit_code"], 2)
        for mutate in (
            lambda r: r.pop("gate_ref"),
            lambda r: r["gate_ref"].update(hash="sha256:wrong"),
            lambda r: r["oracle"].update(schema_version=999),
            lambda r: r["oracle"].update(run_id="stale"),
            lambda r: r["oracle"].update(policy_hash="sha256:wrong"),
        ):
            record = copy.deepcopy(accepted)
            mutate(record)
            self.assertEqual(reader.read(self.target, record)["exit_code"], 2)
        component = next(c["result"] for c in payload["components"] if c["result"])
        path = Path(component["path"])
        path.write_bytes(path.read_bytes() + b"\n")
        self.assertEqual(reader.read(self.target, accepted)["exit_code"], 2)
        legacy = {"schema_version": 1, "exit_code": 0, "status": "pass", "composite": 0.9}
        # No policy is needed for a legacy recorded result; don't upgrade its schema.
        self.assertEqual(reader.read(self.target, {"oracle": legacy}), legacy)

    def test_ac5_published_refusal_missing_refs_is_preserved_not_promoted(self):
        fragment = self.fixture.out / "oracle.sh.fragment"
        fragment.write_text(fragment.read_text() + "\n# drift\n")
        _, payload = self.fixture.gate()
        reader = self.reader()
        record = self.recorded(payload)
        read = reader.read(self.target, record)
        self.assertEqual(read["exit_code"], 2)
        self.assertEqual(read["oracle"], payload)
        self.assertIsNone(read["composite"])
        self.assertIn("fragment", str(read["oracle"]["required"]["items"]))

    def test_ac5_legacy_unversioned_no_policy_gateway_is_unchanged(self):
        # Existing no-policy gateway adapters can emit the historical minimal
        # scalar shape. Explicit unknown versions must still refuse.
        target = self.target / "legacy"
        target.mkdir()
        reader = self.reader()
        scalar = {"exit_code": 1}
        self.assertEqual(reader.accept(target, scalar, 1, "unused"), scalar)
        self.assertEqual(reader.accept(target, {**scalar, "schema_version": 99},
                                       1, "unused")["exit_code"], 2)

    def test_ac5_live_json_rejects_ambiguous_keys_and_nonfinite_numbers(self):
        reader = self.reader()
        for text in ('{"schema_version":2,"schema_version":1}', '{"composite":NaN}'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                reader.parse(text)

    def test_ac5_refused_downgrade_cannot_promote_on_readback(self):
        reader = self.reader()
        legacy = {"schema_version": 1, "exit_code": 0, "status": "pass", "composite": 1.0}
        refused = reader.accept(self.target, legacy, 0, "unused")
        self.assertEqual(refused["exit_code"], 2)
        self.assertEqual(reader.read(self.target, refused)["exit_code"], 2)

    def test_ac5_malformed_record_is_actionable_refusal_not_reader_crash(self):
        reader = self.reader()
        for record in ([], {"oracle": ["bad"]}, {"oracle": {
                "schema_version": 2, "exit_code": 0, "status": "pass", "required": ["bad"]},
                "gate_ref": ["bad"]}):
            with self.subTest(record=record):
                result = reader.read(self.target, record)
                self.assertEqual(result["exit_code"], 2)
                self.assertIn("unavailable", reader.guidance(result))
                self.assertEqual(reader.record_target(result, self.target), self.target)

    def test_ac5_generated_hosts_and_goal_vendor_use_same_v2_reader(self):
        for relative in ("hosts/claude", "hosts/codex/plugins/servo", "hosts/copilot/.github"):
            with self.subTest(host=relative):
                package = ROOT / relative
                reader = module(
                    "generated_consumer", package / "skills/quality-gate/gate_consumer.py")
                run_id, env = reader.request(self.target)
                proc = subprocess.run(
                    [sys.executable, str(package / "skills/quality-gate/gate.py"),
                     str(self.target), "--json"],
                    env={**os.environ, **env, "THRESHOLD": "0"}, text=True,
                    capture_output=True, timeout=30)
                accepted = reader.accept(
                    self.target, json.loads(proc.stdout), proc.returncode, run_id)
                self.assertEqual(accepted["status"], "fail", accepted)
                self.assertEqual(reader.read(self.target, accepted)["status"], "fail")
        vendored, error = self.loop._ensure_vendored_gate(self.target)
        self.assertIsNone(error)
        path = vendored.with_name("gate_consumer.py")
        source = ROOT / "skills/quality-gate/gate_consumer.py"
        self.assertEqual(path.read_bytes(), source.read_bytes())
        reader = module("vendored_consumer", path)
        self.assertEqual(reader.parse('{"schema_version":2}')["schema_version"], 2)

    def test_ac5_current_installed_driver_drift_invalidates_readback(self):
        (self.target / "subject").touch()
        _, payload = self.fixture.gate()
        record = self.recorded(payload)
        self.assertEqual(self.reader().read(self.target, record)["exit_code"], 0)
        path = self.target / "oracle.sh"
        path.write_text(path.read_text() + "\n# driver drift\n")
        self.assertEqual(self.reader().read(self.target, record)["exit_code"], 2)

    def test_ac5_current_config_body_drift_refuses_without_reexecution(self):
        (self.target / "subject").touch()
        _, payload = self.fixture.gate()
        record = self.recorded(payload)
        path = self.fixture.out / "checks.json"
        plan = json.loads(path.read_text())
        plan["checks"][0]["command"] = [sys.executable, "-c", "raise SystemExit(0)"]
        path.write_text(json.dumps(plan))
        self.assertEqual(self.reader().read(self.target, record)["exit_code"], 2)
        self.assertEqual((self.target / "calls").read_text(), "x")
    def test_ac6_real_supported_final_triage_human_json_correction_evidence(self):
        summary = self.summary(self.run_loop("--max-iterations", "1"))
        outcome = self.heartbeat._outcome_from_summary(summary, target=self.target)
        self.assertEqual(outcome["oracle_status"], "fail")
        record = {
            "schema_version": self.heartbeat.SCHEMA_VERSION,
            "finding_id": "fixture", "title": "required assertion", "source": "issue",
            "status": "tried", "actionable": True, "outcome": outcome,
        }
        path = self.target / ".servo/triage/inbox.jsonl"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(record) + "\n")
        for as_json in (False, True):
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(self.heartbeat.run_status(self.target, as_json=as_json), 0)
            text = output.getvalue()
            self.assertIn("required_constraints_failed", text)
            self.assertIn("assertion", text)
            self.assertIn(summary["gate_ref"]["path"], text)
            if as_json:
                self.assertEqual(json.loads(text)["outcomes"][0]["outcome"]["oracle"],
                                 summary["oracle"])
            else:
                self.assertIn("repair", text.lower())
