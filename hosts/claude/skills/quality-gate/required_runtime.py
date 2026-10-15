"""Opt-in required policy and invocation carrier (stdlib, Python >=3.9).

No producer registry: approved components publish a closed evidence set from
their ordinary scalar invocation. The overall gate, never a component, decides.
"""
import hashlib
import json
import math
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

MARKER = "# SERVO_REQUIRED_DRIVER:1"
DRIVER = '''# SERVO_REQUIRED_DRIVER:1
exec python3 ".servo/required_runtime.py" oracle "$0"
'''


def driver_identity(prefix):
    value = re.sub(r"^COMPONENTS=\(.*?^\)", "COMPONENTS=()", prefix, flags=re.S | re.M)
    value = re.sub(r"^# SEED:start [^\n]+\n.*?^# SEED:end [^\n]+", "", value,
                   flags=re.S | re.M)
    value = value.replace("{{SEED_BLOCKS}}", "")
    value = re.sub(r"^# \(no SEED blocks.*\n", "", value, flags=re.M)
    return digest("\n".join(line for line in value.splitlines() if line.strip()).encode())


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def digest(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def file_hash(path):
    return digest(Path(path).read_bytes())


def policy_path(path, base):
    """Project-local identity paths relocate; shared/external paths stay exact."""
    path = Path(path).resolve()
    try:
        return str(path.relative_to(base.resolve()))
    except ValueError:
        return str(path)


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key: " + key)
        result[key] = value
    return result


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"),
                      object_pairs_hook=_pairs,
                      parse_constant=lambda x: (_ for _ in ()).throw(
                          ValueError("non-finite JSON: " + x)))


def _output_path(value):
    """Canonical relative POSIX spelling, without expansion or traversal."""
    if (not isinstance(value, str) or not value or "\\" in value
            or "\0" in value or "{" in value or "}" in value
            or any(p in ("", ".", "..") for p in value.split("/"))):
        raise ValueError("result_artifact needs normalized relative POSIX paths")
    return value


def _output_contract(check, run_id):
    if "result_artifact" not in check:
        return None
    config = check["result_artifact"]
    if (not isinstance(config, dict)
            or set(config) != {"root", "manifest", "schema_version", "kind"}
            or type(config["schema_version"]) is not int
            or not isinstance(config["kind"], str) or not config["kind"].strip()):
        raise ValueError("invalid result_artifact configuration")
    if not isinstance(run_id, str) or str(uuid.UUID(run_id)) != run_id:
        raise ValueError("result_artifact needs current canonical gate run UUID")
    root = config["root"]
    if (not isinstance(root, str)
            or root.split("/").count("{run_id}") != 1):
        raise ValueError("result_artifact root needs one {run_id} segment")
    root = _output_path(root.replace("{run_id}", run_id))
    manifest = _output_path(config["manifest"])
    _output_run_paths([root, manifest], run_id)
    return {**config, "root": root, "manifest": manifest}


