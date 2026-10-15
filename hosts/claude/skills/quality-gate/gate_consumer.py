"""Read installed overall gate authority, never evaluate or rescore evidence.

Gate versions and checkpoint/report versions are separate namespaces. New live
invocations own a fresh UUID; immutable report rereads do not claim it again.
Source identity is approved provenance, not delivered/served-build attestation.
"""
import importlib.util
import json
import uuid
from pathlib import Path

# Load only the stdlib carrier's read-only identity helpers. This works both
# beside gate.py in a project vendor and in a host's sibling skill directory.
_spec = importlib.util.spec_from_file_location(
    "_consumer_pins", Path(__file__).with_name("required_runtime.py"))
pins = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pins)


def parse(text):
    """Strict JSON for live v2 carriers (including their stdout copy)."""
    def invalid(value):
        raise ValueError("non-finite JSON: " + value)
    return json.loads(text, object_pairs_hook=pins._pairs, parse_constant=invalid)


def request(target):
    run_id = str(uuid.uuid4())
    directory = Path(target).resolve() / ".servo/gate-runs" / run_id
    if directory.exists():
        raise ValueError("gate invocation destination already exists")
    return run_id, {"SERVO_GATE_RUN_ID": run_id, "SERVO_GATE_RESULT_DIR": str(directory)}


def _refuse(payload, message, reference=None):
    """Retain the *original* payload, including any known contradictions."""
    return {
        "schema_version": 2, "status": "env_error", "exit_code": 2,
        "reason": "required_evidence_unavailable", "composite": None,
        "threshold": payload.get("threshold") if isinstance(payload, dict) else None,
        "oracle": payload, "gate_ref": reference, "consumer_error": str(message),
    }


def _version(payload):
    if not isinstance(payload, dict) or type(payload.get("schema_version")) is not int:
        raise ValueError("missing gate payload version")
    version = payload["schema_version"]
    if version not in (1, 2):
        raise ValueError("unsupported gate payload version: " + str(version))
    code = payload.get("exit_code")
    statuses = {0: "pass", 1: "fail" if version == 2 else "below_threshold", 2: "env_error"}
    if type(code) is not int or payload.get("status") != statuses.get(code):
        raise ValueError("gate exit/status mismatch")
    return version


def _bound_file(reference, expected):
    if (not isinstance(reference, dict) or set(reference) != {"path", "hash"}
            or Path(reference["path"]).resolve() != expected.resolve()
            or pins.file_hash(expected) != reference["hash"]):
        raise ValueError("missing/mutated evidence digest or destination: " + str(expected))
    return pins.load(expected)


def _validate(target, payload, reference):
    """Check the original carrier and mandatory bindings without re-grading."""
    run_id = payload["run_id"]
    if str(uuid.UUID(run_id)) != run_id or payload.get("kind") != "gate_result":
        raise ValueError("invalid overall gate identity")
    expected = target / ".servo/gate-runs" / run_id / "gate.json"
    published = _bound_file(reference, expected)
    if pins.canonical(published) != pins.canonical(payload):
        raise ValueError("overall payload differs from published gate bytes")
    policy, policy_hash = pins.installed_policy(target)
    if payload.get("policy_hash") != policy_hash:
        raise ValueError("gate policy identity is not the current installed approval")
    driver = (target / "oracle.sh").read_text()
    if (not driver.endswith(pins.DRIVER)
            or pins.driver_identity(driver[:-len(pins.DRIVER)]) != policy["driver_prefix_hash"]):
        raise ValueError("current installed required driver differs")
    required = payload["required"]
    if required["status"] not in ("pass", "fail", "unknown"):
        raise ValueError("invalid required status")
    if payload["exit_code"] == 2:
        if payload.get("reason") != "required_evidence_unavailable":
            raise ValueError("invalid refusal reason")
    elif (payload["exit_code"] == 0 and (
            payload.get("reason") is not None or required["status"] != "pass")):
        raise ValueError("invalid overall pass")
    elif payload["exit_code"] == 1 and payload.get("reason") not in (
            "required_constraints_failed", "quality_below_threshold",
            "required_and_quality_failed"):
        raise ValueError("invalid overall failure reason")
    components = payload["components"]
    by_name = {c["component"]: c for c in components}
    if len(by_name) != len(components):
        raise ValueError("duplicate component")
    for entry in policy["components"]:
        component = by_name.get(entry["component"])
        ref = component.get("result") if component else None
        # Published env_error records legitimately lack unavailable refs. They
        # remain refusal; absence cannot promote them or erase their raw causes.
        if payload["exit_code"] == 2 and (not ref or not ref.get("hash")):
            continue
        path = (target / entry["checks_path"]).parent / "runs" / run_id / "result.json"
        record = _bound_file(ref, path)
        identities = {
            "schema_version": 1, "kind": "required_component_result", "run_id": run_id,
            "component": entry["component"], "policy_hash": policy_hash,
            "config_hash": entry["config_hash"], "evaluator_hash": entry["evaluator"]["hash"],
            "source_identity": entry["source_identity"],
        }
        for key, value in identities.items():
            if type(record.get(key)) is not type(value) or record[key] != value:
                raise ValueError("component binding mismatch: " + key)
        if record["score"] != component["score"]:
            raise ValueError("component diagnostic differs from overall record")
        if sorted(record["required"]["ids"]) != entry["required_ids"]:
            raise ValueError("component required set mismatch")
        plan = pins.load(target / entry["checks_path"])
        if (plan.get("approved_required_binding") != entry
                or plan.get("approval_status") != "approved"
                or plan.get("approved_content_hash") != entry["config_hash"]
                or entry["source_identity"] != {
                    "path": plan.get("source_spec_path"), "hash": plan.get("source_hash")}):
            raise ValueError("current approved config/source binding differs")
        pins.check_pins([entry["evaluator"], entry["required_runtime"]]
                        + entry["evaluator_artifacts"], target)
        # Reuse the approved evaluator's existing pure content-identity helper,
        # not its run/check/score functions. A remembered approved_hash field
        # alone cannot detect honest edits to the frozen check bodies.
        identity_spec = importlib.util.spec_from_file_location(
            "_approved_config_identity", target / entry["evaluator"]["path"])
        identity = importlib.util.module_from_spec(identity_spec)
        identity_spec.loader.exec_module(identity)
        if identity.plan_content_hash(plan) != entry["config_hash"]:
            raise ValueError("current approved config content differs")
        fragment = (target / entry["checks_path"]).parent / "oracle.sh.fragment"
        if (pins.file_hash(fragment) != entry["fragment_hash"]
                or fragment.read_text().rstrip() not in (target / "oracle.sh").read_text()):
            raise ValueError("live required fragment differs")
        # Compare interpreted channels as published, not observations or grades.
        for item in record["required"]["items"]:
            if {**item, "component": entry["component"]} not in required["items"]:
                raise ValueError("component required item missing from overall carrier")


