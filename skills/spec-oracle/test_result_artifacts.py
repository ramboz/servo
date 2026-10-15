"""036-01: generic output closure/refusal, without design interpretation."""
import copy
import importlib.util
import io
import json
import subprocess
import sys
from contextlib import redirect_stdout
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


ck = module("output_checks", "skills/spec-oracle/checks.py")
rt = module("output_runtime", "skills/quality-gate/required_runtime.py")
installed = module("installed_examples", "skills/spec-oracle/test_required_gate.py")
CONFIG = {"root": "spec/oracle/card/runs/{run_id}/design",
          "manifest": "evidence.json", "schema_version": 1, "kind": "design_evidence"}
FAMILIES = ["command", "generated_artifact_command"]
RUN = "559e6f45-de4a-4630-a0b5-d68d553797dc"
OTHER_RUN = "9b45224c-3818-44dc-bda0-7c497d89cbfa"


@pytest.fixture
def run(monkeypatch):
    monkeypatch.setenv("SERVO_GATE_RUN_ID", RUN)
    return RUN


def bundle(base, run_id=RUN):
    root = base / CONFIG["root"].replace("{run_id}", run_id)
    root.mkdir(parents=True)
    (root / "capture.png").write_bytes(b"\x89PNG\r\nraw capture")
    (root / "raw.json").write_bytes(b'{ "actual": null, "reason": "unavailable" }\n')
    rows = [{"path": p.name, "hash": rt.file_hash(p)}
            for p in sorted(root.iterdir())]
    manifest = {"schema_version": 1, "kind": "design_evidence",
                "run_id": run_id, "artifacts": rows, "opaque_design_meaning": None}
    (root / "evidence.json").write_text(json.dumps(manifest, indent=2) + "\n")
    reference = {"schema_version": 1, "kind": "command_result_artifacts",
                 "run_id": run_id, "root": root.relative_to(base).as_posix(),
                 "manifest": {"path": "evidence.json",
                              "hash": rt.file_hash(root / "evidence.json")},
                 "artifacts": rows}
    return root, reference


def check(family="command", code=0):
    return {"id": "capture", "family": family, "required": True,
            "command": [sys.executable, "-c",
                        f"import sys; print('concrete acquisition reason', file=sys.stderr); "
                        f"raise SystemExit({code})"],
            "evaluator_artifacts": [], "result_artifact": copy.deepcopy(CONFIG),
            "refusal_exit_codes": [2]}


@pytest.mark.parametrize("family", FAMILIES)
@pytest.mark.parametrize("code,status", [(0, "pass"), (1, "fail"), (2, "env_error")])
def test_command_outcome_preserves_exact_raw_references(tmp_path, run, family, code, status):
    root, reference = bundle(tmp_path)
    config = check(family, code)
    if family == "command":
        (tmp_path / "sub").mkdir()
        config["working_directory"] = "sub"
    evidence = ck.run_check(config, tmp_path)
    assert evidence["status"] == status
    assert evidence["exit_code"] == code
    assert evidence["result_artifact"] == reference
    assert rt.validate_output_references(config, evidence, run, tmp_path) is None
    if code:
        assert "concrete acquisition reason" in evidence["message"]
    assert (root / "evidence.json").is_file()


@pytest.mark.parametrize("family", FAMILIES)
@pytest.mark.parametrize("mode", ["missing", "partial", "extra", "duplicate", "escape",
                                  "symlink", "symlink-dir", "foreign", "wrong-kind",
                                  "bool-version", "unsorted", "self", "bad-hash"])
def test_invalid_output_never_passes_matching_exit(tmp_path, run, family, mode):
    root, _ = bundle(tmp_path)
    path = root / "evidence.json"
    value = rt.load(path)
    if mode == "missing":
        path.unlink()
    elif mode == "partial":
        path.write_text('{"schema_version":')
    elif mode == "extra":
        (root / "unlisted").touch()
    elif mode == "symlink":
        (root / "capture.png").unlink()
        (root / "capture.png").symlink_to(root / "raw.json")
    elif mode == "symlink-dir":
        (root / "link").symlink_to(tmp_path, target_is_directory=True)
    else:
        if mode == "duplicate":
            value["artifacts"].append(value["artifacts"][0])
        elif mode == "escape":
            value["artifacts"][0]["path"] = "../outside"
        elif mode == "foreign":
            value["run_id"] = OTHER_RUN
        elif mode == "wrong-kind":
            value["kind"] = "other"
        elif mode == "bool-version":
            value["schema_version"] = True
        elif mode == "unsorted":
            value["artifacts"].reverse()
        elif mode == "self":
            value["artifacts"].append({"path": "evidence.json", "hash": "sha256:" + "0" * 64})
        elif mode == "bad-hash":
            value["artifacts"][0]["hash"] = "sha256:" + "0" * 64
        path.write_text(json.dumps(value))
    evidence = ck.run_check(check(family), tmp_path)
    assert evidence["status"] == "env_error", (mode, evidence)
    assert evidence["exit_code"] == 0
    assert "result_artifact" not in evidence
    assert "result_artifact" in evidence["message"]


