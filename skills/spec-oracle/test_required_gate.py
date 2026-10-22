"""Installed-source required-policy contract; fixtures also serve as examples."""
import hashlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_runtime():
    spec = importlib.util.spec_from_file_location(
        "required_contract", ROOT / "skills/quality-gate/required_runtime.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class InstalledRequiredGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.target = Path(self.tmp.name)
        self.runtime = getattr(self, "package", ROOT)
        self.cli("scaffold-init/scaffold.py", str(self.target))
        oracle = self.target / "oracle.sh"
        text = oracle.read_text().replace(
            "COMPONENTS=(\n", 'COMPONENTS=(\n  "baseline:1"\n')
        text = text.replace('weighted_sum="0"', """# SEED:start baseline
score_baseline() {
  python3 -c "from pathlib import Path; p=Path('quality-calls'); p.open('a').write('x'); print(1.0)"
}
# SEED:end baseline

weighted_sum="0" """.rstrip())
        oracle.write_text(text)
        self.spec = self.target / "spec"
        self.out = self.spec / "oracle" / "demo"
        self.out.mkdir(parents=True)
        source = self.spec / "spec.md"
        source.write_text("Required assertion\n")
        self.plan = {
            "schema_version": 1, "spec_id": "demo",
            "source_spec_path": "spec/spec.md",
            "source_hash": "sha256:" + hashlib.sha256(source.read_bytes()).hexdigest(),
            "required_policy": {"schema_version": 1, "enabled": True},
            "checks": [{
                "id": "assertion", "family": "command", "required": True,
                "command": [sys.executable, "-c",
                            "from pathlib import Path; "
                            "p=Path('calls'); "
                            "p.write_text(p.read_text()+'x' if p.exists() else 'x'); "
                            "raise SystemExit(0 if Path('subject').exists() else 1)"],
                "evaluator_artifacts": [],
            }], "residual_judgment": [],
        }
        self.write_plan()

    def cli(self, helper, *args, env=None):
        return subprocess.run(
            [sys.executable, str(self.runtime / "skills" / helper), *args],
            capture_output=True, text=True,
            env={**(os.environ if env is None else env),
                 "XDG_STATE_HOME": str(self.target / "state")}, timeout=30)

    def write_plan(self):
        (self.out / "checks.json").write_text(json.dumps(self.plan))

    def overlay(self, operation, *extra):
        return self.cli("spec-oracle/oracle_overlay.py", operation,
                        str(self.target), str(self.spec), "demo", *extra)

    def install_required(self):
        for operation in ("generate", "approve"):
            result = self.overlay(operation)
            self.assertEqual(result.returncode, 0, result.stderr)
        result = self.overlay("install", "--enable-required", "--weight", "0")
        self.assertEqual(result.returncode, 0, result.stderr)

    def gate(self, **overrides):
        result = self.cli("quality-gate/gate.py", str(self.target), "--json",
                          env={**os.environ, **overrides})
        return result, json.loads(result.stdout)

    def test_ac2_installed_contradiction_veto_at_high_quality_and_zero_threshold(self):
        self.install_required()
        for threshold in ("0.5", "0"):
            result, payload = self.gate(THRESHOLD=threshold)
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertEqual(payload["schema_version"], 2)
            self.assertGreaterEqual(payload["composite"], 0.99)
            self.assertEqual(payload["reason"], "required_constraints_failed")
            self.assertEqual(payload["required"]["failed"], ["assertion"])
        self.assertEqual((self.target / "calls").read_text(), "xx")
        self.assertEqual((self.target / "quality-calls").read_text(), "xx")
        direct = subprocess.run([str(self.target / "oracle.sh")], cwd=self.target,
                                env={**os.environ, "THRESHOLD": "0"},
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(direct.returncode, 1, direct.stderr)
        self.assertIn("composite=1.0 threshold=0.0", direct.stdout)
        self.assertEqual((self.target / "calls").read_text(), "xxx")

    def test_ac1_approval_install_and_preserved_artifact(self):
        self.assertEqual(self.overlay("generate").returncode, 0)
        refused = self.overlay("install", "--enable-required")
        self.assertEqual(refused.returncode, 2)
        self.assertNotIn("approved_required_binding",
                         json.loads((self.out / "checks.json").read_text()))
        self.install_required()
        (self.target / "subject").touch()
        result, payload = self.gate()
        self.assertEqual(result.returncode, 0, payload)
        path = self.target / ".servo/gate-runs" / payload["run_id"] / "gate.json"
        self.assertEqual(json.loads(path.read_text()), payload)
        reference = next(c["result"] for c in payload["components"] if c["result"])
        self.assertEqual(reference["hash"],
                         "sha256:" + hashlib.sha256(
                             Path(reference["path"]).read_bytes()).hexdigest())
        record = json.loads(Path(reference["path"]).read_text())
        self.assertEqual(record["kind"], "required_component_result")
        self.assertEqual(record["required"]["ids"], ["assertion"])
        self.assertEqual(record["run_id"], payload["run_id"])
        ledger = [json.loads(line) for line in (self.out / "ledger.jsonl").read_text().splitlines()]
        self.assertEqual(ledger[-1]["run_id"], payload["run_id"])

    def test_ac3_fail_plus_unknown_retains_failure_and_observed_absence(self):
        self.plan["checks"].append({
            "id": "capture", "family": "command", "required": True,
            "command": [sys.executable, "-c", "import time; time.sleep(0.1)"],
            "timeout": 0.01, "evaluator_artifacts": []})
        self.write_plan()
        self.install_required()
        result, payload = self.gate()
        self.assertEqual(result.returncode, 2)
        self.assertEqual(payload["required"]["failed"], ["assertion"])
        self.assertEqual(payload["required"]["unknown"], ["capture"])
        self.assertIn("timeout", str(payload["required"]["items"]))

    def test_ac3_required_residual_and_unknown_family_are_unknown(self):
        for family in ("residual_judgment", "not-a-family", "file_presence"):
            with self.subTest(family=family):
                self.plan["checks"][0].update(family=family, path="subject")
                self.write_plan()
                self.install_required()
                result, payload = self.gate()
                self.assertEqual(result.returncode, 2)
                self.assertEqual(payload["required"]["status"], "unknown")

    def test_ac3_policy_and_executable_drift_refuse_before_assertion(self):
        self.install_required()
        path = self.out / "checks.json"
        approved = path.read_text()
        mutations = [
            lambda p: p.update(approval_status="draft"),
            lambda p: p["checks"][0].update(expected=1),
            lambda p: p["checks"][0].update(required=False),
            lambda p: p["approved_required_binding"].update(component="wrong"),
            lambda p: p.update(source_hash="sha256:wrong"),
        ]
        for mutate in mutations:
            plan = json.loads(approved)
            mutate(plan)
            path.write_text(json.dumps(plan))
            result, payload = self.gate()
            self.assertEqual(result.returncode, 2, payload)
            self.assertFalse((self.target / "calls").exists())
        path.write_text(approved)
        # Lifecycle-only source bytes are not current-source provenance.
        (self.spec / "spec.md").write_text("status: IN_PROGRESS\nRequired assertion\n")
        self.assertEqual(self.gate()[0].returncode, 1)

    def test_ac3_script_closure_is_explicit_and_frozen_not_subject(self):
        script = self.target / "assert.py"
        script.write_text("from pathlib import Path\n"
                          "raise SystemExit(0 if Path('subject').exists() else 1)\n")
        self.plan["checks"][0]["command"] = [sys.executable, "assert.py"]
        self.plan["checks"][0]["evaluator_artifacts"] = ["assert.py"]
        self.write_plan()
        self.install_required()
        self.assertEqual(self.gate()[0].returncode, 1)
        (self.target / "subject").touch()
        self.assertEqual(self.gate()[0].returncode, 0)
        script.write_text("raise SystemExit(0)\n")
        result, payload = self.gate()
        self.assertEqual(result.returncode, 2, payload)
        self.assertIn("modified", str(payload["required"]))

    def test_ac3_pinned_input_drift_retains_exact_inventory_and_original_cause(self):
        source = self.target / "approved-input.json"
        original = b'{"approved":true}\n'
        source.write_bytes(original)
        self.plan["checks"][0]["evaluator_artifacts"] = ["approved-input.json"]
        self.plan["checks"].append({
            **self.plan["checks"][0], "id": "second",
        })
        self.write_plan()
        for operation, extra in (("generate", ["--vendor-engine"]), ("approve", []),
                                 ("install", ["--vendor-engine", "--enable-required"])):
            result = self.overlay(operation, *extra)
            self.assertEqual(result.returncode, 0, result.stderr)
        entry = json.loads((self.out / "checks.json").read_text())["approved_required_binding"]
        (self.target / "subject").touch()
        pins = [{"path": "approved-input.json"}, entry["evaluator"], entry["required_runtime"]]
        for pin in pins:
            with self.subTest(pin=pin["path"]):
                path = self.target / pin["path"]
                self.assertTrue(path.resolve().is_relative_to(self.target.resolve()))
                saved = path.read_bytes()
                calls = self.target / "calls"
                before = calls.read_bytes() if calls.exists() else None
                try:
                    path.write_bytes(saved + b"\n")
                    result, payload = self.gate(THRESHOLD="0")
                finally:
                    path.write_bytes(saved)
                self.assertEqual(result.returncode, 2, payload)
                self.assertEqual(payload["required"]["ids"], ["assertion", "second"])
                self.assertEqual(payload["required"]["counts"],
                                 {"pass": 0, "fail": 0, "unknown": 2})
                self.assertEqual(payload["required"]["unknown"], ["assertion", "second"])
                self.assertTrue(all(
                    item["reason"] == "approved artifact modified: " + pin["path"]
                    for item in payload["required"]["items"]
                ), payload)
                self.assertEqual(calls.read_bytes() if calls.exists() else None, before)
                component = next(c for c in payload["components"]
                                 if c["component"] == "spec_oracle_demo")
                self.assertIsNone(component["result"])
                result, restored = self.gate(THRESHOLD="0")
                self.assertEqual(result.returncode, 0, restored)
                self.assertEqual(restored["required"]["passed"], ["assertion", "second"])

    def test_ac3_current_pins_do_not_accept_missing_or_malformed_component_results(self):
        self.install_required()
        (self.target / "subject").touch()
        runtime = load_runtime()
        for mutation in ("missing-reference", "missing-file", "malformed-record"):
            with self.subTest(mutation=mutation):
                def intercepted(oracle, target, timeout, env, mutation=mutation):
                    result = subprocess.run([str(oracle)], cwd=target, env=env,
                                            capture_output=True, text=True, timeout=30)
                    path = Path(env["SERVO_GATE_RESULT_DIR"]) / "oracle-result.json"
                    payload = runtime.load(path)
                    component = next(c for c in payload["components"]
                                     if c["component"] == "spec_oracle_demo")
                    if mutation == "missing-reference":
                        component["result"] = None
                        path.write_bytes(runtime.canonical(payload))
                    elif mutation == "missing-file":
                        Path(component["result"]["path"]).unlink()
                    else:
                        Path(component["result"]["path"]).write_text('{"schema_version":')
                    return result.stdout, result.stderr, result.returncode, False

                output = io.StringIO()
                with redirect_stdout(output):
                    code = runtime.run_gate(self.target, intercepted, 30, True, False)
                payload = json.loads(output.getvalue())
                self.assertEqual(code, 2, payload)
                self.assertIn("assertion", payload["required"]["unknown"])
                self.assertEqual(payload["required"]["passed"], [])
                policy, _ = runtime.installed_policy(self.target)
                entry = policy["components"][0]
                runtime.check_pins([entry["evaluator"], entry["required_runtime"]]
                                   + entry["evaluator_artifacts"], self.target)

    def test_ac3_working_directory_pins_the_executed_assertion(self):
        directory = self.target / "sub"
        directory.mkdir()
        script = directory / "assert.py"
        script.write_text("raise SystemExit(1)\n")
        (self.target / "assert.py").write_text("raise SystemExit(0)\n")
        self.plan["checks"][0].update(
            command=[sys.executable, "assert.py"], working_directory="sub",
            evaluator_artifacts=["assert.py"])
        self.write_plan()
        self.assertEqual(self.overlay("generate").returncode, 0)
        self.assertEqual(self.overlay("approve").returncode, 2)
        self.plan["checks"][0]["evaluator_artifacts"] = ["sub/assert.py"]
        self.write_plan()
        self.install_required()
        self.assertEqual(self.gate()[0].returncode, 1)
        script.write_text("raise SystemExit(0)\n")
        result, payload = self.gate()
        self.assertEqual(result.returncode, 2, payload)
        self.assertIn("sub/assert.py", str(payload["required"]))

    def test_ac3_relative_path_executable_resolution_refuses_approval(self):
        for directory in (self.target / "bin", self.target / "sub/bin"):
            directory.mkdir(parents=True)
            executable = directory / "check"
            executable.write_text("#!/bin/sh\nexit 1\n")
            executable.chmod(0o755)
        self.plan["checks"][0].update(
            command=["check"], working_directory="sub", evaluator_artifacts=[])
        self.write_plan()
        self.assertEqual(self.overlay("generate").returncode, 0)
        result = subprocess.run(
            [sys.executable, str(ROOT / "skills/spec-oracle/oracle_overlay.py"),
             "approve", str(self.target), str(self.spec), "demo"],
            cwd=self.target, capture_output=True, text=True, timeout=30,
            env={**os.environ, "PATH": "bin:" + os.environ["PATH"],
                 "XDG_STATE_HOME": str(self.target / "state")})
        self.assertEqual(result.returncode, 2, result.stderr)

    def test_ac3_extensionless_interpreter_assertion_requires_binding(self):
        script = self.target / "assertion"
        script.write_text("raise SystemExit(1)\n")
        self.plan["checks"][0].update(
            command=[sys.executable, "assertion"], evaluator_artifacts=[])
        self.write_plan()
        self.assertEqual(self.overlay("generate").returncode, 0)
        self.assertEqual(self.overlay("approve").returncode, 2)
        self.plan["checks"][0]["evaluator_artifacts"] = ["assertion"]
        self.write_plan()
        self.install_required()
        self.assertEqual(self.gate()[0].returncode, 1)
        script.write_text("raise SystemExit(0)\n")
        self.assertEqual(self.gate()[0].returncode, 2)

    def test_ac3_generated_relative_extensionless_interpreter_refuses(self):
        source = self.target / "input"
        source.mkdir()
        (source / "assertion").write_text("raise SystemExit(0)\n")
        self.plan["checks"][0].update(
            family="generated_artifact_command", source="input",
            command=[sys.executable, "assertion"],
            evaluator_artifacts=["input/assertion"])
        self.write_plan()
        self.assertEqual(self.overlay("generate").returncode, 0)
        self.assertEqual(self.overlay("approve").returncode, 2)

    def test_ac3_python_option_separator_cannot_hide_script_entrypoint(self):
        (self.target / "-c").write_text("raise SystemExit(1)\n")
        for family in ("command", "generated_artifact_command"):
            with self.subTest(family=family):
                self.plan["checks"][0].update(
                    family=family, command=[sys.executable, "--", "-c", "arg"],
                    evaluator_artifacts=[])
                self.write_plan()
                self.assertEqual(self.overlay("generate").returncode, 0)
                self.assertEqual(self.overlay("approve").returncode, 2)

    def test_ac3_invalid_opt_in_never_falls_back_to_v1(self):
        self.install_required()
        manifest = self.target / ".servo/install.json"
        original = manifest.read_text()
        manifest.write_text(original.replace('"required_policy":', '"old_policy":'))
        result, payload = self.gate()
        self.assertEqual(result.returncode, 2)
        self.assertEqual(payload["schema_version"], 2)
        manifest.write_text(original)
        (self.target / ".servo/required-policy.json").unlink()
        self.assertEqual(self.gate()[0].returncode, 2)

    def test_ac4_concurrent_single_invocations_and_immutable_publication(self):
        self.install_required()
        commands = [sys.executable, str(self.runtime / "skills/quality-gate/gate.py"),
                    str(self.target), "--json"]
        # Count by exclusive files, not a racy shared read/modify/write counter.
        plan = json.loads((self.out / "checks.json").read_text())
        plan["checks"][0]["command"] = [
            sys.executable, "-c",
            "import os; from pathlib import Path; "
            "Path('call-'+os.environ['SERVO_GATE_RUN_ID']).open('a').write('x'); "
            "raise SystemExit(1)"]
        self.plan = plan
        self.write_plan()
        self.install_required()
        processes = [subprocess.Popen(commands, stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE, text=True) for _ in range(2)]
        payloads = [json.loads(p.communicate(timeout=30)[0]) for p in processes]
        self.assertEqual([p.returncode for p in processes], [1, 1])
        self.assertEqual(len({p["run_id"] for p in payloads}), 2)
        self.assertEqual(len(list(self.target.glob("call-*"))), 2)
        self.assertTrue(all(p.read_text() == "x" for p in self.target.glob("call-*")))
        self.assertEqual((self.target / "quality-calls").read_text(), "xx")
        runtime = load_runtime()
        path = self.out / "immutable.json"
        runtime.publish(path, {"x": 1})
        with self.assertRaises(FileExistsError):
            runtime.publish(path, {"x": 2})
        result, payload = self.gate(SERVO_GATE_RUN_ID=payloads[0]["run_id"])
        self.assertEqual(result.returncode, 2)
        self.assertIn("exists", str(payload["required"]))

    def test_ac4_result_identity_complete_set_and_partial_write_controls(self):
        self.install_required()
        _, payload = self.gate()
        runtime = load_runtime()
        policy, policy_hash = runtime.installed_policy(self.target)
        entry = policy["components"][0]
        component = next(c for c in payload["components"] if c["result"])
        reference = component["result"]
        path = Path(reference["path"])
        original = path.read_bytes()
        changes = [
            lambda r: r.update(schema_version=99),
            lambda r: r.update(run_id="stale"),
            lambda r: r.update(component="other"),
            lambda r: r.update(config_hash="wrong"),
            lambda r: r.update(policy_hash="wrong"),
            lambda r: r.update(evaluator_hash="wrong"),
            lambda r: r.update(source_identity={}),
            lambda r: r["evidence"].append(dict(r["evidence"][0])),
            lambda r: r.update(evidence=[]),
            lambda r: r["evidence"][0].update(check_id="extra"),
            lambda r: r["required"].update(ids=[]),
            lambda r: r["required"]["counts"].update(fail=0),
        ]
        for mutate in changes:
            record = json.loads(original)
            mutate(record)
            path.write_bytes(runtime.canonical(record))
            with self.assertRaises((ValueError, KeyError)):
                runtime.validate_component(
                    {**reference, "hash": runtime.file_hash(path)}, entry,
                    payload["run_id"], policy_hash, component["score"], self.target)
        path.write_bytes(b'{"schema_version":')
        with self.assertRaises(ValueError):
            runtime.validate_component(
                {**reference, "hash": runtime.file_hash(path)}, entry,
                payload["run_id"], policy_hash, component["score"], self.target)
        path.write_bytes(original)
        with self.assertRaises(ValueError):
            runtime.validate_component({**reference, "hash": "wrong"}, entry,
                                       payload["run_id"], policy_hash, component["score"],
                                       self.target)

    def test_ac5_quality_required_decision_table_preserves_overall_failure(self):
        self.install_required()
        for present, threshold, code, reason in (
            (True, "0.5", 0, None),
            (True, "1.1", 1, "quality_below_threshold"),
            (False, "1.1", 1, "required_and_quality_failed"),
        ):
            if present:
                (self.target / "subject").touch()
            else:
                (self.target / "subject").unlink()
            result, payload = self.gate(THRESHOLD=threshold)
            self.assertEqual(result.returncode, code)
            self.assertEqual(payload["reason"], reason)
            self.assertEqual(payload["threshold_override"]["source"], "environment")
            if present:
                reference = next(c["result"] for c in payload["components"] if c["result"])
                record = json.loads(Path(reference["path"]).read_text())
                self.assertEqual(record["required"]["status"], "pass")
                self.assertEqual(payload["status"], "fail" if code else "pass")

    def test_ac6_disabled_reapproved_removal_empty_stays_v2_and_force_refuses(self):
        self.install_required()
        snapshot = (self.target / "oracle.sh").read_bytes()
        uninstall = self.cli("spec-oracle/oracle_overlay.py", "uninstall",
                             str(self.target), "demo")
        self.assertEqual(uninstall.returncode, 2)
        self.assertEqual(snapshot, (self.target / "oracle.sh").read_bytes())
        force = self.cli("scaffold-init/scaffold.py", str(self.target), "--force")
        self.assertNotEqual(force.returncode, 0)
        self.assertEqual(snapshot, (self.target / "oracle.sh").read_bytes())
        self.plan["required_policy"]["enabled"] = False
        self.plan["checks"][0]["required"] = False
        self.write_plan()
        self.assertEqual(self.overlay("install", "--enable-required").returncode, 2)
        self.install_required()
        result, payload = self.gate()
        self.assertEqual(result.returncode, 0, payload)
        self.assertEqual(payload["schema_version"], 2)
        self.assertEqual(payload["required"]["ids"], [])
        for _ in range(2):
            uninstall = self.cli("spec-oracle/oracle_overlay.py", "uninstall",
                                 str(self.target), "demo")
            self.assertEqual(uninstall.returncode, 0, uninstall.stderr)

    def test_ac6_customized_driver_refuses_without_partial_writes(self):
        self.assertEqual(self.overlay("generate").returncode, 0)
        self.assertEqual(self.overlay("approve").returncode, 0)
        oracle = self.target / "oracle.sh"
        oracle.write_text(oracle.read_text().replace('weighted_sum="0"', 'weighted_sum="1"'))
        before = {p: p.read_bytes() for p in self.target.rglob("*") if p.is_file()}
        self.assertEqual(self.overlay("install", "--enable-required").returncode, 2)
        self.assertEqual(before, {p: p.read_bytes() for p in self.target.rglob("*") if p.is_file()})

    def test_ac6_seed_driver_marker_does_not_truncate_custom_scorer(self):
        oracle = self.target / "oracle.sh"
        text = oracle.read_text().replace(
            '  python3 -c "from pathlib import Path; p=Path(\'quality-calls\'); '
            'p.open(\'a\').write(\'x\'); print(1.0)"',
            '  local weighted_sum="0"\nweighted_sum="0"\n  printf "1.0\\n"')
        self.assertIn('local weighted_sum="0"', text)
        oracle.write_text(text)
        self.install_required()
        syntax = subprocess.run(["bash", "-n", str(oracle)],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(syntax.returncode, 0, syntax.stderr)
        self.assertIn('local weighted_sum="0"', oracle.read_text())
        result, payload = self.gate()
        self.assertEqual(result.returncode, 1, payload)
        self.assertEqual(payload["reason"], "required_constraints_failed")
        self.assertEqual(payload["composite"], 1.0)

    def test_ac6_no_policy_scalar_and_score_only_stay_legacy(self):
        self.plan.pop("required_policy")
        self.plan["checks"][0].pop("required")
        self.write_plan()
        for operation in ("generate", "approve", "install"):
            result = self.overlay(operation)
            self.assertEqual(result.returncode, 0, result.stderr)
        result, payload = self.gate(THRESHOLD="0")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(payload["schema_version"], 1)
        score = self.cli("spec-oracle/checks.py", str(self.out / "checks.json"),
                         "--base-dir", str(self.target), "--score-only")
        self.assertEqual(score.returncode, 0)
        self.assertEqual(float(score.stdout), 0.0)

    def test_ac6_false_required_annotation_keeps_scalar_freeze(self):
        self.plan.pop("required_policy")
        self.plan["checks"][0]["required"] = False
        self.write_plan()
        for operation in ("generate", "approve", "install"):
            extra = ["--vendor-engine"] if operation != "approve" else []
            result = self.overlay(operation, *extra)
            self.assertEqual(result.returncode, 0, result.stderr)
        (self.out / "required_runtime.py").unlink()
        result, payload = self.gate(THRESHOLD="0")
        self.assertEqual(result.returncode, 0, (result.stderr, payload))
        self.assertEqual(payload["schema_version"], 1)
        score = self.cli(
            "spec-oracle/checks.py", str(self.out / "checks.json"),
            "--base-dir", str(self.target), "--score-only", "--enforce-freeze")
        self.assertEqual(score.returncode, 0, score.stderr)
        self.assertEqual(float(score.stdout), 0.0)

    def test_ac6_legacy_oracle_comment_encoding_does_not_enable_policy(self):
        oracle = self.target / "oracle.sh"
        oracle.write_bytes(oracle.read_bytes() + b"\n# legacy comment byte: \xff\n")
        result = self.cli("quality-gate/gate.py", str(self.target), "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["status"], "pass")
        manifest = self.target / ".servo/install.json"
        manifest.write_bytes(manifest.read_bytes() + b"\n\xff")
        force = self.cli("scaffold-init/scaffold.py", str(self.target), "--force")
        self.assertEqual(force.returncode, 0, force.stderr)
        self.assertNotIn(b"\xff", oracle.read_bytes())
        self.assertNotIn("required_policy", json.loads(manifest.read_text()))

    def test_ac1_generated_artifact_setup_and_vendored_assertion_closure(self):
        script = self.target / "build.py"
        script.write_text("from pathlib import Path\nPath('built').touch()\n")
        self.plan["checks"][0] = {
            "id": "generated", "family": "generated_artifact_command", "required": True,
            "build_command": [sys.executable, str(script)],
            "command": [sys.executable, "-c",
                        "from pathlib import Path; raise SystemExit(not Path('built').exists())"],
            "evaluator_artifacts": ["build.py"],
        }
        self.write_plan()
        for operation, extra in (("generate", ["--vendor-engine"]), ("approve", []),
                                 ("install", ["--vendor-engine", "--enable-required"])):
            result = self.overlay(operation, *extra)
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.out / "required_runtime.py").is_file())
        result, payload = self.gate()
        self.assertEqual(result.returncode, 0, payload)
        script.write_text("raise SystemExit(0)\n")
        self.assertEqual(self.gate()[0].returncode, 2)

    def test_ac6_supported_gate_vendor_carries_runtime(self):
        spec = importlib.util.spec_from_file_location(
            "loop_vendor", ROOT / "skills/agent-loop/loop.py")
        loop = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = loop
        spec.loader.exec_module(loop)
        path, error = loop._ensure_vendored_gate(self.target)
        self.assertIsNone(error)
        self.assertTrue(path.with_name("required_runtime.py").is_file())
        self.install_required()
        result = subprocess.run([sys.executable, str(path), str(self.target), "--json"],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)["schema_version"], 2)

    def test_ac6_missing_vendored_runtime_refuses_instead_of_downgrading(self):
        self.install_required()
        vendor = self.target / "vendor"
        vendor.mkdir()
        gate = vendor / "gate.py"
        shutil.copyfile(ROOT / "skills/quality-gate/gate.py", gate)
        for present in (False, True):
            if present:
                (self.target / "subject").touch()
            result = subprocess.run(
                [sys.executable, str(gate), str(self.target), "--json"],
                capture_output=True, text=True, timeout=30)
            payload = json.loads(result.stdout)
            self.assertEqual(result.returncode, 2, payload)
            self.assertEqual(payload["schema_version"], 2)
            self.assertEqual(payload["status"], "env_error")
            self.assertEqual(payload["reason"], "required_evidence_unavailable")
            self.assertIn("required_runtime.py", str(payload["required"]))
            self.assertFalse((self.target / "calls").exists())
            self.assertFalse((self.target / "quality-calls").exists())

    def test_ac6_vendored_checks_and_policy_survive_target_relocation(self):
        for operation, extra in (("generate", ["--vendor-engine"]), ("approve", []),
                                 ("install", ["--vendor-engine", "--enable-required"])):
            result = self.overlay(operation, *extra)
            self.assertEqual(result.returncode, 0, result.stderr)
        with tempfile.TemporaryDirectory() as temporary:
            clone = Path(temporary) / "clone"
            shutil.copytree(self.target, clone)
            result = self.cli("quality-gate/gate.py", str(clone), "--json")
            payload = json.loads(result.stdout)
            self.assertEqual(result.returncode, 1, payload)
            reference = next(c["result"] for c in payload["components"] if c["result"])
            self.assertTrue(Path(reference["path"]).resolve().is_relative_to(clone.resolve()))

    def test_ac4_direct_oracle_rejects_unowned_context(self):
        self.install_required()
        result = subprocess.run([str(self.target / "oracle.sh")], cwd=self.target,
                                capture_output=True, text=True,
                                env={**os.environ, "SERVO_GATE_RUN_ID": "not-a-uuid",
                                     "SERVO_GATE_RESULT_DIR": str(self.target)}, timeout=30)
        self.assertEqual(result.returncode, 2)
        self.assertFalse((self.target / "oracle-result.json").exists())

    def test_ac5_gate_recomputes_quality_instead_of_trusting_oracle_label(self):
        oracle = self.target / "oracle.sh"
        oracle.write_text(oracle.read_text().replace("print(1.0)", "print(0.75)"))
        self.install_required()
        (self.target / "subject").touch()
        runtime = load_runtime()

        def intercepted(oracle, target, timeout, env):
            result = subprocess.run([str(oracle)], cwd=target, env=env,
                                    capture_output=True, text=True, timeout=30)
            path = Path(env["SERVO_GATE_RESULT_DIR"]) / "oracle-result.json"
            payload = runtime.load(path)
            # A component's pass cannot legitimize a forged quality composite.
            payload["composite"] = 1.0
            path.write_bytes(runtime.canonical(payload))
            return result.stdout, result.stderr, 0, False

        from contextlib import redirect_stdout
        from io import StringIO
        output = StringIO()
        with redirect_stdout(output):
            code = runtime.run_gate(self.target, intercepted, 30, True, False)
        self.assertEqual(code, 2)
        self.assertIn("quality composite mismatch",
                      str(json.loads(output.getvalue())["required"]))

    def test_ac6_runtime_vendor_contract_includes_carrier(self):
        contract = json.loads((ROOT / ".claude-plugin/install-contract.json").read_text())
        gate = next(s for s in contract["required"]["skills"] if s["name"] == "quality-gate")
        self.assertIn("required_runtime.py", gate["files"])

    def test_ac6_unsupported_enabled_driver_refuses_reinstall_without_writes(self):
        self.install_required()
        oracle = self.target / "oracle.sh"
        oracle.write_text(oracle.read_text().replace("set -euo pipefail", "set -eu"))
        before = {p: p.read_bytes() for p in self.target.rglob("*") if p.is_file()}
        self.assertEqual(self.overlay("install", "--enable-required").returncode, 2)
        self.assertEqual(before, {p: p.read_bytes() for p in self.target.rglob("*") if p.is_file()})

    def test_ac3_finite_quality_and_invalid_policy_controls(self):
        for mutate in (
            lambda p: p["required_policy"].update(schema_version=2),
            lambda p: p["required_policy"].update(enabled=1),
            lambda p: p["checks"][0].update(required="true"),
            lambda p: p["checks"].append(dict(p["checks"][0])),
            lambda p: p["checks"][0].update(id=""),
            lambda p: p["checks"][0].pop("evaluator_artifacts"),
        ):
            plan = json.loads(json.dumps(self.plan))
            mutate(self.plan)
            self.write_plan()
            self.overlay("generate")
            self.assertEqual(self.overlay("approve").returncode, 2)
            self.plan = plan
        self.write_plan()
        self.install_required()
        for threshold in ("nan", "inf", "-inf"):
            result, payload = self.gate(THRESHOLD=threshold)
            self.assertEqual(result.returncode, 2, payload)
            self.assertEqual(payload["schema_version"], 2)

    def test_ac6_dynamic_component_array_refuses_before_writes(self):
        self.overlay("generate")
        self.overlay("approve")
        oracle = self.target / "oracle.sh"
        oracle.write_text(oracle.read_text().replace('"baseline:1"', '"${CUSTOM}:1"'))
        before = {p: p.read_bytes() for p in self.target.rglob("*") if p.is_file()}
        self.assertEqual(self.overlay("install", "--enable-required").returncode, 2)
        self.assertEqual(before, {p: p.read_bytes() for p in self.target.rglob("*") if p.is_file()})

    def test_ac3_invalid_oracle_required_aggregate_refuses_retains_failure(self):
        self.install_required()
        runtime = load_runtime()

        def intercepted(oracle, target, timeout, env):
            result = subprocess.run([str(oracle)], cwd=target, env=env,
                                    capture_output=True, text=True, timeout=30)
            path = Path(env["SERVO_GATE_RESULT_DIR"]) / "oracle-result.json"
            payload = runtime.load(path)
            payload["required"]["failed"] = []
            path.write_bytes(runtime.canonical(payload))
            return result.stdout, result.stderr, result.returncode, False

        from contextlib import redirect_stdout
        from io import StringIO
        output = StringIO()
        with redirect_stdout(output):
            code = runtime.run_gate(self.target, intercepted, 30, True, False)
        payload = json.loads(output.getvalue())
        self.assertEqual(code, 2)
        self.assertIn("assertion", payload["required"]["failed"])

    def test_ac3_malformed_raw_evidence_cannot_claim_required_pass(self):
        self.install_required()
        _, payload = self.gate()
        runtime = load_runtime()
        policy, policy_hash = runtime.installed_policy(self.target)
        entry = policy["components"][0]
        component = next(c for c in payload["components"] if c["result"])
        reference = component["result"]
        path = Path(reference["path"])
        original = runtime.load(path)
        for mutation in (
            {"schema_version": True}, {"message": {}},
            {"family": "generated_artifact_command"}, {"status": "pass"},
        ):
            record = json.loads(json.dumps(original))
            record["evidence"][0].update(mutation)
            record["required"] = runtime.interpret(entry["required_ids"], record["evidence"])
            path.write_bytes(runtime.canonical(record))
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                runtime.validate_component(
                    {**reference, "hash": runtime.file_hash(path)}, entry,
                    payload["run_id"], policy_hash, component["score"], self.target)

    def test_ac3_result_domain_types_cannot_alias_valid_json_numbers(self):
        self.install_required()
        (self.target / "subject").touch()
        runtime = load_runtime()
        from contextlib import redirect_stdout
        from io import StringIO
        for mutation in (
                {"schema_version": 2.0}, {"exit_code": False},
                {"composite": True}, {"unbound_scalar_result": True},
                {"threshold": 10**400},
                {"component_weight": 10**400}, {"component_score": 10**400},
                {"component_exit": False}, {"component_exit": 0.0},
                {"counts": {"pass": True, "fail": 0, "unknown": 0}}):
            with self.subTest(mutation=mutation):
                def intercepted(oracle, target, timeout, env, mutation=mutation):
                    result = subprocess.run([str(oracle)], cwd=target, env=env,
                                            capture_output=True, text=True, timeout=30)
                    path = Path(env["SERVO_GATE_RESULT_DIR"]) / "oracle-result.json"
                    payload = runtime.load(path)
                    if "counts" in mutation:
                        payload["required"]["counts"] = mutation["counts"]
                    elif "component_exit" in mutation:
                        payload["components"][0]["exit_code"] = mutation["component_exit"]
                    elif "component_weight" in mutation:
                        payload["components"][0]["weight"] = mutation["component_weight"]
                    elif "component_score" in mutation:
                        payload["components"][0]["score"] = mutation["component_score"]
                    elif "unbound_scalar_result" in mutation:
                        scalar = next(c for c in payload["components"] if c["result"] is None)
                        scalar["result"] = {"path": str(target / "unbound-result.json"),
                                            "hash": "sha256:unbound"}
                    else:
                        payload.update(mutation)
                    path.write_bytes(runtime.canonical(payload))
                    return result.stdout, result.stderr, result.returncode, False
                output = StringIO()
                with redirect_stdout(output):
                    code = runtime.run_gate(self.target, intercepted, 30, True, False)
                self.assertEqual(code, 2, output.getvalue())
        _, payload = self.gate()
        policy, policy_hash = runtime.installed_policy(self.target)
        entry = policy["components"][0]
        component = next(c for c in payload["components"] if c["result"])
        path = Path(component["result"]["path"])
        record = runtime.load(path)
        record["required"]["counts"]["pass"] = True
        path.write_bytes(runtime.canonical(record))
        with self.assertRaises(ValueError):
            runtime.validate_component(
                {"path": str(path), "hash": runtime.file_hash(path)}, entry,
                payload["run_id"], policy_hash, component["score"], self.target)

    def test_ac3_empty_policy_still_requires_numeric_quality_fields(self):
        self.install_required()
        self.plan["required_policy"]["enabled"] = False
        self.plan["checks"][0]["required"] = False
        self.write_plan()
        self.install_required()
        removal = self.cli("spec-oracle/oracle_overlay.py", "uninstall",
                           str(self.target), "demo")
        self.assertEqual(removal.returncode, 0, removal.stderr)
        runtime = load_runtime()
        from contextlib import redirect_stdout
        from io import StringIO
        for field in ("score", "weight"):
            with self.subTest(field=field):
                def intercepted(oracle, target, timeout, env, field=field):
                    result = subprocess.run([str(oracle)], cwd=target, env=env,
                                            capture_output=True, text=True, timeout=30)
                    path = Path(env["SERVO_GATE_RESULT_DIR"]) / "oracle-result.json"
                    payload = runtime.load(path)
                    payload["components"][0][field] = "1.0"
                    path.write_bytes(runtime.canonical(payload))
                    return result.stdout, result.stderr, result.returncode, False
                output = StringIO()
                with redirect_stdout(output):
                    code = runtime.run_gate(self.target, intercepted, 30, True, False)
                self.assertEqual(code, 2, output.getvalue())

    def test_ac6_required_opt_in_preserves_usd_budget_preflight(self):
        self.install_required()
        manifest = self.target / ".servo/install.json"
        data = json.loads(manifest.read_text())
        data.update(components=["baseline"], unpriced_components=["baseline"])
        manifest.write_text(json.dumps(data))
        result = self.cli("quality-gate/gate.py", str(self.target), "--json",
                          "--usd-budget-context")
        self.assertEqual(result.returncode, 2)
        self.assertFalse((self.target / "calls").exists())
        self.assertIn("unpriced", result.stdout)

    def test_ac6_explicit_reapproval_can_refresh_installed_runtime_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            package = Path(temporary) / "package"
            # A bounded source-package fixture, never mutate the real runtime.
            for name in ("spec-oracle", "quality-gate"):
                shutil.copytree(ROOT / "skills" / name, package / "skills" / name)
            shutil.copytree(ROOT / "templates", package / "templates")
            self.runtime = package
            self.install_required()
            runtime = package / "skills/quality-gate/required_runtime.py"
            runtime.write_text(runtime.read_text() + "\n# reviewed new runtime epoch\n")
            self.install_required()
            result, payload = self.gate()
            self.assertEqual(result.returncode, 1, payload)

    def test_ac3_missing_oracle_record_retains_exact_run_bound_failure(self):
        self.install_required()
        runtime = load_runtime()

        def intercepted(oracle, target, timeout, env):
            result = subprocess.run([str(oracle)], cwd=target, env=env,
                                    capture_output=True, text=True, timeout=30)
            (Path(env["SERVO_GATE_RESULT_DIR"]) / "oracle-result.json").unlink()
            return result.stdout, result.stderr, result.returncode, False

        from contextlib import redirect_stdout
        from io import StringIO
        output = StringIO()
        with redirect_stdout(output):
            code = runtime.run_gate(self.target, intercepted, 30, True, False)
        payload = json.loads(output.getvalue())
        self.assertEqual(code, 2)
        self.assertIn("assertion", payload["required"]["failed"])
        self.assertTrue(any(c["result"] for c in payload["components"]))
        self.assertEqual((self.target / "calls").read_text(), "x")


class GeneratedRequiredGateTests(unittest.TestCase):
    def test_ac6_generated_hosts_real_scaffold_approve_install_gate(self):
        spec = importlib.util.spec_from_file_location(
            "required_package_builder", ROOT / "scripts/build_host_packages.py")
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)
        with tempfile.TemporaryDirectory() as temporary:
            hosts = Path(temporary) / "hosts"
            self.assertEqual(builder.build_all(ROOT, hosts, out=io.StringIO()), 0)
            for relative in ("claude", "codex/plugins/servo", "copilot/.github"):
                with self.subTest(host=relative):
                    fixture = InstalledRequiredGateTests()
                    fixture.package = hosts / relative
                    fixture.setUp()
                    try:
                        fixture.install_required()
                        result, payload = fixture.gate(THRESHOLD="0")
                        self.assertEqual(result.returncode, 1, (result.stderr, payload))
                        self.assertEqual(payload["reason"], "required_constraints_failed")
                        (fixture.target / "subject").touch()
                        self.assertEqual(fixture.gate()[0].returncode, 0)
                        (fixture.out / "oracle.sh.fragment").write_text("edited\n")
                        self.assertEqual(fixture.gate()[0].returncode, 2)
                    finally:
                        fixture.doCleanups()


if __name__ == "__main__":
    unittest.main()
