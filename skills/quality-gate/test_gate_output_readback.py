"""Preserved declared-output closure through native pure readers."""
import builtins
import copy
import importlib._bootstrap_external
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


outputs = module("readback_output_fixtures", "skills/spec-oracle/test_result_artifacts.py")
rt = outputs.rt


@pytest.fixture
def harness():
    value = outputs.installed.InstalledRequiredGateTests()
    value.setUp()
    try:
        yield value
    finally:
        value.doCleanups()


def reader():
    return module("output_gate_consumer", "skills/quality-gate/gate_consumer.py")


def published(harness, family="command", code=0, *, claim=True, required=True):
    harness.plan["checks"] = [outputs.producer(harness.target, family, code)]
    harness.plan["checks"][0]["required"] = required
    if not required:
        harness.plan["checks"].append({
            "id": "assertion", "family": "command", "required": True,
            "command": [sys.executable, "-c", "raise SystemExit(0)"],
            "evaluator_artifacts": [],
        })
    harness.write_plan()
    harness.install_required()
    consumer = reader()
    run_id, env = consumer.request(harness.target)
    process = harness.cli("quality-gate/gate.py", str(harness.target), "--json",
                          env={**os.environ, **env, "THRESHOLD": "0"})
    payload = json.loads(process.stdout)
    assert process.returncode == code, (process.stderr, payload)
    path = harness.target / ".servo/gate-runs" / run_id / "gate.json"
    accepted = (consumer.accept(harness.target, payload, process.returncode, run_id) if claim
                else {"oracle": payload, "gate_ref": {"path": str(path),
                                                     "hash": rt.file_hash(path)},
                      **payload})
    assert accepted["exit_code"] == code, accepted
    component = next(c["result"] for c in payload["components"] if c["result"])
    record = rt.load(component["path"])
    root = harness.target / record["evidence"][0]["result_artifact"]["root"]
    return consumer, accepted, root, component


def reseal_synthetic(accepted, component, record):
    path = Path(component["path"])
    path.write_bytes(rt.canonical(record))
    payload = copy.deepcopy(accepted["oracle"])
    next(c["result"] for c in payload["components"] if c["result"])["hash"] = rt.file_hash(path)
    gate = Path(accepted["gate_ref"]["path"])
    gate.write_bytes(rt.canonical(payload))
    return {"oracle": payload, "gate_ref": {"path": str(gate), "hash": rt.file_hash(gate)}}


@pytest.mark.parametrize("family", outputs.FAMILIES)
@pytest.mark.parametrize("mutation", [
    "capture", "envelope", "partial", "missing-envelope", "missing-capture",
    "unlisted", "duplicate", "foreign-run", "foreign-path", "escape",
    "symlink-file", "symlink-dir", "symlink-root",
])
def test_postpublication_output_mutation_refuses_with_original_gate(
        harness, family, mutation):
    consumer, accepted, root, component = published(harness, family)
    original_gate = Path(accepted["gate_ref"]["path"]).read_bytes()
    original_component = Path(component["path"]).read_bytes()
    manifest = root / "evidence.json"
    value = rt.load(manifest)
    if mutation == "capture":
        (root / "capture.png").write_bytes(b"mutated after publication")
    elif mutation == "envelope":
        manifest.write_bytes(manifest.read_bytes() + b"\n")
    elif mutation == "partial":
        manifest.write_text('{"schema_version":')
    elif mutation == "missing-envelope":
        manifest.unlink()
    elif mutation == "missing-capture":
        (root / "capture.png").unlink()
    elif mutation == "unlisted":
        (root / "unlisted").touch()
    elif mutation == "symlink-file":
        (root / "capture.png").unlink()
        (root / "capture.png").symlink_to(manifest)
    elif mutation == "symlink-dir":
        (root / "linked").symlink_to(harness.target, target_is_directory=True)
    elif mutation == "symlink-root":
        moved = root.with_name("moved")
        root.rename(moved)
        root.symlink_to(moved, target_is_directory=True)
    else:
        if mutation == "duplicate":
            value["artifacts"].append(value["artifacts"][0])
        elif mutation == "foreign-run":
            value["run_id"] = outputs.OTHER_RUN
        elif mutation == "foreign-path":
            value["artifacts"][0]["path"] = outputs.OTHER_RUN + "/capture.png"
        elif mutation == "escape":
            value["artifacts"][0]["path"] = "../capture.png"
        manifest.write_text(json.dumps(value))
    result = consumer.read(harness.target, accepted)
    assert result["exit_code"] == 2, result
    assert result["status"] == "env_error"
    assert result["reason"] == "required_evidence_unavailable"
    assert result["composite"] is None
    assert result["oracle"] == accepted["oracle"]
    assert result["gate_ref"] == accepted["gate_ref"]
    assert result["consumer_error"]
    assert consumer.fields(result)["oracle_reason"] == "required_evidence_unavailable"
    assert Path(accepted["gate_ref"]["path"]).read_bytes() == original_gate
    assert Path(component["path"]).read_bytes() == original_component
    assert (harness.target / "calls").read_text() == "x"


