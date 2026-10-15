"""Bounded card observations; component evidence is not completion authority."""

import argparse
import importlib.metadata
import importlib.util
import os
import platform
import secrets
import shutil
import sys
import uuid
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from pathlib import Path

import card_bundle as bundle
from card_bundle import canonical, require

PRODUCER_PINS = {
    "approved_card.py": "sha256:0461146abba5d01c83169f89c6fccbddc79ef7018f6569418e69b5f9d99d5373",
    "resolve_redline.py": "sha256:4ac7206d58f7af1cab12ad71f32c373d91afd905284242e78a18e222d7219b57",
}
PACKAGE_PINS = {
    "normal.json": "sha256:b894ed7590cf7678af832071b657085cf9316bb1cd4c4dfde2f4f9be53ec0303",
    "open.json": "sha256:5d3ac7de4780ab4cc21802e8e9cd3d5aae7572a3050312f7608ab4e7b839f4fb",
    "release.json": "sha256:5aeea5e302038656d17ad881052a0f63d47bb297370f1c0c5d04e0a1339b6313",
    "approval.json": "sha256:d4322d16444bba75f6e4384430284595ecf2b203f4278c3ac0fda9564f8c4c5b",
}


def _indexed(rows):
    require(type(rows) is list, "missing comparison inventory")
    result = {}
    for row in rows:
        require(
            type(row) is dict and type(row.get("id")) is str and row["id"] not in result,
            "duplicate/invalid observation ID",
        )
        result[row["id"]] = row
    return result


def compare(package, observed):
    ids = package["required_inventory"]["required_ids"]
    policies = _indexed(package["policy"]["constraints"])
    targets = _indexed(package["source_facts"])
    facts = _indexed(observed["facts"])
    require(
        ids == sorted(set(ids)) and sorted(policies) == ids and sorted(targets) == ids,
        "required inventory mismatch",
    )
    require(set(facts).issubset(ids), "extra observation ID")
    require(observed["state"] == package["view"]["state"], "foreign state observation")
    result = []
    for identity in ids:
        policy, target = policies[identity], targets[identity]
        require(
            policy["required"] is True
            and "tolerance" in policy
            and type(policy["tolerance"]) is str,
            "missing explicit comparison/tolerance",
        )
        row = {
            **policy,
            "state": observed["state"],
            "expected": target["value"],
            "actual": facts.get(identity, {}).get("value"),
            "observation": {"path": observed["state"] + ".observations.json", "property": identity},
        }
        element = observed["elements"].get(policy["binding_id"])
        if element is not None and (
            element.get("count") == 0
            or (element.get("count") == 1 and element.get("visible") is False)
        ):
            status, reason = "fail", "required bound element absent or not visible"
        elif observed.get("acquisition_error"):
            status, reason = "unknown", observed["acquisition_error"]
        elif not element or element.get("count") != 1:
            status, reason = "unknown", "missing or ambiguous bound observation"
        elif identity.endswith("-subtitle-text") and observed.get("state_error"):
            status, reason = "fail", observed["state_error"]
        elif identity not in facts or facts[identity].get("error"):
            status, reason = (
                "unknown",
                facts.get(identity, {}).get("error", "missing required property observation"),
            )
        else:
            actual, expected = row["actual"], row["expected"]
            comparison = policy["comparison"]
            if comparison in ("exact", "present"):
                require(policy["tolerance"] == "0", "unsupported exact tolerance")
                matches = canonical(actual) == canonical(expected)
            elif comparison == "absolute-inclusive":
                require(
                    type(actual) in (str, int) and type(expected) in (str, int),
                    "invalid numeric observation",
                )
                try:
                    a, e, tolerance = (
                        Fraction(Decimal(str(v))) for v in (actual, expected, policy["tolerance"])
                    )
                except (InvalidOperation, ValueError, OverflowError) as exc:
                    raise ValueError("invalid finite scalar") from exc
                require(tolerance >= 0, "negative tolerance")
                matches = abs(a - e) <= tolerance
            else:
                raise ValueError("unsupported required comparison")
            status = "pass" if matches else "fail"
            reason = "approved comparison satisfied" if matches else "observed value differs"
        result.append({**row, "status": status, "reason": reason})
    return result


