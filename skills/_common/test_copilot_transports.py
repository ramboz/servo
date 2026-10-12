import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SKILLS = Path(__file__).resolve().parent.parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def judge_config():
    return {
        "transport": "copilot", "model": "pinned", "decoding_mode": "native-default",
        "runtime_version": "1.0.96-2",
    }


def fake_result():
    events = [
        {"type": "assistant.message", "data": {
            "phase": "final_answer", "model": "pinned",
            "content": '{"score":0.7,"reasoning":"fixture","strengths":[],"weaknesses":[]}',
        }},
        {"type": "result", "exitCode": 0, "sessionId": "fresh"},
    ]
    return subprocess.CompletedProcess([], 0, "\n".join(map(json.dumps, events)), "")


class NativeTransportTests(unittest.TestCase):
    def test_native_candidate_policy_is_frozen_but_moving_bytes_are_not(self):
        module = load("native_candidate_hash", SKILLS / "eval-authoring" / "score.py")
        config = {
            "judge": judge_config(), "candidate_policy": "component-file-utf8-v1",
            "rubric": "fixture", "samples": {"n": 2}, "threshold": 0.8,
            "cases": [{"id": "fixture", "input": "not the candidate", "candidate_file": "one.txt",
                       "expected_output": {"constraints": []}, "category": "happy_path"}],
        }
        before = module.definition_hash(config)
        config["cases"][0]["candidate_file"] = "two.txt"
        self.assertNotEqual(module.definition_hash(config), before)
        config["cases"][0]["candidate_file"] = "one.txt"
        config["candidate_policy"] = "unsupported"
        self.assertNotEqual(module.definition_hash(config), before)
        legacy = dict(config, judge={"transport": "api", "model": "old"})
        expected = module._fe.definition_hash(
            legacy, module._CASES_KEY, module._CASE_PIN_FIELDS, module._EXTRA_HASH_FIELDS,
        )
        self.assertEqual(module.definition_hash(legacy), expected)

    def test_native_candidate_snapshot_rejects_escapes_binary_and_constraints(self):
        module = load("native_candidate_read", SKILLS / "eval-authoring" / "score.py")
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            candidate = directory / "candidate.txt"
            candidate.write_text("public candidate")
            config = {"judge": judge_config(), "candidate_policy": "component-file-utf8-v1",
                      "cases": [{"id": "fixture", "candidate_file": "candidate.txt",
                                 "expected_output": {"constraints": []}}]}
            module.validate_native_candidates(config, directory)
            text, snapshot = module.acquire_native_candidate(directory, config["cases"][0])
            self.assertEqual(text, "public candidate")
            self.assertEqual(snapshot["sha256"], module.sha256_text("public candidate"))
            self.assertEqual(snapshot["candidate_file"], "candidate.txt")
            for path in ("../outside.txt", str(candidate), "missing.txt"):
                with self.subTest(path=path), self.assertRaises(module.EnvError):
                    module.acquire_native_candidate(
                        directory, dict(config["cases"][0], candidate_file=path),
                    )
            outside = directory.parent / (directory.name + "-outside.txt")
            try:
                outside.write_text("outside")
                (directory / "escape.txt").symlink_to(outside)
                with self.assertRaises(module.EnvError):
                    module.acquire_native_candidate(
                        directory, dict(config["cases"][0], candidate_file="escape.txt"),
                    )
            finally:
                outside.unlink(missing_ok=True)
            candidate.write_bytes(b"bad\x00binary")
            with self.assertRaises(module.EnvError):
                module.acquire_native_candidate(directory, config["cases"][0])
            config["cases"][0]["expected_output"]["constraints"] = ["length >= 1"]
            with self.assertRaises(module.EnvError):
                module.validate_native_candidates(config, directory)

    def test_native_candidate_is_one_snapshot_for_the_entire_sample_batch(self):
        module = load("native_candidate_batch", SKILLS / "eval-authoring" / "score.py")
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            candidate = directory / "candidate.txt"
            candidate.write_text("first output")
            config = {
                "judge": judge_config(), "candidate_policy": "component-file-utf8-v1",
                "rubric": "fixture", "samples": {"n": 2}, "threshold": 0.8,
                "cases": [{"id": "fixture", "input": "not an output",
                           "candidate_file": "candidate.txt", "category": "happy_path",
                           "expected_output": {"constraints": []}}],
                "approval_status": "approved",
            }
            config["hashes"] = module.artifact_hashes(config, directory)
            config["approved_content_hash"] = module.definition_hash(config)
            (directory / "config.json").write_text(json.dumps(config))
            gathered = []

            def judging(text, _config):
                gathered.append(text)
                candidate.write_text("later output")
                return {"score": 0.8}

            with mock.patch.dict(os.environ, {}, clear=True), \
                    mock.patch.object(module, "judge", side_effect=judging):
                self.assertEqual(module.score(directory), 0.8)
            self.assertEqual(gathered, ["first output", "first output"])
            record = json.loads((directory / "ledger.jsonl").read_text().splitlines()[-1])
            self.assertEqual(
                record["cases"][0]["candidate_snapshot"]["sha256"],
                module.sha256_text("first output"),
            )
            self.assertEqual(module.definition_hash(config), config["approved_content_hash"])
            config["cases"].append({
                "id": "missing", "candidate_file": "missing.txt",
                "expected_output": {"constraints": []}, "category": "happy_path",
            })
            config["approved_content_hash"] = module.definition_hash(config)
            (directory / "config.json").write_text(json.dumps(config))
            with mock.patch.dict(os.environ, {}, clear=True), \
                    mock.patch.object(module, "judge") as judge:
                with self.assertRaises(module.EnvError):
                    module.score(directory)
                judge.assert_not_called()

    def test_native_score_injection_is_refused_in_every_consumer(self):
        for skill in ("eval-authoring", "content-fidelity", "design-eval"):
            module = load("native_fake_" + skill.replace("-", "_"), SKILLS / skill / "score.py")
            with self.subTest(skill=skill), tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary)
                config = {
                    "schema_version": 2, "judge": judge_config(), "rubric": "fixture",
                    "samples": {"n": 1}, "threshold": 0.8,
                    "cases": [{
                        "id": "fixture", "input": "public",
                        "expected_output": {"constraints": []},
                        "source": {"type": "file", "path": "generated.txt"},
                        "reference": "public",
                    }],
                    "screens": [{"id": "fixture", "reference": "ref.png", "weight": 1.0}],
                    "dimensions": [{"id": "color", "description": "fixture", "weight": 1.0}],
                    "ignore": [], "approval_status": "approved",
                }
                if skill == "design-eval":
                    config.pop("rubric")
                config["hashes"] = module.artifact_hashes(config, directory)
                config["approved_content_hash"] = module.definition_hash(config)
                (directory / "config.json").write_text(json.dumps(config))
                with mock.patch.dict(os.environ, {
                    module._FAKE_SCORES_ENV: '{"fixture":[1.0]}',
                }, clear=True), self.assertRaisesRegex(module.EnvError, "inject|fake"):
                    module.score(directory)

    def test_installed_presets_sync_pricing_on_refreeze_not_only_reinstall(self):
        for skill, filename in (
            ("content-fidelity", "content_fidelity.py"), ("design-eval", "design_eval.py"),
        ):
            module = load("native_refreeze_" + skill.replace("-", "_"), SKILLS / skill / filename)
            with self.subTest(skill=skill), tempfile.TemporaryDirectory() as temporary:
                target = Path(temporary)
                (target / "oracle.sh").write_text(
                    '#!/bin/bash\nCOMPONENTS=(\n)\nweighted_sum="0"\n',
                )
                manifest = target / ".servo" / "install.json"
                manifest.parent.mkdir()
                manifest.write_text('{"components":[]}')
                directory = module.init(target)
                config_path = directory / "config.json"
                config = json.loads(config_path.read_text())
                config["cases" if skill == "content-fidelity" else "screens"] = []
                config_path.write_text(json.dumps(config))
                module.install(target)
                self.assertNotIn("unpriced_components", json.loads(manifest.read_text()))
                config["judge"] = judge_config()
                config_path.write_text(json.dumps(config))
                kwargs = {"acknowledge": True} if skill == "design-eval" else {}
                with mock.patch.dict("os.environ", {}, clear=True), \
                        mock.patch("shutil.which", return_value="/fake/copilot"), \
                        mock.patch("subprocess.run", return_value=subprocess.CompletedProcess(
                            [], 0, "GitHub Copilot CLI 1.0.96-2.\n", "",
                        )):
                    module.freeze(target, **kwargs)
                    self.assertEqual(
                        json.loads(manifest.read_text())["unpriced_components"], [module.COMPONENT],
                    )
                    invalid = json.loads(config_path.read_text())
                    invalid["judge"]["temperature"] = 0.0
                    config_path.write_text(json.dumps(invalid))
                    before = config_path.read_bytes()
                    with self.assertRaises(module._fe.EnvError):
                        module.freeze(target, **kwargs)
                    self.assertEqual(config_path.read_bytes(), before)
                    self.assertEqual(
                        json.loads(manifest.read_text())["unpriced_components"], [module.COMPONENT],
                    )
                config = json.loads(config_path.read_text())
                config["judge"] = {"transport": "api", "model": "old", "temperature": 0.0}
                config_path.write_text(json.dumps(config))
                module.freeze(target, **kwargs)
                self.assertNotIn("unpriced_components", json.loads(manifest.read_text()))

    def test_all_native_installers_register_unknown_usd_and_uninstall_clears_it(self):
        for skill, filename in (
            ("content-fidelity", "content_fidelity.py"), ("design-eval", "design_eval.py"),
            ("eval-authoring", "eval_authoring.py"),
        ):
            module = load("native_marker_" + skill.replace("-", "_"), SKILLS / skill / filename)
            with self.subTest(skill=skill), tempfile.TemporaryDirectory() as temporary:
                target = Path(temporary)
                (target / "oracle.sh").write_text(
                    '#!/bin/bash\nCOMPONENTS=(\n)\nweighted_sum="0"\n',
                )
                manifest = target / ".servo" / "install.json"
                manifest.parent.mkdir()
                manifest.write_text('{"components":[]}')
                if skill == "eval-authoring":
                    score = module._load_score()
                    config = {"judge": judge_config(), "approval_status": "approved"}
                    module.install_component(config, "fixture", target, 1.0, score)
                    component = "fixture"
                    self.assertEqual(
                        json.loads(manifest.read_text())["unpriced_components"], [component],
                    )
                    module.uninstall_component(target, component, score)
                else:
                    directory = module.init(target)
                    config_path = directory / "config.json"
                    config = json.loads(config_path.read_text())
                    config["judge"] = judge_config()
                    config_path.write_text(json.dumps(config))
                    module.install(target)
                    component = module.COMPONENT
                    self.assertEqual(
                        json.loads(manifest.read_text())["unpriced_components"], [component],
                    )
                    module.uninstall(target)
                self.assertNotIn("unpriced_components", json.loads(manifest.read_text()))

    def test_unpriced_manifest_registration_is_symmetric_and_preserves_old_shape(self):
        harness = load("native_registration", SKILLS / "_common" / "fidelity_eval.py")
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary)
            manifest = target / ".servo" / "install.json"
            manifest.parent.mkdir()
            manifest.write_text(
                json.dumps({"components": ["baseline"], "signals": {"tests": True}}),
            )
            harness.register_manifest(target, "native", unpriced=True)
            data = json.loads(manifest.read_text())
            self.assertEqual(data["unpriced_components"], ["native"])
            harness.register_manifest(target, "native", unpriced=True)
            self.assertEqual(json.loads(manifest.read_text())["unpriced_components"], ["native"])
            harness.register_manifest(target, "native")
            self.assertNotIn("unpriced_components", json.loads(manifest.read_text()))
            harness.register_manifest(target, "native", unpriced=True)
            harness.deregister_manifest(target, "native")
            self.assertEqual(json.loads(manifest.read_text()), {
                "components": ["baseline"], "signals": {"tests": True},
            })

    def test_installed_native_component_scores_and_rejects_definition_drift(self):
        module = load(
            "native_installed_content", SKILLS / "content-fidelity" / "content_fidelity.py",
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            binary = root / "fake-copilot"
            binary.write_text(
                "#!/usr/bin/env python3\n"
                "import json,sys\n"
                "if '--version' in sys.argv:\n"
                " print('GitHub Copilot CLI 1.0.96-2.')\n"
                "else:\n"
                " print(json.dumps({'type':'assistant.message','data':"
                "{'content':'{\"score\":0.7}','model':'pinned','phase':'final_answer'}}))\n"
                " print(json.dumps({'type':'result','exitCode':0,'sessionId':'fresh'}))\n"
            )
            binary.chmod(0o755)
            with mock.patch.dict(os.environ, {"SERVO_COPILOT_BIN": str(binary)}):
                directory = module.init(
                    root, transport="copilot", model="pinned", decoding_mode="native-default",
                )
                (directory / "candidate.txt").write_text("public fixture")
                config_path = directory / "config.json"
                config = json.loads(config_path.read_text())
                config["cases"] = [{
                    "id": "fixture", "reference": "public fixture",
                    "source": {"type": "file", "path": "candidate.txt"},
                }]
                config_path.write_text(json.dumps(config))
                module.freeze(root)
                result = subprocess.run(
                    [sys.executable, str(directory / "score.py"), str(root)],
                    capture_output=True, text=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(float(result.stdout.strip()), 0.7)
                approved = json.loads(config_path.read_text())
                approved["judge"]["runtime_version"] = "1.0.97-1"
                config_path.write_text(json.dumps(approved))
                stale = subprocess.run(
                    [sys.executable, str(directory / "score.py"), str(root)],
                    capture_output=True, text=True,
                )
                self.assertEqual(stale.returncode, 2)
                self.assertNotIn("0.7", stale.stdout)

    def test_native_params_do_not_rewrite_approved_definition(self):
        module = load(
            "native_approved_params", SKILLS / "eval-authoring" / "eval_authoring.py",
        )
        config = {"judge": judge_config(), "approval_status": "approved"}
        original = json.dumps(config, sort_keys=True)
        with self.assertRaises(module.EnvError):
            module.apply_params(
                config, transport="copilot", model="new", decoding_mode="native-default",
            )
        self.assertEqual(json.dumps(config, sort_keys=True), original)

    def test_all_three_judge_consumers_dispatch_native(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            first, second = directory / "first.png", directory / "second.png"
            first.write_bytes(b"first image")
            second.write_bytes(b"second image")
            for skill in ("eval-authoring", "content-fidelity", "design-eval"):
                module = load("native_" + skill.replace("-", "_"), SKILLS / skill / "score.py")
                config = {"judge": judge_config(), "rubric": "fixture"}
                version = subprocess.CompletedProcess([], 0, "GitHub Copilot CLI 1.0.96-2.\n", "")
                with self.subTest(skill=skill), \
                        mock.patch.dict("os.environ", {}, clear=True), \
                        mock.patch("shutil.which", return_value="/fake/copilot"), \
                        mock.patch("subprocess.run", side_effect=[version, fake_result()]):
                    if skill == "eval-authoring":
                        self.assertEqual(module.judge("candidate", config)["score"], 0.7)
                    elif skill == "content-fidelity":
                        self.assertEqual(module.judge("candidate", "reference", config), 0.7)
                    else:
                        self.assertEqual(module.judge(first, second, config), 0.7)

    def test_preset_native_initialization_is_explicit_and_vendors_helper(self):
        for skill, filename in (
            ("content-fidelity", "content_fidelity.py"), ("design-eval", "design_eval.py"),
        ):
            module = load("native_init_" + skill.replace("-", "_"), SKILLS / skill / filename)
            with self.subTest(skill=skill), tempfile.TemporaryDirectory() as temporary, \
                    mock.patch.dict("os.environ", {}, clear=True), \
                    mock.patch("shutil.which", return_value="/fake/copilot"), \
                    mock.patch("subprocess.run", return_value=subprocess.CompletedProcess(
                        [], 0, "GitHub Copilot CLI 1.0.96-2.\n", "",
                    )):
                directory = module.init(
                    Path(temporary), transport="copilot", model="pinned",
                    decoding_mode="native-default",
                )
                config = json.loads((directory / "config.json").read_text())
                self.assertEqual(config["judge"], judge_config())
                self.assertTrue((directory / "copilot_eval.py").is_file())
                with self.assertRaises(module._fe.EnvError):
                    module.init(
                        Path(temporary), transport="copilot", model="changed",
                        decoding_mode="native-default",
                    )
                self.assertEqual(json.loads((directory / "config.json").read_text()), config)

    def test_native_params_require_consent_and_reject_numeric_controls(self):
        module = load("native_authoring_params", SKILLS / "eval-authoring" / "eval_authoring.py")
        original = {
            "judge": {"transport": "api", "model": "old", "temperature": 0.0, "max_tokens": 1024},
            "samples": {"n": 3}, "threshold": 0.5,
        }
        with self.assertRaises(module.EnvError):
            module.apply_params(original, transport="copilot", model="pinned")
        self.assertEqual(original["judge"]["transport"], "api")
        with mock.patch.dict("os.environ", {}, clear=True), \
                mock.patch("shutil.which", return_value="/fake/copilot"), \
                mock.patch("subprocess.run", return_value=subprocess.CompletedProcess(
                    [], 0, "GitHub Copilot CLI 1.0.96-2.\n", "",
                )):
            module.apply_params(
                original, transport="copilot", model="pinned", decoding_mode="native-default",
            )
        self.assertEqual(original["judge"], judge_config())
        with self.assertRaises(module.EnvError):
            module.apply_params(original, temperature=0.0)

    def test_native_authoring_uses_two_fresh_calls_and_retains_human_curation(self):
        module = load("native_authoring_goal", SKILLS / "eval-authoring" / "eval_authoring.py")
        runtime = load("native_goal_runtime", SKILLS / "_common" / "copilot_eval.py")
        responses = [
            {"text": json.dumps({"acs": [{
                "statement": "Returns four", "tag": "deterministic", "rationale": "exact",
            }]}), "model": "pinned", "runtime_version": "1.0.96-2", "session_id": "expansion"},
            {"text": '{"flags":[]}', "model": "pinned",
             "runtime_version": "1.0.96-2", "session_id": "review"},
        ]
        with tempfile.TemporaryDirectory() as temporary, \
                mock.patch.object(
                    module, "_jig_independent_review_skill_path", return_value=None,
                ), \
                mock.patch.object(module, "_copilot_runtime", return_value=runtime), \
                mock.patch.object(runtime, "invoke", side_effect=responses) as invoke:
            payload, directory = module.from_goal_target(
                "Public fixture goal", Path(temporary), backend="copilot", model="pinned",
            )
            self.assertEqual(invoke.call_count, 2)
            self.assertEqual(payload["authoring_runtime"]["backend"], "copilot")
            self.assertTrue((directory / "criteria.json").is_file())
            self.assertNotEqual(
                payload["authoring_runtime"]["expansion_session"],
                payload["authoring_runtime"]["review_session"],
            )
            with self.assertRaises(module.EnvError):
                module.from_goal_target(
                    "Public fixture goal", Path(temporary), backend="copilot", model="pinned",
                )
            self.assertEqual(invoke.call_count, 2)


if __name__ == "__main__":
    unittest.main()