def test_complete_frozen_arguments_and_repeated_reads_are_pure(harness, monkeypatch):
    consumer, accepted, _, component = published(harness)
    plan = rt.load(harness.out / "checks.json")
    raw = rt.load(component["path"])["evidence"][0]
    before = {p: p.read_bytes() for p in harness.target.rglob("*") if p.is_file()}
    calls = []
    validate = consumer.pins.validate_output_references

    def capture(check, evidence, run_id, base):
        calls.append((check, evidence, run_id, base))
        return validate(check, evidence, run_id, base)

    def forbidden(*args, **kwargs):
        pytest.fail("readback must not execute or grade")

    monkeypatch.setattr(consumer.pins, "validate_output_references", capture)
    monkeypatch.setattr(consumer.pins, "validate_component", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    for _ in range(2):
        assert consumer.read(harness.target, accepted)["exit_code"] == 0
    assert calls == [(plan["checks"][0], raw, accepted["run_id"], harness.target.resolve())] * 2
    assert before == {p: p.read_bytes() for p in harness.target.rglob("*") if p.is_file()}


def poison_cache(path):
    cache = Path(importlib.util.cache_from_source(str(path)))
    cache.parent.mkdir(exist_ok=True)
    source = compile("raise AssertionError('cached identity executed')", str(path), "exec")
    state = path.stat()
    cache.write_bytes(importlib._bootstrap_external._code_to_timestamp_pyc(
        source, int(state.st_mtime), state.st_size))
    return cache


@pytest.mark.parametrize("cache_mode", ["cold", "forged", "transitive"])
def test_native_read_uses_verified_source_without_cache_io(harness, monkeypatch, cache_mode):
    overlay = harness.overlay

    def vendor(operation, *extra):
        flags = ("--vendor-engine",) if operation in ("generate", "install") else ()
        return overlay(operation, *extra, *flags)

    monkeypatch.setattr(harness, "overlay", vendor)
    consumer, accepted, _, _ = published(harness)
    engine = harness.out / "checks.py"
    cache = Path(importlib.util.cache_from_source(str(engine)))
    if cache.exists():
        cache.unlink()
    if cache_mode == "forged":
        poison_cache(engine)
    if cache_mode == "transitive":
        dependency = harness.target / "cold_identity_dependency.py"
        dependency.write_text("VALUE = 1\n")
        monkeypatch.syspath_prepend(str(harness.target))
        imported = builtins.__import__

        def cold_import(name, *args, **kwargs):
            if name == "tarfile":
                imported("cold_identity_dependency")
            return imported(name, *args, **kwargs)

        monkeypatch.delitem(sys.modules, "cold_identity_dependency", raising=False)
        monkeypatch.setattr(builtins, "__import__", cold_import)
    before = {p: p.read_bytes() for p in harness.target.rglob("*") if p.is_file()}
    monkeypatch.setattr(sys, "dont_write_bytecode", False)

    def forbidden(*args, **kwargs):
        pytest.fail("native readback must not execute commands or grade")

    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(consumer.pins, "validate_component", forbidden)
    for _ in range(2):
        assert consumer.read(harness.target, accepted)["exit_code"] == 0
    assert sys.dont_write_bytecode is False
    assert before == {p: p.read_bytes() for p in harness.target.rglob("*") if p.is_file()}


@pytest.mark.parametrize("cache_mode", ["cold", "forged"])
def test_consumer_carrier_bootstrap_ignores_bytecode_cache(tmp_path, monkeypatch, cache_mode):
    for name in ("gate_consumer.py", "required_runtime.py"):
        (tmp_path / name).write_bytes((ROOT / "skills/quality-gate" / name).read_bytes())
    if cache_mode == "forged":
        poison_cache(tmp_path / "required_runtime.py")
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    monkeypatch.setattr(sys, "dont_write_bytecode", False)
    namespace = {"__name__": "cold_consumer", "__file__": str(tmp_path / "gate_consumer.py")}
    exec(compile((tmp_path / "gate_consumer.py").read_bytes(), namespace["__file__"], "exec"),
         namespace)
    assert namespace["pins"].finite(1) == 1
    assert before == {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}


def test_source_loader_restores_bytecode_policy_after_failed_import(tmp_path, monkeypatch):
    consumer = reader()
    path = tmp_path / "invalid_identity.py"
    path.write_text("raise ValueError('invalid identity helper')\n")
    monkeypatch.setattr(sys, "dont_write_bytecode", False)
    with pytest.raises(ValueError, match="invalid identity helper"):
        consumer._source_module("invalid_identity", path, rt.file_hash(path))
    assert sys.dont_write_bytecode is False


def test_live_acceptance_checks_outputs_before_exclusive_marker(harness):
    consumer, published_record, root, _ = published(harness, claim=False)
    payload = published_record["oracle"]
    capture = root / "capture.png"
    original = capture.read_bytes()
    capture.write_bytes(b"changed before first live acceptance")
    result = consumer.accept(harness.target, payload, 0, payload["run_id"])
    assert result["exit_code"] == 2
    assert "result_artifact" in result["consumer_error"]
    marker = Path(published_record["gate_ref"]["path"]).with_name("consumer-accepted.json")
    assert not marker.exists()
    capture.write_bytes(original)  # throwaway synthetic fixture, not historical evidence
    accepted = consumer.accept(harness.target, payload, 0, payload["run_id"])
    assert accepted["exit_code"] == 0
    marker_bytes = marker.read_bytes()
    assert consumer.accept(harness.target, payload, 0, payload["run_id"])["exit_code"] == 2
    assert consumer.accept(harness.target, payload, 0, outputs.OTHER_RUN)["exit_code"] == 2
    assert consumer.read(harness.target, accepted)["exit_code"] == 0
    assert marker.read_bytes() == marker_bytes


@pytest.mark.parametrize("code", [1, 2])
def test_failure_and_refusal_output_mutation_keep_raw_cause(harness, code):
    consumer, accepted, root, _ = published(harness, code=code)
    assert consumer.read(harness.target, accepted)["exit_code"] == code
    (root / "capture.png").write_bytes(b"changed failing/refused output")
    result = consumer.read(harness.target, accepted)
    assert result["exit_code"] == 2
    assert result["oracle"] == accepted["oracle"]
    assert result["oracle"]["reason"] == (
        "required_constraints_failed" if code == 1 else "required_evidence_unavailable")
    assert result["gate_ref"] == accepted["gate_ref"]


def test_optional_declared_output_is_also_bound(harness):
    consumer, accepted, root, _ = published(harness, required=False)
    assert accepted["required"]["ids"] == ["assertion"]
    (root / "capture.png").write_bytes(b"changed optional output")
    assert consumer.read(harness.target, accepted)["exit_code"] == 2


@pytest.mark.parametrize("mutation", [
    "omitted", "duplicate", "extra", "missing-reference", "foreign-reference",
])
def test_declared_outputs_require_exact_evidence_inventory(harness, mutation):
    consumer, accepted, _, component = published(harness)
    record = rt.load(component["path"])
    if mutation == "omitted":
        record["evidence"] = []
    elif mutation == "duplicate":
        record["evidence"].append(copy.deepcopy(record["evidence"][0]))
    elif mutation == "extra":
        record["evidence"].append({**record["evidence"][0], "check_id": "unapproved"})
    elif mutation == "missing-reference":
        record["evidence"][0].pop("result_artifact")
    else:
        record["evidence"][0]["result_artifact"]["run_id"] = outputs.OTHER_RUN
    # Deliberately malformed synthetic carrier with consistent outer byte refs
    # isolates inventory checking; this does not authenticate malicious writers.
    malformed = reseal_synthetic(accepted, component, record)
    result = consumer.read(harness.target, malformed)
    assert result["exit_code"] == 2
    assert result["oracle"] == malformed["oracle"]
    assert result["gate_ref"] == malformed["gate_ref"]
    assert any(message in result["consumer_error"] for message in (
        "evidence ID", "references missing", "identity/digest mismatch"))


def test_missing_output_on_honest_acquisition_refusal_is_not_fabricated(harness):
    check = outputs.check(code=2)
    harness.plan["checks"] = [check]
    harness.write_plan()
    harness.install_required()
    process, payload = harness.gate(THRESHOLD="0")
    assert process.returncode == 2
    component = next(c["result"] for c in payload["components"] if c["result"])
    assert "result_artifact" not in rt.load(component["path"])["evidence"][0]
    path = harness.target / ".servo/gate-runs" / payload["run_id"] / "gate.json"
    record = {"oracle": payload, "gate_ref": {"path": str(path), "hash": rt.file_hash(path)}}
    result = reader().read(harness.target, record)
    assert result["exit_code"] == 2
    assert result["required"]["unknown"] == ["capture"]
    assert result["oracle"] == payload
    assert result["gate_ref"] == record["gate_ref"]
    assert "consumer_error" not in result
    assert not (harness.target / check["result_artifact"]["root"].replace(
        "{run_id}", payload["run_id"])).exists()


def test_triage_reports_refuse_mutated_capture_without_erasing_overall(harness):
    consumer, accepted, root, component = published(harness)
    heartbeat = module("output_heartbeat", "skills/heartbeat/heartbeat.py")
    summary = {**accepted, "final_oracle_status": "pass", "cumulative_cost_usd": 0.25}
    outcome = heartbeat._outcome_from_summary(summary, target=harness.target)
    assert outcome["oracle_status"] == "pass"
    inbox = harness.target / ".servo/triage/inbox.jsonl"
    inbox.parent.mkdir()
    entry = {"schema_version": heartbeat.SCHEMA_VERSION, "finding_id": "capture",
             "title": "bound output", "status": "passed", "outcome": outcome}
    inbox.write_text(json.dumps(entry) + "\n")
    original_inbox = inbox.read_bytes()
    original_component = Path(component["path"]).read_bytes()
    (root / "capture.png").write_bytes(b"changed after passing final handoff")
    for _ in range(2):
        records, cause = heartbeat._read_inbox_for_status(inbox)
        assert cause is None
        report = records[0]
        assert report["status"] == "tried"
        assert report["outcome"]["oracle_status"] == "env_error"
        assert report["outcome"]["oracle_composite"] is None
        assert report["outcome"]["oracle"] == accepted["oracle"]
        assert report["outcome"]["gate_ref"] == accepted["gate_ref"]
        assert report["outcome"]["oracle_reason"] == "required_evidence_unavailable"
        assert report["outcome"]["cost_usd"] == 0.25
        assert report["outcome"]["dispatched_at"] == outcome["dispatched_at"]
    assert inbox.read_bytes() == original_inbox
    assert Path(component["path"]).read_bytes() == original_component
    assert consumer.read(harness.target, accepted)["exit_code"] == 2


def test_valid_earlier_output_cannot_clear_later_final_unavailability(harness):
    _, accepted, _, _ = published(harness)
    heartbeat = module("unavailable_output_heartbeat", "skills/heartbeat/heartbeat.py")
    for status in ("env_error", "unknown_interrupted"):
        outcome = heartbeat._outcome_from_summary(
            {**accepted, "final_oracle_status": status}, target=harness.target)
        assert outcome["oracle_status"] == status
        assert outcome["oracle_composite"] is None
        assert outcome["oracle"] == accepted["oracle"]
        assert outcome["gate_ref"] == accepted["gate_ref"]


@pytest.mark.parametrize("package", [
    "hosts/claude", "hosts/codex/plugins/servo", "hosts/copilot/.github", "vendor",
])
def test_generated_and_vendored_readers_close_same_output(harness, package):
    _, accepted, root, _ = published(harness)
    if package == "vendor":
        loop = module("output_vendor_loop", "skills/agent-loop/loop.py")
        gate, error = loop._ensure_vendored_gate(harness.target)
        assert error is None
        path = gate.with_name("gate_consumer.py")
    else:
        path = ROOT / package / "skills/quality-gate/gate_consumer.py"
    assert path.read_bytes() == (ROOT / "skills/quality-gate/gate_consumer.py").read_bytes()
    consumer = module("packaged_output_consumer", path)
    assert consumer.read(harness.target, accepted)["exit_code"] == 0
    (root / "capture.png").write_bytes(b"postpublication package readback mutation")
    result = consumer.read(harness.target, accepted)
    assert result["exit_code"] == 2
    assert result["oracle"] == accepted["oracle"]
    assert result["gate_ref"] == accepted["gate_ref"]


def test_output_contract_config_drift_is_rejected_before_using_validator(harness, monkeypatch):
    consumer, accepted, _, _ = published(harness)
    path = harness.out / "checks.json"
    plan = rt.load(path)
    plan["checks"][0]["result_artifact"]["kind"] = "unapproved"
    path.write_text(json.dumps(plan))

    def forbidden(*args):
        pytest.fail("unapproved check must not reach output validator")

    monkeypatch.setattr(consumer.pins, "validate_output_references", forbidden)
    result = consumer.read(harness.target, accepted)
    assert result["exit_code"] == 2
    assert "config content differs" in result["consumer_error"]
    assert result["oracle"] == accepted["oracle"]


def test_residual_evidence_is_in_exact_inventory_without_judging(harness):
    harness.plan["residual_judgment"] = [
        {"id": "manual-review", "statement": "Unbound manual diagnostic", "required": False}]
    consumer, accepted, _, component = published(harness)
    record = rt.load(component["path"])
    residual = next(e for e in record["evidence"] if e["check_id"] == "manual-review")
    assert residual["status"] == "not_applicable"
    assert consumer.read(harness.target, accepted)["exit_code"] == 0
    record["evidence"].remove(residual)
    malformed = reseal_synthetic(accepted, component, record)
    result = consumer.read(harness.target, malformed)
    assert result["exit_code"] == 2
    assert "evidence ID" in result["consumer_error"]
    assert result["oracle"] == malformed["oracle"]