@pytest.mark.parametrize("family", FAMILIES)
@pytest.mark.parametrize("field,value", [
    ("refusal_exit_codes", None), ("refusal_exit_codes", "2"),
    ("refusal_exit_codes", [True]), ("refusal_exit_codes", [2, 2]),
    ("refusal_exit_codes", [0]), ("refusal_exit_codes", [1.5]),
    ("refusal_exit_codes", [3]),
    ("result_artifact", None), ("result_artifact", []),
    ("result_artifact", {**CONFIG, "schema_version": True}),
    ("result_artifact", {**CONFIG, "root": "/tmp/{run_id}"}),
    ("result_artifact", {**CONFIG, "root": "runs/../{run_id}"}),
    ("result_artifact", {**CONFIG, "root": "runs/{other}"}),
    ("result_artifact", {**CONFIG, "root": "runs/fixed"}),
    ("result_artifact", {**CONFIG, "root": "runs/{run_id}/{run_id}"}),
    ("result_artifact", {**CONFIG, "manifest": "../evidence.json"}),
    ("result_artifact", {**CONFIG, "manifest": "./evidence.json"}),
    ("result_artifact", {**CONFIG, "extra": 1}),
])
def test_invalid_options_refuse_before_any_execution(tmp_path, run, monkeypatch, family,
                                                   field, value):
    calls = []
    monkeypatch.setattr(ck, "_run_bounded", lambda *args: calls.append(args))
    config = check(family)
    config["expected"] = {"exit_code": 3}
    config["build_command"] = [sys.executable, "-c", "raise SystemExit(0)"]
    config[field] = value
    evidence = ck.run_check(config, tmp_path)
    assert evidence["status"] == "env_error"
    assert not calls


@pytest.mark.parametrize("bad_run", [None, "bad", RUN.upper()])
@pytest.mark.parametrize("family", FAMILIES)
def test_invalid_current_run_refuses_before_execution(tmp_path, monkeypatch, family, bad_run):
    monkeypatch.delenv("SERVO_GATE_RUN_ID", raising=False)
    if bad_run:
        monkeypatch.setenv("SERVO_GATE_RUN_ID", bad_run)
    calls = []
    monkeypatch.setattr(ck, "_run_bounded", lambda *args: calls.append(args))
    assert ck.run_check(check(family), tmp_path)["status"] == "env_error"
    assert not calls


@pytest.mark.parametrize("family", FAMILIES)
def test_legacy_and_refusal_without_output(tmp_path, monkeypatch, family):
    monkeypatch.delenv("SERVO_GATE_RUN_ID", raising=False)
    config = check(family, 2)
    config.pop("result_artifact")
    config.pop("refusal_exit_codes")
    assert ck.run_check(config, tmp_path)["status"] == "fail"
    config["refusal_exit_codes"] = [2]
    evidence = ck.run_check(config, tmp_path)
    assert evidence["status"] == "env_error"
    assert evidence["exit_code"] == 2
    assert "result_artifact" not in evidence


@pytest.mark.parametrize("family", FAMILIES)
def test_acquisition_refuses_without_fabricating_output(tmp_path, run, family):
    evidence = ck.run_check(check(family, 2), tmp_path)
    assert evidence["status"] == "env_error"
    assert evidence["exit_code"] == 2
    assert "concrete acquisition reason" in evidence["message"]
    assert "result_artifact" not in evidence
    assert rt.validate_output_references(check(family), evidence, run, tmp_path) is None
    with pytest.raises(ValueError):
        rt.validate_output_references(check(family), {**evidence, "status": "pass"}, run, tmp_path)


@pytest.mark.parametrize("mode", ["manifest", "capture", "extra", "missing", "replay",
                                  "ref-root", "ref-hash", "ref-duplicate", "ref-extra",
                                  "symlink-root", "foreign-path"])