_INVALID = (OSError, ValueError, KeyError, TypeError, AttributeError, IndexError)


def accept(target, payload, returncode, run_id):
    """Accept exactly this invocation once. No latest pointers or scalar trust."""
    target = Path(target).resolve()
    reference = None
    try:
        if (isinstance(payload, dict) and "schema_version" not in payload
                and "required" not in payload and "kind" not in payload
                and not pins.enabled(target) and type(payload.get("exit_code")) is int
                and payload["exit_code"] in (0, 1, 2) and payload["exit_code"] == returncode):
            return payload  # legacy no-policy gateway adapter, not a v2 downgrade
        version = _version(payload)
        if returncode != payload["exit_code"]:
            raise ValueError("gate subprocess exit differs from payload")
        if version == 1:
            if pins.enabled(target):
                raise ValueError("enabled policy cannot downgrade to gate v1")
            return payload
        if payload.get("run_id") != run_id:
            raise ValueError("stale/replayed gate invocation")
        path = target / ".servo/gate-runs" / run_id / "gate.json"
        reference = {"path": str(path), "hash": pins.file_hash(path)}
        _validate(target, payload, reference)
        # Exclusive consumer claim, distinct from producer publication. Reports
        # use read(), so multiple reports may inspect the same immutable run.
        pins.publish(path.with_name("consumer-accepted.json"), reference)
        return {**payload, "oracle": payload, "gate_ref": reference}
    except _INVALID as exc:
        return _refuse(payload, exc, reference)


def read(target, record, *, require_v2=False):
    """Revalidate a recorded oracle + gate_ref without claiming or executing."""
    if not isinstance(record, dict):
        return _refuse(record, "invalid consumer record")
    payload = record.get("oracle", record)
    reference = record.get("gate_ref")
    try:
        if record.get("consumer_error"):
            raise ValueError(record["consumer_error"])  # invalid acceptance stays refused
        if _version(payload) == 1:
            if require_v2:
                raise ValueError("enabled dispatch requires an overall gate v2 carrier")
            return payload  # historical v1 remains historical, no auto-upgrade
        _validate(Path(target).resolve(), payload, reference)
        return {**payload, "oracle": payload, "gate_ref": reference}
    except _INVALID as exc:
        return _refuse(payload, exc, reference)


def fields(result):
    """Additive consumer record fields; original v1 shapes stay unchanged."""
    if "oracle" not in result:
        return {}
    return {
        **{key: result[key] for key in ("oracle", "gate_ref", "consumer_error") if key in result},
        "oracle_reason": result.get("oracle_reason", result.get("reason")),
    }


def record_target(record, fallback):
    """A retained dispatch reports the original worktree, not the inbox root."""
    reference = record.get("gate_ref") or {}
    if not isinstance(reference, dict) or not isinstance(reference.get("path", ""), str):
        return Path(fallback)
    path = Path(reference.get("path") or "")
    if (path.is_absolute() and len(path.parents) >= 4 and path.name == "gate.json"
            and path.parent.parent.name == "gate-runs" and path.parents[2].name == ".servo"):
        return path.parents[3]
    return Path(fallback)


def guidance(result):
    raw = result.get("oracle") or result
    required = raw.get("required") if isinstance(raw, dict) else None
    required = required if isinstance(required, dict) else {}
    entries = required.get("items")
    entries = entries if isinstance(entries, list) else []
    items = "; ".join("{}: {} ({})".format(i.get("id"), i.get("status"), i.get("reason"))
                      for i in entries if isinstance(i, dict))
    reference = result.get("gate_ref") or {}
    reference = reference if isinstance(reference, dict) else {}
    if result.get("exit_code") == 2:
        action = "Repair evidence acquisition/bindings, then rerun; completion is unavailable."
    else:
        action = "Inspect the assertion evidence, repair the implementation, then rerun the gate."
    return "{}. {} {} gate={} hash={}. Policy changes require reviewed reapproval.".format(
        result.get("reason"), items, action, reference.get("path"), reference.get("hash"))
