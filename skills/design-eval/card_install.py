"""Prepare the bounded card pilot for independent review and ordinary installation."""

import argparse
import importlib.metadata
import importlib.util
import json
import os
import platform
import re
import shlex
import shutil
import site
import subprocess
import sys
from pathlib import Path

import card_bundle as bundle
from card_evidence import (
    PACKAGE_PINS,
    PRODUCER_PINS,
    assert_driver_seal,
    check_startup_environment,
    packages_at,
    policy_hash,
    producer_at,
    validated_policy,
)

HERE = Path(__file__).resolve().parent


def _native_dependencies(files, programs):
    """Close non-OS absolute linkage; browser assets are separately inventoried."""
    bundle.require(
        platform.system() == "Darwin" and Path("/usr/bin/otool").is_file(),
        "this bounded native-linkage preparation requires the pinned macOS runtime",
    )
    pending = {Path(path).resolve() for path in programs}
    pending.update(
        Path(module.__file__).resolve()
        for module in list(sys.modules.values())
        if getattr(module, "__file__", None) and Path(module.__file__).suffix in (".so", ".dylib")
    )
    pending.update(path for path in files if path.name == "node")
    seen, resolutions = set(), {}
    while pending:
        path = pending.pop()
        if path in seen:
            continue
        seen.add(path)
        bundle.require(path in files, "unlisted native module: " + str(path))
        process = subprocess.run(
            ["/usr/bin/otool", "-L", str(path)],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        bundle.require(process.returncode == 0, "native linkage unavailable: " + str(path))
        for line in process.stdout.splitlines()[1:]:
            if not line.strip() or (line.startswith(str(path)) and line.rstrip().endswith(":")):
                continue
            name = line.strip().split(" (compatibility", 1)[0]
            if name.startswith(("/usr/lib/", "/System/Library/")):
                continue
            if name.startswith("@loader_path/"):
                name = os.path.normpath(str(path.parent / name.removeprefix("@loader_path/")))
            bundle.require(name.startswith("/"), "unsupported relative native linkage: " + name)
            dependency = Path(name).resolve()
            bundle.require(
                dependency in files or name.startswith(("/opt/homebrew/", "/usr/local/")),
                "unapproved native dependency location: " + name,
            )
            bundle.require(dependency.is_file(), "native dependency unavailable: " + name)
            files.add(dependency)
            resolutions[name] = {
                "path": name,
                "resolved": str(dependency),
                "hash": bundle.file_hash(dependency),
            }
            if dependency not in seen:
                pending.add(dependency)
    return [resolutions[name] for name in sorted(resolutions)]


def _runtime(python, browser_root, claude):
    bundle.require(
        str(Path(python).resolve()) == str(Path(sys.executable).resolve()),
        "run preparation with the selected Python runtime",
    )
    probe = subprocess.run(
        [str(python), "-I", "-B", "-c", "import json,sys; print(json.dumps(sys.prefix))"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    bundle.require(
        probe.returncode == 0
        and Path(json.loads(probe.stdout)).resolve() == Path(sys.prefix).resolve(),
        "preparation prefix differs from selected Python environment",
    )
    site_roots = sorted(str(Path(root).resolve()) for root in site.getsitepackages())
    check_startup_environment(sys.prefix, site_roots)
    importlib.import_module("card_capture")
    from card_quality import assert_native_cli, judge_environment
    from playwright.sync_api import sync_playwright

    assert_native_cli(claude)
    judge_environment()

    bash = shutil.which("bash")
    bundle.require(bash is not None, "declared bash runtime unavailable")
    files = {Path(sys.executable).resolve(), Path(claude).resolve(), Path(bash).resolve()}
    files.add(Path(sys.prefix).resolve() / "pyvenv.cfg")
    for path in Path(sys.base_prefix).rglob("*"):
        if (
            "site-packages" not in path.parts
            and "__pycache__" not in path.parts
            and path.suffix != ".pyc"
            and path.is_file()
        ):
            files.add(path.resolve())
    versions = {}
    for name in ("playwright", "greenlet", "pyee", "typing_extensions"):
        distribution = importlib.metadata.distribution(name)
        versions[name] = distribution.version
        for name in distribution.files or []:
            path = Path(distribution.locate_file(name))
            if "__pycache__" not in path.parts and path.suffix != ".pyc" and path.is_file():
                files.add(path.resolve())
    browser_root = Path(browser_root).resolve()
    for path in browser_root.rglob("*"):
        if path.is_file():
            files.add(path.resolve())
    with sync_playwright() as runtime:
        executable = Path(runtime.chromium.executable_path)
        bundle.require(executable.is_relative_to(browser_root), "browser outside declared closure")
        browser_hash = bundle.file_hash(executable)
    native_resolutions = _native_dependencies(files, [sys.executable, bash, claude])
    return {
        "python": platform.python_version(),
        "executable": str(Path(sys.executable).resolve()),
        "prefix": str(Path(sys.prefix).resolve()),
        "os": platform.platform(),
        "dependencies": versions,
        "bash": str(Path(bash).resolve()),
        "module_origins": {
            name: str(Path(importlib.util.find_spec(name).origin).resolve()) for name in versions
        },
        "site_roots": site_roots,
        "native_resolutions": native_resolutions,
        "browser_root": str(browser_root),
        "browser_hash": browser_hash,
        "files": [{"path": str(path), "hash": bundle.file_hash(path)} for path in sorted(files)],
    }


def prepare(
    target,
    producer_root,
    references,
    candidate,
    python,
    browser_root,
    claude,
    model="opus",
    quality_mode="live",
    calibration_limit=8,
    prior_attempts=None,
    purpose="bounded-card-calibration",
):
    target = Path(target).resolve()
    bundle.require(not (target / "spec/oracle/card").exists(), "card pilot already exists")
    bundle.require((target / "oracle.sh").is_file(), "scaffold the ordinary target first")
    producer = producer_at(producer_root)
    packages = packages_at(references, producer)
    runtime = _runtime(python, browser_root, claude)
    bundle.require(
        type(calibration_limit) is int and calibration_limit >= 8,
        "unapproved calibration allowance",
    )
    bundle.require(type(purpose) is str and purpose.strip(), "batch purpose required")
    bundle.require(
        calibration_limit == 8 or prior_attempts is not None,
        "new allowance requires preserved prior attempt history",
    )
    helper = target / "tools/card"
    helper.mkdir(parents=True)
    for name in (
        "card_bundle.py",
        "card_capture.py",
        "card_evidence.py",
        "card_quality.py",
        "score.py",
    ):
        shutil.copyfile(HERE / name, helper / name)
    for name in ("fidelity_eval.py",):
        shutil.copyfile(HERE.parent / "_common" / name, helper / name)
    runtime_files = runtime.pop("files")
    runtime_manifest = helper / "runtime-files.json"
    bundle.publish(runtime_manifest, runtime_files)
    runtime["manifest"] = {
        "path": str(runtime_manifest),
        "hash": bundle.file_hash(runtime_manifest),
    }
    source_helper = helper / "producer"
    source_helper.mkdir()
    for name in PRODUCER_PINS:
        shutil.copyfile(Path(producer_root) / name, source_helper / name)
    approved = target / "design-input"
    shutil.copytree(references, approved)
    source = target / "candidate"
    source.mkdir()
    shutil.copyfile(candidate, source / "index.html")
    bundle.publish(
        source / "candidate.json",
        {
            "schema_version": 1,
            "entry": "index.html",
            "dependencies": [],
            "assets": [],
        },
    )
    builds = target / "builds"
    builds.mkdir()
    result = subprocess.run(
        [
            str(python),
            "-B",
            str(helper / "card_bundle.py"),
            "--source",
            str(source),
            "--out",
            str(builds / "baseline"),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    bundle.require(result.returncode == 0, "candidate build failed: " + result.stderr)
    delivery = target / "delivery"
    shutil.copytree(builds / "baseline/output", delivery)
    bundle.publish(
        target / "candidate-selection.json",
        {
            "build": "builds/baseline",
            "delivery": "delivery",
        },
    )
    quality = target / ".servo/design-eval"
    quality.mkdir(parents=True)
    prior_rows = []
    if prior_attempts is not None:
        from card_quality import inherit_attempts

        prior_rows = inherit_attempts(
            prior_attempts, quality / "calibration-invocations", calibration_limit
        )
    (quality / "refs").mkdir()
    for state in packages:
        shutil.copyfile(approved / f"{state}.png", quality / f"refs/{state}.png")
    version = subprocess.run(
        [str(claude), "--version"], capture_output=True, text=True, timeout=30, check=False
    )
    bundle.require(version.returncode == 0, "cannot identify selected Claude CLI")
    dimensions = [
        {"id": "layout", "description": "card/band layout, spacing, dimensions and proportions"},
        {"id": "palette", "description": "band and title/subtitle colours and contrast"},
        {
            "id": "typography",
            "description": "visible typography appearance, sizes, weights, alignment",
        },
        {"id": "visible-content", "description": "visible exact title and state-specific subtitle"},
        {"id": "card-shape", "description": "card/band shape, clipping and edges"},
    ]
    ignore = [
        {
            "id": "actual-font-face",
            "reason": "declaration identity is not actual face certification",
        },
        {"id": "sibling-open-driver", "reason": "sibling state driver is outside approved crop"},
    ]
    config = {
        "schema_version": 2,
        "approval_status": "draft",
        "viewport": {"width": 800, "height": 600, "deviceScaleFactor": 1},
        "judge": {
            "model": model,
            "transport": "cli",
            "decoding_mode": "native-default",
            "execution_mode": "safe-restricted-read-only",
            "auth_mode": "claude-subscription",
            "calibration_limit": calibration_limit,
            "prior_attempts": prior_rows,
            "batch_purpose": purpose,
            "runtime": {
                "binary": str(Path(claude).resolve()),
                "hash": bundle.file_hash(claude),
                "version": version.stdout.strip(),
            },
        },
        "samples": {"n": 4, "k": 1.0, "delta": 0.03},
        "threshold": 0.8,
        "dimensions": dimensions,
        "ignore": ignore,
        "catalogue": [
            {"id": item["id"], "description": item.get("description", item.get("reason"))}
            for item in dimensions + ignore
        ],
        "screens": [
            {
                "id": state,
                "reference": f"refs/{state}.png",
                "weight": 1.0,
            }
            for state in packages
        ],
    }
    bundle.publish(quality / "config.json", config)
    out = target / "spec/oracle/card"
    out.mkdir(parents=True)
    policy_path = out / "card-policy.json"
    evaluator_files = [
        {"path": str(path), "hash": bundle.file_hash(path)}
        for path in sorted(helper.rglob("*"))
        if path.is_file()
    ]
    policy = {
        "schema_version": 1,
        "kind": "card_evidence_policy",
        "target": str(target),
        "producer": str(source_helper),
        "references": str(approved),
        "selection": "candidate-selection.json",
        "output_root": "spec/oracle/card/runs/{run_id}/design",
        "evaluator_files": evaluator_files,
        "runtime": runtime,
        "quality": {"mode": quality_mode, "config": str(quality / "config.json")},
        "approval": {"decision": "pending"},
    }
    bundle.publish(policy_path, policy)
    source_spec = target / "spec/card.md"
    source_spec.write_text(
        "# Bounded approved Trailhead card\n\n"
        + "\n".join(
            f"- {identity}: required under approved C0/C1."
            for package in packages.values()
            for identity in package["required_inventory"]["required_ids"]
        )
        + "\n",
        encoding="utf-8",
    )
    artifacts = (
        [
            path.relative_to(target).as_posix()
            for path in sorted(helper.rglob("*"))
            if path.is_file()
        ]
        + [
            "spec/oracle/card/card-policy.json",
            ".servo/design-eval/config.json",
            ".servo/design-eval/reenumeration.json",
        ]
        + [
            path.relative_to(target).as_posix()
            for path in sorted(approved.rglob("*"))
            if path.is_file()
        ]
        + [f".servo/design-eval/refs/{state}.png" for state in packages]
    )
    plan = {
        "schema_version": 1,
        "spec_id": "card",
        "source_spec_path": "spec/card.md",
        "source_hash": bundle.file_hash(source_spec),
        "required_policy": {"schema_version": 1, "enabled": True},
        "checks": [
            {
                "id": identity,
                "family": "command",
                "required": True,
                "timeout": 2700,
                "command": [
                    str(python),
                    "-B",
                    str(helper / "card_evidence.py"),
                    "evaluate",
                    "--policy",
                    str(policy_path),
                    "--constraint",
                    identity,
                ],
                "evaluator_artifacts": artifacts,
                "refusal_exit_codes": [2],
                "result_artifact": {
                    "root": policy["output_root"],
                    "manifest": "evidence.json",
                    "schema_version": 1,
                    "kind": "design_evidence",
                },
            }
            for package in packages.values()
            for identity in package["required_inventory"]["required_ids"]
        ],
        "residual_judgment": [],
    }
    bundle.publish(out / "checks.json", plan)
    bundle.publish(
        out / "preparation.json",
        {
            "status": "pending-independent-review-not-installed",
            "policy_hash_to_review": policy_hash(policy),
            "source_package_hashes": PACKAGE_PINS,
            "quality_config_hash": bundle.file_hash(quality / "config.json"),
            "judge_invocations": 0,
        },
    )
    return policy_path


def approve_policy(target, review_record):
    target = Path(target).resolve()
    path = target / "spec/oracle/card/card-policy.json"
    policy = bundle.load(path)
    review = bundle.load(review_record)
    bundle.require(
        review.get("verdict") == "pass"
        and review.get("author")
        and review.get("reviewer")
        and review["author"] != review["reviewer"]
        and review.get("policy_hash") == policy_hash(policy),
        "independent current card policy review required",
    )
    approval = {
        "decision": "approved",
        "author": review["author"],
        "reviewer": review["reviewer"],
        "policy_hash": policy_hash(policy),
        "review_record_hash": bundle.file_hash(review_record),
    }
    destination = path.with_name("policy-review.json")
    bundle.require(not destination.exists(), "policy review already recorded")
    shutil.copyfile(review_record, destination)
    policy["approval"] = approval
    path.write_bytes(bundle.canonical(policy) + b"\n")
    checks_path = path.with_name("checks.json")
    checks = bundle.load(checks_path)
    for check in checks["checks"]:
        check["evaluator_artifacts"].append("spec/oracle/card/policy-review.json")
    checks_path.write_bytes(bundle.canonical(checks) + b"\n")
    return approval


def generate(target, vendor=False):
    import design_eval

    target = Path(target).resolve()
    policy_path = target / "spec/oracle/card/card-policy.json"
    policy = validated_policy(policy_path)
    quality_path = Path(policy["quality"]["config"])
    config = bundle.load(quality_path)
    design_eval._score.validate_freeze(config, quality_path.parent)
    bundle.require(
        config.get("approval_provenance") == "reviewed",
        "independent reviewed quality freeze required",
    )
    checks_path = target / "spec/oracle/card/checks.json"
    plan = bundle.load(checks_path)
    for check in plan["checks"]:
        check["evaluator_artifacts"] = [
            path for path in check["evaluator_artifacts"] if path != "oracle.sh"
        ]
    plan["approval_status"] = "draft"
    checks_path.write_bytes(bundle.canonical(plan) + b"\n")
    python = shlex.quote(sys.executable)
    command = " ".join(
        (
            python,
            "-B",
            shlex.quote(str(target / "tools/card/card_evidence.py")),
            "quality --policy",
            shlex.quote(str(policy_path)),
        )
    )
    fragment = (
        "# SEED:start design_fidelity\nPATH="
        + shlex.quote(str(Path(sys.executable).parent))
        + ':"$PATH"\nexport PATH\n'
        + 'if [ -z "${SERVO_GATE_RUN_ID:-}" ]; then\n'
        + '  echo "bound card requires gate.py owned run context" >&2\n  exit 2\nfi\n'
        + "export PYTHONDONTWRITEBYTECODE=1\n"
        + 'export PYTHONPYCACHEPREFIX="$PWD/.servo/gate-runs/$SERVO_GATE_RUN_ID/python-source-only"\n'
        + "score_design_fidelity() {\n  "
        + command
        + "\n}\n# SEED:end design_fidelity\n"
    )
    oracle_path = target / "oracle.sh"
    text, count = re.subn(
        r'^THRESHOLD="\$\{THRESHOLD:-[0-9.]+\}"$',
        'THRESHOLD="${THRESHOLD:-' + str(config["threshold"]) + '}"',
        oracle_path.read_text(),
        flags=re.MULTILINE,
    )
    bundle.require(count == 1, "unsupported oracle threshold declaration")
    text = design_eval._fe.splice_component(text, "design_fidelity", fragment)
    text = design_eval._fe.splice_components_entry(text, "design_fidelity", 1.0)
    oracle_path.write_text(text)
    design_eval._fe.register_manifest(target, "design_fidelity")
    overlay = HERE.parent / "spec-oracle/oracle_overlay.py"
    args = [sys.executable, str(overlay), "generate", str(target), str(target / "spec"), "card"]
    if vendor:
        args.append("--vendor-engine")
    result = subprocess.run(args, capture_output=True, text=True, timeout=180, check=False)
    bundle.require(result.returncode == 0, "ordinary generation failed: " + result.stderr)


def _install_approved(target, vendor=False):
    import design_eval

    target = Path(target).resolve()
    policy = validated_policy(target / "spec/oracle/card/card-policy.json")
    quality_path = Path(policy["quality"]["config"])
    config = bundle.load(quality_path)
    design_eval._score.validate_freeze(config, quality_path.parent)
    bundle.require(
        config.get("approval_provenance") == "reviewed",
        "independent reviewed quality freeze required",
    )
    expected_threshold = 'THRESHOLD="${THRESHOLD:-' + str(config["threshold"]) + '}"'
    bundle.require(
        expected_threshold in (target / "oracle.sh").read_text().splitlines(),
        "oracle quality threshold differs from reviewed definition; regenerate/review first",
    )
    args = [
        sys.executable,
        str(HERE.parent / "spec-oracle/oracle_overlay.py"),
        "install",
        str(target),
        str(target / "spec"),
        "card",
        "--enable-required",
        "--weight",
        "0",
    ]
    if vendor:
        args.append("--vendor-engine")
    result = subprocess.run(args, capture_output=True, text=True, timeout=180, check=False)
    bundle.require(result.returncode == 0, "ordinary installation failed: " + result.stderr)


def seal_driver(target, vendor=False):
    target = Path(target).resolve()
    checks_path = target / "spec/oracle/card/checks.json"
    plan = bundle.load(checks_path)
    bundle.require(
        not any("oracle.sh" in check["evaluator_artifacts"] for check in plan["checks"]),
        "driver already declared; review/reapprove current final bytes instead",
    )
    _install_approved(target, vendor)
    for check in plan["checks"]:
        check["evaluator_artifacts"].append("oracle.sh")
    plan["approval_status"] = "draft"
    checks_path.write_bytes(bundle.canonical(plan) + b"\n")
    args = [
        sys.executable,
        str(HERE.parent / "spec-oracle/oracle_overlay.py"),
        "generate",
        str(target),
        str(target / "spec"),
        "card",
    ]
    if vendor:
        args.append("--vendor-engine")
    result = subprocess.run(args, capture_output=True, text=True, timeout=180, check=False)
    bundle.require(
        result.returncode == 0, "final sealed-driver generation failed: " + result.stderr
    )


def install(target, vendor=False):
    target = Path(target).resolve()
    assert_driver_seal(target)
    _install_approved(target, vendor)
    assert_driver_seal(target)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="operation", required=True)
    prepare_parser = commands.add_parser("prepare")
    for name in (
        "target",
        "producer-root",
        "references",
        "candidate",
        "python",
        "browser-root",
        "claude",
    ):
        prepare_parser.add_argument("--" + name, required=True, type=Path)
    prepare_parser.add_argument("--model", default="opus")
    prepare_parser.add_argument("--calibration-limit", type=int, default=8)
    prepare_parser.add_argument("--prior-attempts", type=Path)
    prepare_parser.add_argument("--purpose", default="bounded-card-calibration")
    prepare_parser.add_argument(
        "--quality-mode", choices=("live", "diagnostic-negative-control"), default="live"
    )
    approve_parser = commands.add_parser("approve-policy")
    approve_parser.add_argument("--target", type=Path, required=True)
    approve_parser.add_argument("--review-record", type=Path, required=True)
    for operation in ("generate", "seal-driver", "install"):
        operation_parser = commands.add_parser(operation)
        operation_parser.add_argument("--target", type=Path, required=True)
        operation_parser.add_argument("--vendor-engine", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.operation == "prepare":
            path = prepare(
                args.target,
                args.producer_root,
                args.references,
                args.candidate,
                args.python,
                args.browser_root,
                args.claude,
                args.model,
                args.quality_mode,
                args.calibration_limit,
                args.prior_attempts,
                args.purpose,
            )
            print("Prepared for independent review, not approved/installed: " + str(path))
        elif args.operation == "approve-policy":
            approve_policy(args.target, args.review_record)
            print("Recorded independently reviewed card policy; not installed")
        elif args.operation == "generate":
            generate(args.target, args.vendor_engine)
            print("Generated ordinary card overlay; review and approve before installation")
        elif args.operation == "seal-driver":
            seal_driver(args.target, args.vendor_engine)
            print(
                "Staged final driver as a required evaluator input; review/reapprove before install. "
                "Unsealed/draft evaluation refuses."
            )
        else:
            install(args.target, args.vendor_engine)
            print("Installed ordinary required card component and same-run quality adapter")
        return 0
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, ImportError) as exc:
        print("REFUSE card workflow: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