def producer_at(root):
    root = Path(root)
    for name, expected in PRODUCER_PINS.items():
        require(bundle.file_hash(root / name) == expected, "producer helper changed: " + name)
    sys.path.insert(0, str(root))
    try:
        spec = importlib.util.spec_from_file_location(
            "servo_card_source_verifier", root / "approved_card.py"
        )
        require(spec is not None and spec.loader is not None, "producer verifier unavailable")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.pop(0)


def packages_at(root, producer):
    root = Path(root)
    for name, expected in PACKAGE_PINS.items():
        require(
            bundle.file_hash(root / name) == expected, "approved source package changed: " + name
        )
    release = producer.load(root / "release.json")
    producer.verify_manifest(root, release["artifacts"])
    return {
        state: producer.validate(producer.load(root / f"{state}.json"), root, approved=True)
        for state in ("normal", "open")
    }


def policy_hash(policy):
    return bundle.identity("servo-policy-v1", {k: v for k, v in policy.items() if k != "approval"})


def validated_policy(path):
    policy = bundle.load(path)
    require(
        type(policy.get("schema_version")) is int
        and policy["schema_version"] == 1
        and policy.get("kind") == "card_evidence_policy",
        "unsupported card policy",
    )
    require(
        set(policy)
        == {
            "schema_version",
            "kind",
            "target",
            "producer",
            "references",
            "selection",
            "output_root",
            "evaluator_files",
            "runtime",
            "quality",
            "approval",
        },
        "unsupported card policy fields",
    )
    approval = policy["approval"]
    require(
        type(approval) is dict
        and approval.get("decision") == "approved"
        and approval.get("author")
        and approval.get("reviewer")
        and approval["author"] != approval["reviewer"]
        and approval.get("policy_hash") == policy_hash(policy),
        "card policy approval stale/missing",
    )
    for row in policy["evaluator_files"]:
        require(bundle.file_hash(row["path"]) == row["hash"], "evaluator helper changed")
    runtime_manifest = policy["runtime"]["manifest"]
    require(
        bundle.file_hash(runtime_manifest["path"]) == runtime_manifest["hash"],
        "runtime dependency manifest changed",
    )
    for row in bundle.load(runtime_manifest["path"]):
        require(
            bundle.file_hash(row["path"]) == row["hash"],
            "runtime dependency changed: " + row["path"],
        )
    require(
        policy["runtime"]["python"] == platform.python_version()
        and policy["runtime"]["executable"] == str(Path(sys.executable).resolve())
        and policy["runtime"]["os"] == platform.platform()
        and os.environ.get("PLAYWRIGHT_BROWSERS_PATH") == policy["runtime"]["browser_root"],
        "runtime environment changed",
    )
    return policy


def current_binding(policy):
    target = Path(policy["target"])
    selection_path = bundle.safe(target, policy["selection"])
    selection = bundle.load(selection_path)
    require(
        type(selection) is dict and set(selection) == {"build", "delivery"},
        "unsupported current candidate selection",
    )
    build_root = bundle.safe(target, selection["build"])
    delivery = bundle.safe(target, selection["delivery"])
    record = bundle.load(build_root / "build.json")
    require(
        Path(record["source"]).resolve().is_relative_to(target.resolve()),
        "candidate source escapes target",
    )
    bundle.verify(record, build_root, delivery)
    return {
        "selection": selection,
        "selection_hash": bundle.file_hash(selection_path),
        "build": record,
        "build_root": str(build_root),
        "delivery": str(delivery),
    }