def test_pure_readback_rejects_mutation_or_replay(tmp_path, run, mode):
    root, ref = bundle(tmp_path)
    evidence = {"status": "pass", "result_artifact": ref}
    if mode == "manifest":
        (root / "evidence.json").write_bytes((root / "evidence.json").read_bytes() + b" ")
    elif mode == "capture":
        (root / "capture.png").write_bytes(b"changed")
    elif mode == "extra":
        (root / "extra").touch()
    elif mode == "missing":
        (root / "capture.png").unlink()
    elif mode == "replay":
        run = OTHER_RUN
    elif mode == "ref-root":
        ref["root"] = "../" + ref["root"]
    elif mode == "ref-hash":
        ref["manifest"]["hash"] = "sha256:" + "0" * 64
    elif mode == "ref-duplicate":
        ref["artifacts"].append(ref["artifacts"][0])
    elif mode == "ref-extra":
        ref["extra"] = True
    elif mode == "symlink-root":
        moved = root.with_name("moved")
        root.rename(moved)
        root.symlink_to(moved, target_is_directory=True)
    elif mode == "foreign-path":
        ref["artifacts"][0]["path"] = "runs/" + OTHER_RUN + "/capture.png"
    with pytest.raises(ValueError):
        rt.validate_output_references(check(), evidence, run, tmp_path)


def component(tmp_path, monkeypatch, code=0):
    run_id = RUN
    monkeypatch.setenv("SERVO_GATE_RUN_ID", run_id)
    config = check(code=code)
    plan_path = tmp_path / "spec/oracle/card/checks.json"
    entry = {"component": "card", "checks_path": "spec/oracle/card/checks.json",
             "required_ids": ["capture"], "config_hash": "config",
             "evaluator": {"hash": "engine"}, "source_identity": {"hash": "source"}}
    plan = {"checks": [config], "approved_required_binding": entry}
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(json.dumps(plan))
    monkeypatch.setenv("SERVO_REQUIRED_COMPONENT", "card")
    monkeypatch.setenv("SERVO_REQUIRED_RESULT",
                       str(plan_path.parent / "runs" / run_id / "result.json"))
    monkeypatch.setenv("SERVO_REQUIRED_POLICY_HASH", "policy")
    result = ck.run_checks(plan, tmp_path)
    return plan_path, plan, entry, result


@pytest.mark.parametrize("code", [0, 1, 2])
@pytest.mark.parametrize("name", ["evidence.json", "capture.png"])
def test_component_revalidates_outputs_including_fail_and_refusal(tmp_path, monkeypatch,
                                                                code, name):
    root, _ = bundle(tmp_path)
    path, plan, entry, result = component(tmp_path, monkeypatch, code)
    reference = rt.component_result(plan, result, path, Path(ck.__file__))
    (root / name).write_bytes(b"mutated after publication")
    with pytest.raises(ValueError):
        rt.validate_output_references(plan["checks"][0], result["evidence"][0],
                                      RUN, tmp_path)
    required = rt.validate_component(reference, entry, RUN, "policy",
                                     result["summary"]["score"], tmp_path)
    assert required["unknown"] == ["capture"]


def test_component_publication_checks_handler_to_publish_race(tmp_path, monkeypatch):
    root, _ = bundle(tmp_path)
    path, plan, entry, result = component(tmp_path, monkeypatch)
    (root / "capture.png").write_bytes(b"changed after handler")
    reference = rt.component_result(plan, result, path, Path(ck.__file__))
    record = rt.load(reference["path"])
    assert record["required"]["unknown"] == ["capture"]
    assert record["evidence"][0]["exit_code"] == 0
    assert record["evidence"][0]["result_artifact"] == result["evidence"][0]["result_artifact"]
    assert result["summary"]["score"] == 0.0
    assert result["summary"]["env_errors"] == 1
    assert ck.exit_code_for(result["summary"]) == 2
    assert rt.validate_component(
        reference, entry, RUN, "policy", 0.0, tmp_path)["status"] == "unknown"