def _output_run_paths(paths, run_id):
    for path in paths:
        for part in path.split("/"):
            if re.fullmatch(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", part):
                if part != run_id:
                    raise ValueError("foreign run in result_artifact path")


def _output_rows(rows, run_id):
    if not isinstance(rows, list):
        raise ValueError("result_artifact artifacts must be a list")
    paths = []
    for row in rows:
        if (not isinstance(row, dict) or set(row) != {"path", "hash"}
                or not isinstance(row["hash"], str)
                or not re.fullmatch(r"sha256:[0-9a-f]{64}", row["hash"])):
            raise ValueError("invalid result_artifact file reference")
        paths.append(_output_path(row["path"]))
    if paths != sorted(set(paths)):
        raise ValueError("result_artifact paths must be sorted and unique")
    _output_run_paths(paths, run_id)


def _output_snapshot(base, root, manifest):
    """Read a closed tree with no-follow directory-relative file descriptors.

    Two independent snapshots catch changes while collecting references. fstat
    and named-entry checks also reject replacement during an individual read.
    Only the manifest bytes are retained; other files are streamed into hashes.
    """
    files, directories, raw = {}, [], None
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK

    def identity(info):
        return (info.st_dev, info.st_ino, info.st_mode, info.st_size,
                info.st_mtime_ns, info.st_ctime_ns)

    def visit(fd, prefix):
        nonlocal raw
        before = os.fstat(fd)
        with os.scandir(fd) as entries:
            names = sorted(entry.name for entry in entries)
        for name in names:
            relative = prefix + name
            _output_path(relative)
            child = os.open(name, flags, dir_fd=fd)
            try:
                start = os.fstat(child)
                if stat.S_ISDIR(start.st_mode):
                    directories.append(relative)
                    visit(child, relative + "/")
                elif stat.S_ISREG(start.st_mode):
                    hasher, chunks = hashlib.sha256(), []
                    while True:
                        data = os.read(child, 1024 * 1024)
                        if not data:
                            break
                        hasher.update(data)
                        if relative == manifest:
                            chunks.append(data)
                    files[relative] = "sha256:" + hasher.hexdigest()
                    if relative == manifest:
                        raw = b"".join(chunks)
                else:
                    raise ValueError("result_artifact contains non-regular entry")
                end = os.fstat(child)
                named = os.stat(name, dir_fd=fd, follow_symlinks=False)
                if identity(start) != identity(end) or identity(end) != identity(named):
                    raise ValueError("result_artifact changed during read")
            finally:
                os.close(child)
        if identity(before) != identity(os.fstat(fd)):
            raise ValueError("result_artifact directory changed during read")

    fd = os.open(str(Path(base).resolve()), flags | os.O_DIRECTORY)
    try:
        for part in root.split("/"):
            child = os.open(part, flags | os.O_DIRECTORY, dir_fd=fd)
            os.close(fd)
            fd = child
        visit(fd, "")
    finally:
        os.close(fd)
    return files, directories, raw


def _result_artifact_reference(check, run_id, base):
    """Acquire only generic closure facts, never interpret producer meaning."""
    try:
        config = _output_contract(check, run_id)
        first = _output_snapshot(base, config["root"], config["manifest"])
        files, directories, raw = first
        _output_run_paths(directories, run_id)
        if raw is None:
            raise ValueError("result_artifact manifest missing")
        manifest = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                              parse_constant=lambda x: (_ for _ in ()).throw(
                                  ValueError("non-finite output JSON: " + x)))
        if (not isinstance(manifest, dict)
                or type(manifest.get("schema_version")) is not int
                or manifest["schema_version"] != config["schema_version"]
                or manifest.get("kind") != config["kind"]
                or manifest.get("run_id") != run_id):
            raise ValueError("result_artifact manifest contract/run mismatch")
        rows = manifest.get("artifacts")
        _output_rows(rows, run_id)
        expected = [{"path": p, "hash": h} for p, h in sorted(files.items())
                    if p != config["manifest"]]
        if rows != expected:
            raise ValueError("result_artifact inventory/digest mismatch")
        if first != _output_snapshot(base, config["root"], config["manifest"]):
            raise ValueError("result_artifact changed during acquisition")
        return {"schema_version": 1, "kind": "command_result_artifacts",
                "run_id": run_id, "root": config["root"],
                "manifest": {"path": config["manifest"],
                             "hash": files[config["manifest"]]},
                "artifacts": rows}
    except (OSError, TypeError, KeyError, UnicodeError) as exc:
        raise ValueError("result_artifact unavailable: " + str(exc)) from exc


def validate_output_references(check, evidence, run_id, base):
    """Pure declared-output validation for publication or preserved readback.

    No execution, observation, comparison, scoring or design-kind dispatch.
    Acquisition errors may honestly have no output. Once references exist,
    they must close exactly, even for a failing/refused command.
    """
    config = _output_contract(check, run_id)
    if "result_artifact" not in evidence:
        if config is not None and evidence.get("status") != "env_error":
            raise ValueError("result_artifact references missing")
        return
    if config is None:
        raise ValueError("undeclared result_artifact references")
    expected = _result_artifact_reference(check, run_id, base)
    try:
        matches = canonical(evidence["result_artifact"]) == canonical(expected)
    except (TypeError, OverflowError) as exc:
        raise ValueError("invalid result_artifact reference value") from exc
    if not matches:
        raise ValueError("result_artifact reference identity/digest mismatch")