def _run_id(target):
    run_id = os.environ.get("SERVO_GATE_RUN_ID", "")
    require(str(uuid.UUID(run_id)) == run_id, "invalid current gate run")
    invocation = target / ".servo" / "gate-runs" / run_id
    require(
        Path(os.environ.get("SERVO_GATE_RESULT_DIR", "")).resolve() == invocation.resolve(),
        "unbound current gate invocation",
    )
    require(
        bundle.load(invocation / "invocation.json")
        == {
            "schema_version": 1,
            "kind": "gate_invocation",
            "run_id": run_id,
        },
        "missing current invocation ownership",
    )
    return run_id


def _normalize(package, observed, producer):
    facts = []
    for target in package["source_facts"]:
        node = observed["elements"].get(target["element"])
        if not node or node.get("count") != 1:
            continue
        key = target["observation"]
        actual = True if key == "presence" else node["raw"].get(key)
        fact = {"id": target["id"], "raw": actual}
        try:
            normalizer = {
                "presence": lambda value: value,
                "text": lambda value: value,
                "width": producer.decimal,
                "height": producer.decimal,
                "backgroundColor": producer.colour,
                "color": producer.colour,
                "fontFamily": producer.family,
                "fontSize": producer.size,
                "fontWeight": producer.weight,
            }.get(key)
            require(normalizer is not None, "unsupported required observation")
            fact["value"] = normalizer(actual)
        except (producer.Refusal, ValueError, TypeError) as exc:
            fact["error"] = str(exc)
        facts.append(fact)
    return {**observed, "facts": facts}


def _summary(rows):
    groups = {
        status: [r["id"] for r in rows if r["status"] == status]
        for status in ("pass", "fail", "unknown")
    }
    status = "unknown" if groups["unknown"] else "fail" if groups["fail"] else "pass"
    return {
        "status": "env_error" if status == "unknown" else status,
        "required_status": status,
        "passed": groups["pass"],
        "failed": groups["fail"],
        "unknown": groups["unknown"],
        "counts": {status: len(values) for status, values in groups.items()},
    }


def _verify_ownership(envelope, root, policy, run_id):
    invocation = Path(policy["target"]) / ".servo/gate-runs" / run_id
    try:
        claim = bundle.load(invocation / "card-acquisition-claim.json")
        receipt = bundle.load(invocation / "card-acquisition-receipt.json")
        local = bundle.load(root / "claim.json")
    except OSError as exc:
        raise ValueError("acquisition ownership receipt unavailable") from exc
    require(
        claim == local
        and claim["run_id"] == run_id
        and claim["policy_hash"] == policy_hash(policy)
        and claim["output_root"] == root.relative_to(Path(policy["target"])).as_posix()
        and receipt
        == {
            "run_id": run_id,
            "nonce": claim["nonce"],
            "envelope_hash": bundle.file_hash(root / "evidence.json"),
        }
        and envelope.get("acquisition_nonce") == claim["nonce"],
        "foreign/relabelled acquisition ownership or receipt",
    )


def _verify_existing(envelope, root, policy, binding, run_id):
    _verify_ownership(envelope, root, policy, run_id)
    require(
        envelope["run_id"] == run_id and envelope["policy"]["hash"] == policy_hash(policy),
        "foreign/stale design run",
    )
    require(
        canonical(envelope["build"]) == canonical(binding["build"])
        and envelope["current_delivery"]["selection_hash"] == binding["selection_hash"],
        "candidate/current delivery changed since capture",
    )
    actual = [row for row in bundle.inventory(root) if row["path"] != "evidence.json"]
    require(actual == envelope["artifacts"], "design output closure changed since capture")
    ids = [row["id"] for row in envelope["constraints"]]
    require(
        ids == envelope["policy"]["required_ids"] and ids == sorted(set(ids)),
        "partial/duplicate design constraints",
    )