def test_publication_race_retains_known_failures(tmp_path, monkeypatch):
    root, _ = bundle(tmp_path)
    path, plan, entry, _ = component(tmp_path, monkeypatch, 1)
    plan["checks"].append({
        "id": "known-fail", "family": "command", "required": True,
        "command": [sys.executable, "-c", "raise SystemExit(1)"]})
    entry["required_ids"].append("known-fail")
    path.write_text(json.dumps(plan))
    result = ck.run_checks(plan, tmp_path)
    (root / "capture.png").write_bytes(b"changed before publication")
    reference = rt.component_result(plan, result, path, Path(ck.__file__))
    record = rt.load(reference["path"])
    assert record["required"]["unknown"] == ["capture"]
    assert record["required"]["failed"] == ["known-fail"]
    assert record["evidence"][0]["exit_code"] == 1
    assert "concrete acquisition reason" in record["evidence"][0]["message"]


def test_nonrequired_output_mutation_cannot_leave_component_passing(tmp_path, monkeypatch):
    root, _ = bundle(tmp_path)
    path, plan, entry, _ = component(tmp_path, monkeypatch)
    plan["checks"][0]["required"] = False
    plan["checks"].append({
        "id": "assertion", "family": "command", "required": True,
        "command": [sys.executable, "-c", "raise SystemExit(0)"]})
    entry["required_ids"] = ["assertion"]
    path.write_text(json.dumps(plan))
    result = ck.run_checks(plan, tmp_path)
    reference = rt.component_result(plan, result, path, Path(ck.__file__))
    (root / "capture.png").write_bytes(b"changed optional output")
    with pytest.raises(ValueError):
        rt.validate_component(reference, entry, RUN, "policy", 1.0, tmp_path)


def test_missing_output_refusal_can_publish_component(tmp_path, monkeypatch):
    path, plan, entry, result = component(tmp_path, monkeypatch, 2)
    reference = rt.component_result(plan, result, path, Path(ck.__file__))
    required = rt.validate_component(reference, entry, RUN, "policy", 0.0, tmp_path)
    assert required["unknown"] == ["capture"]
    record = rt.load(reference["path"])
    assert record["evidence"][0]["exit_code"] == 2
    assert "result_artifact" not in record["evidence"][0]


@pytest.fixture
def harness():
    value = installed.InstalledRequiredGateTests()
    value.setUp()
    try:
        yield value
    finally:
        value.doCleanups()


def producer(target, family, code=0):
    config = check(family, code)
    config["command"] = [sys.executable, "-c", f"""
import hashlib, json, os, sys
from pathlib import Path
target = Path({str(target)!r})
run_id = os.environ['SERVO_GATE_RUN_ID']
with (target / 'calls').open('a') as stream:
    stream.write('x')
root = target / {CONFIG['root']!r}.replace('{{run_id}}', run_id)
root.mkdir(parents=True)
(root / 'capture.png').write_bytes(b'actual command bytes')
rows = [{{'path': 'capture.png', 'hash': 'sha256:' + hashlib.sha256(
    (root / 'capture.png').read_bytes()).hexdigest()}}]
(root / 'evidence.json').write_text(json.dumps({{
    'schema_version': 1, 'kind': 'design_evidence', 'run_id': run_id,
    'artifacts': rows}}))
print('concrete acquisition reason', file=sys.stderr)
raise SystemExit({code})
"""]
    return config


@pytest.mark.parametrize("family", FAMILIES)
@pytest.mark.parametrize("code,status", [(0, "pass"), (1, "fail"), (2, "unknown")])
def test_installed_carrier_actual_publication(harness, family, code, status):
    harness.plan["checks"] = [producer(harness.target, family, code)]
    harness.write_plan()
    harness.install_required()
    process, payload = harness.gate(THRESHOLD="0")
    assert process.returncode == code, (process.stderr, payload)
    assert payload["required"]["status"] == status
    reference = next(c["result"] for c in payload["components"] if c["result"])
    record = rt.load(reference["path"])
    evidence = record["evidence"][0]
    assert evidence["exit_code"] == code
    assert evidence["result_artifact"]["run_id"] == payload["run_id"]
    assert record["schema_version"] == 1
    rt.validate_output_references(harness.plan["checks"][0], evidence,
                                  payload["run_id"], harness.target)
    assert (harness.target / "calls").read_text() == "x"


@pytest.mark.parametrize("field,value", [
    ("refusal_exit_codes", [3]),
    ("result_artifact", {**CONFIG, "kind": "changed"}),
])
def test_output_policy_mutation_requires_reapproval(harness, field, value):
    harness.plan["checks"] = [producer(harness.target, "command")]
    harness.write_plan()
    harness.install_required()
    plan_path = harness.out / "checks.json"
    plan = rt.load(plan_path)
    plan["checks"][0][field] = value
    plan_path.write_text(json.dumps(plan))
    process, _ = harness.gate()
    assert process.returncode == 2
    assert not (harness.target / "calls").exists()
    assert ck.plan_content_hash(plan) != plan["approved_content_hash"]