def publish(path, value):
    """Flush then atomically link, never replace a published record."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=str(path.parent), prefix=".result-")
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(canonical(value))
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
    finally:
        os.unlink(temporary)
    return {"path": str(path), "hash": file_hash(path)}


def finite(value):
    if isinstance(value, bool):
        raise ValueError("boolean is not a quality number")
    try:
        number = float(value)
    except OverflowError as exc:
        raise ValueError("quality number outside finite range") from exc
    if not math.isfinite(number):
        raise ValueError("non-finite quality number")
    return number


def quality_components(text):
    block = re.search(r"^COMPONENTS=\((.*?)^\)", text, re.S | re.M)
    if not block:
        raise ValueError("unsupported COMPONENTS shape")
    entries = []
    for line in block[1].splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        match = re.fullmatch(r'"([A-Za-z_][A-Za-z0-9_-]*):([0-9.eE+-]+)"', line)
        if not match:
            raise ValueError("unsupported dynamic/customized COMPONENTS entry")
        name, weight = match.groups()
        weight = finite(weight)
        if weight < 0:
            raise ValueError("negative quality weight")
        entries.append((name, weight))
    if len({n for n, _ in entries}) != len(entries):
        raise ValueError("duplicate quality component")
    return entries


def policy_mode(plan):
    entries = plan.get("checks", []) + plan.get("residual_judgment", [])
    ids = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("invalid check entry")
        if "required" in entry and type(entry["required"]) is not bool:
            raise ValueError("required must be boolean")
        ids.append(entry.get("id"))
    policy = plan.get("required_policy")
    if policy is not None:
        if (not isinstance(policy, dict)
                or set(policy) != {"schema_version", "enabled"}
                or type(policy["schema_version"]) is not int
                or policy["schema_version"] != 1
                or type(policy["enabled"]) is not bool):
            raise ValueError("unsupported required_policy")
        if any(not isinstance(i, str) or not i.strip() for i in ids):
            raise ValueError("required policy needs nonempty check IDs")
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate check ID")
    enabled = policy is not None and policy["enabled"]
    if any(e.get("required") for e in entries) and not enabled:
        raise ValueError("required flags need enabled approved policy")
    return None if policy is None else enabled


def required_ids(plan):
    policy_mode(plan)
    return sorted(e["id"] for e in
                  plan.get("checks", []) + plan.get("residual_judgment", [])
                  if e.get("required") is True)


def assertion_closure(plan, base):
    """Reviewed closed files, not transitive dependency inference."""
    pins = {}
    for check in plan.get("checks", []):
        if not check.get("required"):
            continue
        if check.get("family") not in ("command", "generated_artifact_command"):
            continue  # unsupported evidence is unknown, not silently promoted
        artifacts = check.get("evaluator_artifacts")
        if not isinstance(artifacts, list) or any(
                not isinstance(p, str) or not p or Path(p).is_absolute()
                or ".." in Path(p).parts for p in artifacts):
            raise ValueError("required command needs evaluator_artifacts list")
        working_directory = check.get("working_directory") or "."
        if not isinstance(working_directory, str):
            raise ValueError("invalid assertion working_directory")
        command_directory = (base / working_directory).resolve()
        if not command_directory.is_relative_to(base.resolve()):
            raise ValueError("assertion working_directory escapes target")
        for artifact in artifacts:
            path = (base / artifact).resolve()
            if not path.is_relative_to(base.resolve()):
                raise ValueError("evaluator artifact escapes target")
            pins[policy_path(path, base)] = file_hash(path)
        for field in ("command", "build_command"):
            argv = check.get(field)
            if argv is None and field == "build_command":
                continue
            if (not isinstance(argv, list) or not argv
                    or any(not isinstance(a, str) for a in argv)):
                raise ValueError("required commands need explicit argv")
            if check["family"] == "generated_artifact_command":
                if "/" in argv[0] and not Path(argv[0]).is_absolute():
                    raise ValueError("generated evaluator needs absolute executable")
                execution_directory = None
            else:
                execution_directory = command_directory
            if "/" not in argv[0] and any(
                    not Path(part).is_absolute()
                    for part in os.environ.get("PATH", os.defpath).split(os.pathsep)):
                raise ValueError("required executable resolution needs absolute PATH entries")
            executable = (str(execution_directory / argv[0])
                          if execution_directory is not None and "/" in argv[0]
                          else shutil.which(argv[0]))
            if executable is None:
                raise ValueError("unavailable executable: " + argv[0])
            executable = str(Path(executable).resolve())
            if Path(executable).name in (
                    "sh", "bash", "zsh", "dash", "env", "eval"):
                raise ValueError("unsupported shell/dynamic evaluator")
            pins[policy_path(executable, base)] = file_hash(executable)
            script = None
            interpreter = Path(executable).name
            if re.fullmatch(r"python(?:\d+(?:\.\d+)*)?", interpreter):
                index = 1
                while index < len(argv) and argv[index] in (
                        "-I", "-S", "-B", "-E", "-s", "-u"):
                    index += 1
                if index < len(argv) and argv[index] == "--":
                    raise ValueError("unsupported required Python option separator")
                if index >= len(argv):
                    raise ValueError("required Python evaluator needs an entrypoint")
                if argv[index] == "-c":
                    if index + 1 >= len(argv):
                        raise ValueError("required Python inline evaluator needs code")
                elif argv[index].startswith("-"):
                    raise ValueError("unsupported required Python evaluator option")
                else:
                    script = argv[index]
            elif interpreter in ("node", "nodejs", "ruby", "perl", "php", "lua"):
                raise ValueError("unsupported required interpreter entrypoint")
            elif len(argv) > 1 and argv[1].endswith((".py", ".js", ".rb", ".sh")):
                script = argv[1]
            if script is not None:
                if execution_directory is None and not Path(script).is_absolute():
                    raise ValueError("generated assertion needs absolute script artifact")
                actual_script = ((execution_directory or base) / script).resolve()
                if actual_script not in {
                        (base / a).resolve() for a in artifacts}:
                    raise ValueError("assertion script must be declared")
    return [{"path": p, "hash": h} for p, h in sorted(pins.items())]


def check_pins(pins, base=None):
    base = Path.cwd() if base is None else base
    for pin in pins:
        if file_hash(base / pin["path"]) != pin["hash"]:
            raise ValueError("approved artifact modified: " + pin["path"])


def binding(plan, component, checks_path, engine, runtime, fragment, base):
    mode = policy_mode(plan)
    if mode is None:
        raise ValueError("no explicit required policy to approve")
    source = {"path": plan.get("source_spec_path"),
              "hash": plan.get("source_hash")}
    if not all(isinstance(v, str) and v for v in source.values()):
        raise ValueError("required approval needs source provenance")
    return {
        "schema_version": 1, "kind": "approved_required_binding",
        "component": component, "checks_path": policy_path(checks_path, base),
        "config_hash": plan["approved_content_hash"],
        "enabled": mode, "required_ids": required_ids(plan),
        "source_identity": source,
        "evaluator": {"path": policy_path(engine, base), "hash": file_hash(engine)},
        "evaluator_artifacts": assertion_closure(plan, base),
        "fragment_hash": file_hash(fragment),
        "required_runtime": {"path": policy_path(runtime, base),
                             "hash": file_hash(runtime)},
        "driver_hash": digest(DRIVER.encode()),
    }


def validate_binding(entry, plan, content_hash, base):
    if (type(entry.get("schema_version")) is not int or entry["schema_version"] != 1
            or entry.get("kind") != "approved_required_binding"):
        raise ValueError("unsupported approved required binding")
    if plan.get("approval_status") != "approved":
        raise ValueError("policy unapproved")
    if content_hash != entry["config_hash"]:
        raise ValueError("config identity modified")
    if entry != plan.get("approved_required_binding"):
        raise ValueError("approved binding modified")
    if entry["required_ids"] != required_ids(plan):
        raise ValueError("required ID set modified")
    if policy_mode(plan) != entry["enabled"]:
        raise ValueError("policy mode modified")
    if entry["source_identity"] != {
            "path": plan.get("source_spec_path"), "hash": plan.get("source_hash")}:
        raise ValueError("source identity modified")
    check_pins([entry["evaluator"], entry["required_runtime"]]
               + entry["evaluator_artifacts"], base)
    if assertion_closure(plan, base) != entry["evaluator_artifacts"]:
        raise ValueError("executable resolution modified")
    if entry["driver_hash"] != digest(DRIVER.encode()):
        raise ValueError("required driver modified")
    fragment = (base / entry["checks_path"]).parent / "oracle.sh.fragment"
    if file_hash(fragment) != entry["fragment_hash"]:
        raise ValueError("fragment modified")


def enabled(target):
    manifest = target / ".servo/install.json"
    try:
        if "required_policy" in load(manifest):
            return True
    except (OSError, ValueError, TypeError):
        try:
            if re.search(r'"required_policy"\s*:', manifest.read_text(errors="replace")):
                return True
        except OSError:
            pass
    return ((target / ".servo/required-policy.json").exists()
            or ((target / "oracle.sh").is_file()
                and MARKER in (target / "oracle.sh").read_text(errors="replace")))


def installed_policy(target):
    manifest = load(target / ".servo/install.json")
    policy = load(target / ".servo/required-policy.json")
    if (type(policy.get("schema_version")) is not int
            or policy["schema_version"] != 1
            or policy.get("kind") != "required_policy"
            or not isinstance(policy.get("components"), list)):
        raise ValueError("invalid installed required policy")
    pin = manifest.get("required_policy")
    policy_hash = digest(canonical(policy))
    if canonical(pin) != canonical({"schema_version": 1, "hash": policy_hash}):
        raise ValueError("missing/mismatched manifest policy pin")
    check_pins([{"path": str(target / ".servo/required_runtime.py"),
                 "hash": policy["runtime_hash"]}])
    names = [e["component"] for e in policy["components"]]
    if len(names) != len(set(names)):
        raise ValueError("duplicate required component")
    return policy, policy_hash


def interpret(ids, evidence):
    items = []
    evidence_ids = [e.get("check_id") for e in evidence]
    for identity in ids:
        matching = [e for e in evidence if e.get("check_id") == identity]
        if len(matching) != 1:
            status, reason = "unknown", "missing/duplicate evidence"
        else:
            ev = matching[0]
            status = ev.get("status")
            if (status not in ("pass", "fail")
                    or ev.get("family") not in ("command", "generated_artifact_command")
                    or ev.get("schema_version") != 1 or ev.get("kind") != "evidence"):
                status = "unknown"
            reason = ev.get("message", "invalid evidence")
        items.append({"id": identity, "status": status, "reason": reason,
                      "evidence_index": (evidence_ids.index(identity)
                                         if identity in evidence_ids else None)})
    return aggregate(items, ids)


def aggregate(items, ids=None):
    groups = {s: [i["id"] for i in items if i["status"] == s]
              for s in ("pass", "fail", "unknown")}
    return {"status": ("unknown" if groups["unknown"] else
                       "fail" if groups["fail"] else "pass"),
            "ids": sorted(ids if ids is not None else [i["id"] for i in items]),
            "passed": groups["pass"], "failed": groups["fail"],
            "unknown": groups["unknown"],
            "counts": {s: len(g) for s, g in groups.items()}, "items": items}


def context(target):
    run_id = os.environ.get("SERVO_GATE_RUN_ID") or str(uuid.uuid4())
    if str(uuid.UUID(run_id)) != run_id:
        raise ValueError("invalid gate run ID")
    destination = target / ".servo/gate-runs" / run_id
    supplied = os.environ.get("SERVO_GATE_RESULT_DIR")
    if supplied and Path(supplied).resolve() != destination.resolve():
        raise ValueError("wrong gate result directory")
    destination.mkdir(parents=True, exist_ok=False)
    publish(destination / "invocation.json", {
        "schema_version": 1, "kind": "gate_invocation", "run_id": run_id})
    return run_id, destination


def oracle_context(target):
    run_id = os.environ.get("SERVO_GATE_RUN_ID")
    supplied = os.environ.get("SERVO_GATE_RESULT_DIR")
    if not run_id and not supplied:
        run_id, directory = context(target)
    else:
        if not run_id or not supplied or str(uuid.UUID(run_id)) != run_id:
            raise ValueError("invalid caller run context")
        directory = target / ".servo/gate-runs" / run_id
        if Path(supplied).resolve() != directory.resolve():
            raise ValueError("wrong caller result directory")
        if load(directory / "invocation.json") != {
                "schema_version": 1, "kind": "gate_invocation", "run_id": run_id}:
            raise ValueError("unowned caller run context")
    publish(directory / "oracle-claim.json", {"run_id": run_id})
    return run_id, directory


def component_result(plan, result, checks_path, runtime_path):
    run_id = os.environ["SERVO_GATE_RUN_ID"]
    entry = plan["approved_required_binding"]
    if os.environ.get("SERVO_REQUIRED_COMPONENT") != entry["component"]:
        raise ValueError("wrong component invocation")
    destination = Path(os.environ["SERVO_REQUIRED_RESULT"])
    expected = checks_path.resolve().parent / "runs" / run_id / "result.json"
    if destination.resolve() != expected:
        raise ValueError("wrong component destination")
    # Prefer the approved target-relative checks location, not command cwd
    # (working_directory) or a generated command's disposable build directory.
    location = Path(entry["checks_path"])
    base = Path.cwd()
    if not location.is_absolute():
        base = checks_path.resolve()
        for _ in location.parts:
            base = base.parent
        if (base / location).resolve() != checks_path.resolve():
            raise ValueError("component checks location mismatch")
    checks = {c["id"]: c for c in plan.get("checks", [])}
    unavailable = False
    for index, evidence in enumerate(result["evidence"]):
        check = checks.get(evidence["check_id"], {})
        try:
            validate_output_references(check, evidence, run_id, base)
        except ValueError as exc:
            # A publication race cannot erase other contradictions or the
            # original raw exit/references. Refuse only the affected evidence
            # before sealing it; never rewrite a published component.
            unavailable = True
            result["evidence"][index] = {
                **evidence, "status": "env_error",
                "message": evidence["message"] + "; result_artifact: " + str(exc)}
    if unavailable:
        passed = sum(e["status"] == "pass" for e in result["evidence"])
        failed = sum(e["status"] == "fail" for e in result["evidence"])
        errors = sum(e["status"] == "env_error" for e in result["evidence"])
        result["summary"].update(
            passed_checks=passed, failed_checks=failed, env_errors=errors,
            score=passed / (passed + failed) if passed + failed else 0.0)
    envelope = {
        "schema_version": 1, "kind": "required_component_result",
        "run_id": run_id, "component": entry["component"],
        "policy_hash": os.environ["SERVO_REQUIRED_POLICY_HASH"],
        "config_hash": entry["config_hash"],
        "evaluator_hash": entry["evaluator"]["hash"],
        "source_identity": entry["source_identity"],
        "score": result["summary"]["score"],
        "evidence": result["evidence"],
        "required": interpret(entry["required_ids"], result["evidence"]),
    }
    return publish(destination, envelope)


def validate_component(reference, entry, run_id, policy_hash, score, base=None):
    base = Path.cwd() if base is None else base
    path = Path(reference["path"])
    expected = (base / entry["checks_path"]).parent / "runs" / run_id / "result.json"
    if path.resolve() != expected.resolve() or file_hash(path) != reference["hash"]:
        raise ValueError("component digest/destination mismatch")
    record = load(path)
    expected_identity = {
        "schema_version": 1, "kind": "required_component_result",
        "run_id": run_id, "component": entry["component"],
        "policy_hash": policy_hash, "config_hash": entry["config_hash"],
        "evaluator_hash": entry["evaluator"]["hash"],
        "source_identity": entry["source_identity"],
    }
    for key, value in expected_identity.items():
        if record.get(key) != value or type(record.get(key)) is not type(value):
            raise ValueError("component identity mismatch: " + key)
    if finite(record["score"]) != score:
        raise ValueError("component score mismatch")
    plan = load(base / entry["checks_path"])
    expected_ids = sorted(e["id"] for e in
                          plan.get("checks", []) + plan.get("residual_judgment", []))
    if sorted(e["check_id"] for e in record["evidence"]) != expected_ids:
        raise ValueError("extra/omitted/duplicate evidence ID")
    checks = {c["id"]: c for c in plan.get("checks", [])}
    checks.update({c["id"]: {**c, "family": "residual_judgment"}
                   for c in plan.get("residual_judgment", [])})
    output_errors = {}
    for evidence in record["evidence"]:
        check = checks[evidence["check_id"]]
        if (type(evidence.get("schema_version")) is not int
                or evidence["schema_version"] != 1 or evidence.get("kind") != "evidence"
                or evidence.get("family") != check.get("family")
                or evidence.get("ac_id") != (check.get("ac_id") or check["id"])
                or not isinstance(evidence.get("message"), str)
                or evidence.get("status") not in ("pass", "fail", "env_error", "not_applicable")):
            raise ValueError("invalid raw evidence: " + evidence["check_id"])
        try:
            validate_output_references(check, evidence, run_id, base)
        except ValueError as exc:
            output_errors[evidence["check_id"]] = str(exc)
    passed = sum(e["status"] == "pass" for e in record["evidence"])
    failed = sum(e["status"] == "fail" for e in record["evidence"])
    errors = sum(e["status"] == "env_error" for e in record["evidence"])
    diagnostic = passed / (passed + failed) if passed + failed else (0.0 if errors else 1.0)
    if diagnostic != record["score"]:
        raise ValueError("diagnostic score inconsistent with raw evidence")
    interpreted = interpret(entry["required_ids"], record["evidence"])
    if canonical(interpreted) != canonical(record["required"]):
        raise ValueError("required interpretation/counts mismatch")
    if output_errors:
        if set(output_errors) - set(entry["required_ids"]):
            raise ValueError("component output closure unavailable: " + str(output_errors))
        # Preserve immutable raw exits/reasons and other known failures. An
        # invalid output cannot carry its former pass into overall publication.
        return aggregate([
            {**item, "status": "unknown", "reason": output_errors[item["id"]]}
            if item["id"] in output_errors else item
            for item in interpreted["items"]], entry["required_ids"])
    return interpreted


def outcome(run_id, policy_hash, components, composite, threshold, items, override):
    required = aggregate(items)
    quality_failed = composite is not None and composite < threshold
    if required["status"] == "unknown" or composite is None:
        code, reason = 2, "required_evidence_unavailable"
    elif required["status"] == "fail":
        code = 1
        reason = ("required_and_quality_failed" if quality_failed
                  else "required_constraints_failed")
    elif quality_failed:
        code, reason = 1, "quality_below_threshold"
    else:
        code, reason = 0, None
    return {"schema_version": 2, "kind": "gate_result", "run_id": run_id,
            "status": {0: "pass", 1: "fail", 2: "env_error"}[code],
            "exit_code": code, "reason": reason,
            "composite": composite, "threshold": threshold,
            "threshold_override": override, "policy_hash": policy_hash,
            "required": required, "components": components, "missing": []}


def unknown_items(entry, reason):
    return [{"id": i, "component": entry["component"], "status": "unknown",
             "reason": reason, "evidence_index": None}
            for i in entry["required_ids"]]


def oracle(target):
    """Run each ordinary shell score once, carrying its exact evidence."""
    run_id, directory = oracle_context(target)
    policy_hash, components, items = None, [], []
    threshold, composite = None, None
    override = {"source": "environment" if "THRESHOLD" in os.environ else "oracle_default",
                "value": os.environ.get("THRESHOLD", "0.5")}
    try:
        policy, policy_hash = installed_policy(target)
        text = (target / "oracle.sh").read_text()
        if not text.endswith(DRIVER):
            raise ValueError("required driver modified")
        prefix = text[:-len(DRIVER)]
        if driver_identity(prefix) != policy["driver_prefix_hash"]:
            raise ValueError("unsupported customized required driver")
        default = re.search(r'THRESHOLD="\$\{THRESHOLD:-([^}]+)\}"', prefix)
        threshold = finite(os.environ.get("THRESHOLD", default[1]))
        override["value"] = os.environ.get("THRESHOLD", default[1])
        entries = quality_components(prefix)
        if not entries:
            raise ValueError("invalid quality component set")
        required_entries = {e["component"]: e for e in policy["components"]}
        absent = set(required_entries) - {n for n, _ in entries}
        for name in sorted(absent):
            items.extend(unknown_items(required_entries[name], "required component omitted"))
        quality_valid = True
        for name, raw_weight in entries:
            weight = finite(raw_weight)
            if weight < 0:
                raise ValueError("negative quality weight")
            entry = required_entries.get(name)
            env = {k: v for k, v in os.environ.items()
                   if not k.startswith("SERVO_REQUIRED_")}
            env.update(SERVO_GATE_RUN_ID=run_id, SERVO_GATE_RESULT_DIR=str(directory))
            reference = None
            error = None
            if entry:
                try:
                    # Engines enforce content freeze before executing. Here
                    # also prove the approved fragment is the live shell block.
                    check_pins([entry["evaluator"], entry["required_runtime"]]
                               + entry["evaluator_artifacts"], target)
                    plan = load(target / entry["checks_path"])
                    if (plan.get("approved_required_binding") != entry
                            or plan.get("approval_status") != "approved"
                            or plan.get("approved_content_hash") != entry["config_hash"]
                            or entry["source_identity"] != {
                                "path": plan.get("source_spec_path"),
                                "hash": plan.get("source_hash")}):
                        raise ValueError("installed approval/config/source binding modified")
                    fragment = (target / entry["checks_path"]).parent / "oracle.sh.fragment"
                    if (file_hash(fragment) != entry["fragment_hash"]
                            or fragment.read_text().rstrip() not in prefix):
                        raise ValueError("live required fragment modified")
                    path = (target / entry["checks_path"]).parent / "runs" / run_id / "result.json"
                    env.update(SERVO_REQUIRED_COMPONENT=name,
                               SERVO_REQUIRED_RESULT=str(path),
                               SERVO_REQUIRED_POLICY_HASH=policy_hash)
                    reference = {"path": str(path)}
                except (OSError, ValueError, KeyError) as exc:
                    error = str(exc)
            if error:
                rc, score = 2, None
            else:
                process = subprocess.run(
                    ["bash", "-c", prefix + "\nscore_" + name],
                    cwd=str(target), env=env, capture_output=True, text=True)
                rc = process.returncode
                try:
                    score = finite(process.stdout.strip())
                    if not 0 <= score <= 1:
                        raise ValueError("score outside [0,1]")
                except ValueError as exc:
                    error, score = str(exc), None
                if entry:
                    try:
                        reference["hash"] = file_hash(reference["path"])
                        required = validate_component(reference, entry, run_id,
                                                      policy_hash, score, target)
                        items.extend({**i, "component": name} for i in required["items"])
                    except (OSError, ValueError, KeyError, TypeError) as exc:
                        error = str(exc)
            if error and entry:
                items.extend(unknown_items(entry, error))
            if rc != 0 or score is None:
                quality_valid = False
            components.append({"component": name, "weight": weight, "score": score,
                               "exit_code": rc, "result": reference})
        total = sum(c["weight"] for c in components)
        if quality_valid and (len(components) == 1 or total > 0):
            composite = (components[0]["score"] if len(components) == 1 else
                         sum(c["weight"] * c["score"] for c in components) / total)
    except (OSError, ValueError, KeyError, TypeError, AttributeError, IndexError) as exc:
        items.append({"id": "<policy>", "status": "unknown", "reason": str(exc)})
    payload = outcome(run_id, policy_hash, components, composite, threshold, items, override)
    publish(directory / "oracle-result.json", payload)
    print("oracle: composite={} threshold={}".format(composite, threshold))
    return payload["exit_code"]


def run_gate(target, runner, timeout, json_mode, verbose, preflight_error=None):
    run_id, directory, policy_hash = None, None, None
    policy = None
    items = []
    components, composite, threshold, override = [], None, None, None
    try:
        run_id, directory = context(target)
        if preflight_error:
            raise ValueError(preflight_error)
        policy, policy_hash = installed_policy(target)
        environment = {"SERVO_GATE_RUN_ID": run_id,
                       "SERVO_GATE_RESULT_DIR": str(directory)}
        stdout, stderr, code, timed_out = runner(
            target / "oracle.sh", target, timeout, env={**os.environ, **environment})
        payload = load(directory / "oracle-result.json")
        if (type(payload.get("schema_version")) is not int
                or payload["schema_version"] != 2 or payload.get("kind") != "gate_result"
                or payload.get("run_id") != run_id or payload.get("policy_hash") != policy_hash
                or type(payload.get("exit_code")) is not int
                or payload.get("exit_code") != code or timed_out):
            raise ValueError("invalid oracle result/run/exit")
        for field in ("composite", "threshold"):
            if payload.get(field) is not None and type(payload[field]) not in (int, float):
                raise ValueError("invalid overall quality field type: " + field)
        # Effective quality policy is independent authority, not a label or
        # unvalidated composite copied from a component-owned result.
        default = re.search(r'THRESHOLD="\$\{THRESHOLD:-([^}]+)\}"',
                            (target / "oracle.sh").read_text())
        threshold = finite(os.environ.get("THRESHOLD", default[1]))
        override = {"source": ("environment" if "THRESHOLD" in os.environ
                               else "oracle_default"),
                    "value": os.environ.get("THRESHOLD", default[1])}
        text = (target / "oracle.sh").read_text()
        weights = quality_components(text)
        required_names = {entry["component"] for entry in policy["components"]}
        for component in payload["components"]:
            if (type(component.get("exit_code")) is not int
                    or type(component.get("weight")) not in (int, float)
                    or (component.get("score") is not None
                        and type(component["score"]) not in (int, float))):
                raise ValueError("invalid component quality field type")
            if component["component"] not in required_names and component.get("result") is not None:
                raise ValueError("unbound scalar component result")
        actual = [(c["component"], finite(c["weight"])) for c in payload["components"]]
        if (actual != weights or len(set(n for n, _ in actual)) != len(actual)
                or any(w < 0 for _, w in actual)
                or finite(payload["threshold"]) != threshold
                or payload["threshold_override"] != override):
            raise ValueError("effective quality policy mismatch")
        quality_valid = all(c["exit_code"] == 0 and c["score"] is not None
                            for c in payload["components"])
        scores = [finite(c["score"]) for c in payload["components"] if c["score"] is not None]
        if any(not 0 <= s <= 1 for s in scores):
            raise ValueError("invalid quality score")
        total = sum(w for _, w in weights)
        composite = None
        if quality_valid and (len(weights) == 1 or total > 0):
            composite = (scores[0] if len(weights) == 1 else sum(
                c["weight"] * c["score"] for c in payload["components"]) / total)
        if payload["composite"] != composite:
            raise ValueError("quality composite mismatch")
        components = payload["components"]
        items = []
        by_name = {c["component"]: c for c in payload["components"]}
        for entry in policy["components"]:
            component = by_name.get(entry["component"])
            try:
                required = validate_component(component["result"], entry, run_id,
                                              policy_hash, component["score"], target)
                items.extend({**i, "component": entry["component"]}
                             for i in required["items"])
            except (OSError, ValueError, KeyError, TypeError) as exc:
                # Preserve known failures when another component is unavailable.
                items.extend(unknown_items(entry, str(exc)))
        # Oracle can add refusal causes but cannot confer a pass by inventing
        # component labels. Reconstruct required verdict from immutable bytes.
        if payload["required"]["status"] == "unknown":
            items.extend(i for i in payload["required"]["items"] if i["status"] == "unknown"
                         and i not in items)
        expected = outcome(run_id, policy_hash, payload["components"],
                           payload["composite"], payload["threshold"], items,
                           payload["threshold_override"])
        if canonical(expected) != canonical(payload):
            raise ValueError("invalid oracle aggregate/decision")
    except (OSError, ValueError, KeyError, TypeError, AttributeError, IndexError) as exc:
        if not items and policy is not None:
            # A missing/invalid overall carrier cannot erase contradictions
            # already published by this exact invocation. Recover only these
            # approved destinations; never query a ledger/latest-run pointer.
            for entry in policy["components"]:
                try:
                    path = ((target / entry["checks_path"]).parent
                            / "runs" / run_id / "result.json")
                    reference = {"path": str(path), "hash": file_hash(path)}
                    score = finite(load(path)["score"])
                    required = validate_component(reference, entry, run_id,
                                                  policy_hash, score, target)
                    items.extend({**i, "component": entry["component"]}
                                 for i in required["items"])
                    if not any(c["component"] == entry["component"] for c in components):
                        components.append({"component": entry["component"], "weight": None,
                                           "score": score, "exit_code": 2, "result": reference})
                except (OSError, ValueError, KeyError, TypeError) as unavailable:
                    items.extend(unknown_items(entry, str(unavailable)))
        payload = outcome(run_id, policy_hash, components, composite, threshold,
                          items + [{"id": "<gate>", "status": "unknown",
                                    "reason": str(exc)}], override)
    if directory:
        publish(directory / "gate.json", payload)
    if json_mode:
        print(canonical(payload).decode())
    else:
        print("gate: composite={} threshold={} status={} exit={} reason={}".format(
            payload["composite"], payload["threshold"], payload["status"],
            payload["exit_code"], payload["reason"]))
    return payload["exit_code"]


if __name__ == "__main__":
    try:
        sys.exit(oracle(Path.cwd()))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print("required runtime refused: " + str(exc), file=sys.stderr)
        sys.exit(2)