def evaluate(policy_path):
    policy = validated_policy(policy_path)
    target = Path(policy["target"])
    run_id = _run_id(target)
    producer = producer_at(policy["producer"])
    packages = packages_at(policy["references"], producer)
    binding = current_binding(policy)
    root = bundle.safe(target, policy["output_root"].replace("{run_id}", run_id))
    if root.exists():
        envelope = bundle.load(root / "evidence.json")
        _verify_existing(envelope, root, policy, binding, run_id)
        return envelope
    invocation = target / ".servo/gate-runs" / run_id
    claim = {
        "run_id": run_id,
        "policy_hash": policy_hash(policy),
        "output_root": root.relative_to(target).as_posix(),
        "nonce": secrets.token_hex(32),
    }
    bundle.publish(invocation / "card-acquisition-claim.json", claim)
    root.mkdir(parents=True)
    bundle.publish(root / "claim.json", claim)
    source = Path(binding["build"]["source"])
    shutil.copytree(source, root / "sealed-inputs")
    shutil.copytree(Path(binding["build_root"]) / "output", root / "sealed-output")
    require(
        bundle.inventory(root / "sealed-inputs") == binding["build"]["inputs"],
        "source changed while sealing run",
    )
    require(
        bundle.inventory(root / "sealed-output") == binding["build"]["outputs"],
        "output changed while sealing run",
    )
    bundle.publish(root / "build.json", binding["build"])
    bundle.publish(
        root / "delivery.json",
        {
            "selected_path": binding["delivery"],
            "manifest": bundle.inventory(binding["delivery"]),
            "selection_hash": binding["selection_hash"],
        },
    )
    observations, rows, acquisition_error = {}, [], None
    try:
        from playwright.sync_api import Error as BrowserError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise ValueError("declared Playwright runtime unavailable") from exc
    from card_capture import acquire

    with sync_playwright() as runtime:
        executable = Path(runtime.chromium.executable_path)
        require(
            bundle.file_hash(executable) == policy["runtime"]["browser_hash"],
            "browser executable changed",
        )
        try:
            browser = runtime.chromium.launch(headless=True)
        except BrowserError as exc:
            raise ValueError("browser unavailable: " + str(exc)) from exc
        try:
            for state, package in packages.items():
                observed = acquire(
                    browser,
                    root / "sealed-output/index.html",
                    package["application_binding_intent"],
                    state,
                    root / f"{state}.png",
                )
                observed = _normalize(package, observed, producer)
                observed.update(
                    run_id=run_id, capture_id=str(uuid.uuid4()), acquisition_nonce=claim["nonce"]
                )
                bundle.publish(root / f"{state}.observations.json", observed)
                observations[state] = {
                    "path": f"{state}.observations.json",
                    "hash": bundle.file_hash(root / f"{state}.observations.json"),
                }
                rows.extend(compare(package, observed))
            environment = {
                "python": platform.python_version(),
                "browser": browser.version,
                "browser_hash": bundle.file_hash(executable),
                "os": platform.platform(),
                "viewport": {"width": 800, "height": 600, "device_scale": "1"},
                "dependencies": {
                    name: importlib.metadata.version(name)
                    for name in ("playwright", "greenlet", "pyee", "typing_extensions")
                },
                "settling": "fonts.ready then four identical animation-frame scoped snapshots",
            }
        finally:
            browser.close()
    rows.sort(key=lambda row: row["id"])
    try:
        require(
            canonical(current_binding(policy)) == canonical(binding),
            "source/build/current delivery changed during capture",
        )
        require(
            canonical(validated_policy(policy_path)) == canonical(policy),
            "policy changed during capture",
        )
    except (OSError, ValueError) as exc:
        acquisition_error = str(exc)
    quality = {"mode": "unavailable", "reason": "quality not acquired"}
    if acquisition_error is None and not any(r["status"] == "unknown" for r in rows):
        mode = policy["quality"]["mode"]
        if mode == "live":
            from card_quality import run

            try:
                quality = run(
                    policy["quality"]["config"],
                    {state: root / f"{state}.png" for state in packages},
                    root,
                    target / ".servo/design-eval/calibration-invocations",
                )
            except (OSError, ValueError, RuntimeError) as exc:
                quality = {"mode": "unavailable", "reason": "quality unavailable: " + str(exc)}
        elif mode == "diagnostic-negative-control":
            quality = {
                "mode": mode,
                "composite": 0.99,
                "reason": "explicit synthetic quality control, not live fidelity",
            }
            if not any(r["status"] == "fail" for r in rows):
                quality = {
                    "mode": "unavailable",
                    "reason": "diagnostic quality cannot establish a positive completion run",
                }
        else:
            quality = {"mode": "unavailable", "reason": "live quality not selected"}
    try:
        require(
            canonical(current_binding(policy)) == canonical(binding),
            "source/build/current delivery changed before result publication",
        )
        require(
            canonical(validated_policy(policy_path)) == canonical(policy),
            "policy changed before result publication",
        )
    except (OSError, ValueError) as exc:
        acquisition_error = str(exc)
    if acquisition_error:
        rows = [
            r if r["status"] == "fail" else {**r, "status": "unknown", "reason": acquisition_error}
            for r in rows
        ]
    envelope = {
        "schema_version": 1,
        "kind": "design_evidence",
        "run_id": run_id,
        "acquisition_nonce": claim["nonce"],
        "source": {
            "contract_version": producer.VERSION,
            "packages": {
                state: {
                    "hash": bundle.file_hash(Path(policy["references"]) / f"{state}.json"),
                    "target_revision": package["target_revision"],
                    "approval_hash": "sha256:" + package["approval"]["sha256"],
                }
                for state, package in packages.items()
            },
        },
        "policy": {"hash": policy_hash(policy), "required_ids": [r["id"] for r in rows]},
        "evaluator": policy["evaluator_files"],
        "build": binding["build"],
        "current_delivery": {
            "path": binding["delivery"],
            "selection_hash": binding["selection_hash"],
            "output_hash": binding["build"]["output_hash"],
        },
        "environment": environment,
        "observations": observations,
        "constraints": rows,
        "summary": _summary(rows),
        "quality": quality,
        "artifacts": bundle.inventory(root),
    }
    bundle.publish(root / "evidence.json", envelope)
    bundle.publish(
        invocation / "card-acquisition-receipt.json",
        {
            "run_id": run_id,
            "nonce": claim["nonce"],
            "envelope_hash": bundle.file_hash(root / "evidence.json"),
        },
    )
    return envelope