def test_overall_publication_race_refuses_and_retains_other_failure(harness):
    harness.plan["checks"] = [producer(harness.target, "command"), {
        "id": "known-fail", "family": "command", "required": True,
        "command": [sys.executable, "-c", "raise SystemExit(1)"],
        "evaluator_artifacts": []}]
    harness.write_plan()
    harness.install_required()

    def intercepted(oracle, target, timeout, env):
        process = subprocess.run([str(oracle)], cwd=target, env=env,
                                 capture_output=True, text=True, timeout=30)
        root = target / CONFIG["root"].replace("{run_id}", env["SERVO_GATE_RUN_ID"])
        (root / "capture.png").write_bytes(b"changed before overall publication")
        return process.stdout, process.stderr, process.returncode, False

    output = io.StringIO()
    with redirect_stdout(output):
        code = rt.run_gate(harness.target, intercepted, 30, True, False)
    payload = json.loads(output.getvalue())
    assert code == 2
    assert "capture" in payload["required"]["unknown"]
    assert "known-fail" in payload["required"]["failed"]


def test_pure_validator_does_not_execute_or_change_files(tmp_path, run, monkeypatch):
    _, ref = bundle(tmp_path)
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("must be pure"))
    rt.validate_output_references(check(), {"status": "fail", "result_artifact": ref},
                                  run, tmp_path)
    assert before == {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}


@pytest.mark.parametrize("family", FAMILIES)
def test_foreign_run_directory_is_not_part_of_current_output(tmp_path, run, family):
    root, _ = bundle(tmp_path)
    (root / "runs" / OTHER_RUN).mkdir(parents=True)
    assert ck.run_check(check(family), tmp_path)["status"] == "env_error"


def test_invalid_reference_type_raises_value_error(tmp_path, run):
    _, ref = bundle(tmp_path)
    ref["manifest"]["hash"] = object()
    with pytest.raises(ValueError):
        rt.validate_output_references(check(), {"status": "pass", "result_artifact": ref},
                                      run, tmp_path)


@pytest.mark.parametrize("name", ["capture.png", "evidence.json"])
def test_acquisition_snapshot_race_refuses(tmp_path, run, monkeypatch, name):
    root, ref = bundle(tmp_path)
    original = rt._output_snapshot
    calls = []

    def intercepted(*args):
        value = original(*args)
        calls.append(True)
        if len(calls) == 1:
            (root / name).write_bytes(b"changed between inventory snapshots")
        return value

    monkeypatch.setattr(rt, "_output_snapshot", intercepted)
    with pytest.raises(ValueError):
        rt.validate_output_references(check(), {"status": "pass", "result_artifact": ref},
                                      run, tmp_path)


@pytest.mark.parametrize("family", FAMILIES)
@pytest.mark.parametrize("fault", ["not-found", "timeout"])
def test_acquisition_error_without_output_is_honest(tmp_path, run, monkeypatch, family, fault):
    result = ck._CommandResult(-15 if fault == "timeout" else None, "", "raw reason",
                               timed_out=fault == "timeout", not_found=fault == "not-found")
    calls = []

    def bounded(*args):
        calls.append(args)
        return result

    monkeypatch.setattr(ck, "_run_bounded", bounded)
    evidence = ck.run_check(check(family), tmp_path)
    assert evidence["status"] == "env_error"
    assert "result_artifact" not in evidence
    assert len(calls) == 1
    rt.validate_output_references(check(family), evidence, run, tmp_path)


def test_working_directory_does_not_change_publication_base(tmp_path, monkeypatch):
    bundle(tmp_path)
    path, plan, entry, _ = component(tmp_path, monkeypatch)
    (tmp_path / "sub").mkdir()
    plan["checks"][0]["working_directory"] = "sub"
    path.write_text(json.dumps(plan))
    monkeypatch.chdir(tmp_path / "sub")
    result = ck.run_checks(plan, tmp_path)
    ref = rt.component_result(plan, result, path, Path(ck.__file__))
    assert rt.validate_component(ref, entry, RUN, "policy", 1.0, tmp_path)["status"] == "pass"