def validate_current(policy_path, envelope_path):
    policy = validated_policy(policy_path)
    envelope_path = Path(envelope_path)
    envelope = bundle.load(envelope_path)
    run_id = envelope["run_id"]
    require(str(uuid.UUID(run_id)) == run_id, "invalid preserved run ID")
    expected = bundle.safe(
        Path(policy["target"]), policy["output_root"].replace("{run_id}", run_id)
    )
    require(
        envelope_path.resolve() == (expected / "evidence.json").resolve(),
        "preserved envelope destination mismatch",
    )
    producer = producer_at(policy["producer"])
    packages_at(policy["references"], producer)
    _verify_existing(envelope, expected, policy, current_binding(policy), run_id)
    return envelope


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("evaluate", "quality", "verify-current"))
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--constraint")
    parser.add_argument("--envelope", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.operation == "verify-current":
            require(args.envelope is not None, "preserved envelope required")
            validate_current(args.policy, args.envelope)
            print("preserved bytes and current candidate/delivery match; no re-scoring")
            return 0
        envelope = evaluate(args.policy)
        if args.operation == "quality":
            quality = envelope["quality"]
            require(
                quality["mode"] in ("live", "diagnostic-negative-control")
                and envelope["summary"]["required_status"] != "unknown",
                "quality unavailable for current bound run",
            )
            print(quality["composite"])
            return 0
        match = [row for row in envelope["constraints"] if row["id"] == args.constraint]
        require(len(match) == 1, "unknown required constraint")
        row = match[0]
        print(canonical(row).decode())
        if row["status"] != "pass":
            print(row["id"] + ": " + row["reason"], file=sys.stderr)
        return {"pass": 0, "fail": 1, "unknown": 2}[row["status"]]
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
        print("REFUSE card evidence: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
