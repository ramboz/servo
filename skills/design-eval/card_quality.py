"""Bounded live CLI calibration using the existing reviewed design-eval policy."""

import json
import math
import os
import shutil
import stat
import subprocess
from pathlib import Path

import score as scoring
from card_bundle import file_hash, inventory, load, publish, raw, require, safe


def assert_native_cli(path):
    with Path(path).open("rb") as stream:
        header = stream.read(4)
    require(
        header
        in (
            b"\xcf\xfa\xed\xfe",
            b"\xfe\xed\xfa\xcf",
            b"\xca\xfe\xba\xbe",
            b"\xbe\xba\xfe\xca",
            b"\xca\xfe\xba\xbf",
            b"\xbf\xba\xfe\xca",
            b"\x7fELF",
        )
        or header.startswith(b"MZ"),
        "native Claude entrypoint required; script/PATH interpreter wrappers unsupported",
    )


def judge_environment():
    env = dict(os.environ)
    require(
        not any(env.get(key) for key in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")),
        "unselected auth mode; pilot requires the approved Claude subscription",
    )
    for key in (
        "CLAUDE_CODE_USE_BEDROCK",
        "CLAUDE_CODE_USE_VERTEX",
        "CLAUDE_CODE_USE_FOUNDRY",
        "CLAUDE_CODE_SIMPLE",
    ):
        require(
            env.get(key, "").lower() in ("", "0", "false", "no", "off"),
            "unselected provider or subscription-incompatible mode: " + key,
        )
    require(
        env.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com").rstrip("/")
        == "https://api.anthropic.com",
        "unselected provider endpoint",
    )
    for key in ("GH_TOKEN", "GITHUB_TOKEN", "COPILOT_GITHUB_TOKEN"):
        env.pop(key, None)
    return env


def judge_command(binary, prompt, model):
    return [
        str(binary),
        "--safe-mode",
        "--restricted",
        "--strict-mcp-config",
        "--tools",
        "Read",
        "--allowedTools",
        "Read",
        "--permission-mode",
        "dontAsk",
        "-p",
        prompt,
        "--model",
        model,
        "--output-format",
        "json",
        "--no-session-persistence",
    ]


def input_identity(path):
    before = Path(path).lstat()
    require(stat.S_ISREG(before.st_mode), "judge input must be a regular sealed file")
    digest = file_hash(path)
    after = Path(path).lstat()

    def fields(value):
        return (
            value.st_dev,
            value.st_ino,
            value.st_mode,
            value.st_size,
            value.st_mtime_ns,
            value.st_ctime_ns,
        )

    require(fields(before) == fields(after), "judge input changed while hashing")
    return digest, fields(after)


def parse_reply(envelope, requested):
    require(
        type(envelope) is dict and not envelope.get("is_error"), "Claude judge reported an error"
    )
    reply = json.loads(scoring._extract_json(envelope.get("result", "")))
    value = reply.get("score") if type(reply) is dict else None
    require(
        type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1,
        "invalid finite judge score",
    )
    usage = envelope.get("modelUsage", {})
    require(
        type(usage) is dict and all(type(k) is str and k for k in usage),
        "invalid returned model identity metadata",
    )
    require(
        all(
            (model.startswith("claude-opus-") if requested == "opus" else model == requested)
            for model in usage
        ),
        "exposed model differs from selected Opus judge",
    )
    return {
        "score": value,
        "reasoning": reply.get("reasoning"),
        "requested_model": requested,
        "observed_models": sorted(usage),
        "identity_scope": (
            "CLI-reported usage identity, not immutable provider attestation"
            if usage
            else "resolved model not exposed by CLI response"
        ),
        "session_id": envelope.get("session_id"),
    }


def reserve(directory, limit):
    require(type(limit) is int and limit > 0, "unapproved calibration allowance")
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    for number in range(1, limit + 1):
        try:
            with (directory / f"{number}.claim").open("xb") as stream:
                stream.write(b"reserved before live invocation\n")
            return number
        except FileExistsError:
            continue
    raise ValueError("approved batch allowance exhausted; no automatic replenishment")


def inherit_attempts(source, destination, limit):
    rows = inventory(source)
    require(type(limit) is int and limit >= 8, "unapproved calibration allowance")
    require(
        all(row["path"].endswith(".claim") and row["path"][:-6].isdigit() for row in rows),
        "invalid prior attempt history",
    )
    rows.sort(key=lambda row: int(row["path"][:-6]))
    require(
        [row["path"] for row in rows] == [f"{n}.claim" for n in range(1, len(rows) + 1)]
        and limit == len(rows) + 8,
        "new allowance must preserve history and authorize exactly eight planned judgments",
    )
    destination = Path(destination)
    destination.mkdir(parents=True)
    for row in rows:
        shutil.copyfile(safe(source, row["path"]), safe(destination, row["path"]))
    return rows


def run(config_path, shots, destination, allowance, *, capture_hashes):
    config_path, destination = Path(config_path), Path(destination)
    config_bytes_hash = file_hash(config_path)
    config = load(config_path)
    scoring._require_schema_v2(config)
    scoring.validate_freeze(config, config_path.parent)
    scoring._validate_policy(config)
    require(
        config.get("approval_provenance") == "reviewed",
        "card quality requires independent reviewed freeze",
    )
    judge = config["judge"]
    require(
        judge.get("execution_mode") == "safe-restricted-read-only"
        and judge.get("auth_mode") == "claude-subscription",
        "approved safe/read-only subscription execution mode required",
    )
    env = judge_environment()
    require(
        type(judge.get("batch_purpose")) is str and judge["batch_purpose"].strip(),
        "approved batch purpose required",
    )
    prior = judge.get("prior_attempts", [])
    require(
        type(prior) is list
        and all(type(row) is dict and set(row) == {"path", "hash"} for row in prior)
        and [row["path"] for row in prior] == [f"{n}.claim" for n in range(1, len(prior) + 1)],
        "missing or noncontiguous prior attempt history",
    )
    for row in prior:
        require(
            file_hash(safe(allowance, row["path"])) == row["hash"],
            "consumed attempt history changed",
        )
    require(
        type(judge.get("calibration_limit")) is int
        and judge["calibration_limit"] == len(prior) + 8,
        "approved batch must preserve history and allocate exactly eight judgments",
    )
    existing = list(Path(allowance).glob("*.claim")) if Path(allowance).exists() else []
    require(
        type(judge.get("calibration_limit")) is int
        and judge["calibration_limit"] - len(existing) >= 8,
        "remaining allowance cannot cover eight planned judgments; explicit approval required",
    )
    require(judge["transport"] == "cli", "pilot owner selected Claude CLI")
    require(
        judge.get("decoding_mode") == "native-default"
        and "temperature" not in judge
        and "max_tokens" not in judge,
        "CLI decoding must honestly declare native defaults, not ineffective numeric controls",
    )
    require(
        judge.get("model") == "opus"
        or (type(judge.get("model")) is str and judge["model"].startswith("claude-opus-")),
        "unselected pilot judge model",
    )
    require(
        not os.environ.get("SERVO_DESIGN_EVAL_FAKE_SCORES"), "fake quality is not live fidelity"
    )
    runtime = judge.get("runtime")
    require(
        type(runtime) is dict and set(runtime) == {"binary", "hash", "version"},
        "missing reviewed Claude runtime identity",
    )
    binary = Path(runtime["binary"])
    assert_native_cli(binary)
    require(file_hash(binary) == runtime["hash"], "Claude executable changed")
    version = subprocess.run(
        [str(binary), "--version"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        env=env,
    )
    require(
        version.returncode == 0 and version.stdout.strip() == runtime["version"],
        "Claude CLI runtime version changed",
    )
    require(
        config["samples"] == {"n": 4, "k": 1.0, "delta": 0.03},
        "unapproved first-calibration sampling",
    )
    require(
        type(config["samples"]["n"]) is int
        and type(config["samples"]["k"]) in (int, float)
        and type(config["samples"]["delta"]) in (int, float),
        "sampling quantities must be numbers, not aliases",
    )
    require(
        {s["id"] for s in config["screens"]} == {"normal", "open"} and len(config["screens"]) == 2,
        "quality screen inventory mismatch",
    )
    require(
        config["threshold"] == 0.8
        and config["viewport"] == {"width": 800, "height": 600, "deviceScaleFactor": 1}
        and type(config["viewport"]["deviceScaleFactor"]) in (int, float),
        "unapproved threshold or viewport",
    )
    require(set(capture_hashes) == {"normal", "open"}, "complete browser capture hashes required")
    input_root = safe(destination, "judge-inputs")
    input_root.mkdir()
    samples, invocations = {}, []
    for screen in config["screens"]:
        state = screen["id"]
        actual, reference = Path(shots[state]), config_path.parent / screen["reference"]
        require(
            actual.is_file() and reference.is_file(), "missing actual/reference quality capture"
        )
        require(
            screen["reference"] == f"refs/{state}.png"
            and type(screen["weight"]) in (int, float)
            and screen["weight"] == 1,
            "unsupported reference mapping or screen weight",
        )
        actual_bytes, reference_bytes = actual.read_bytes(), reference.read_bytes()
        require(
            raw(actual_bytes) == capture_hashes[state], "browser capture changed before judging"
        )
        require(
            raw(reference_bytes) == config["hashes"][screen["reference"]],
            "approved reference changed before judging",
        )
        actual, reference = (
            input_root / f"{state}-actual.png",
            input_root / f"{state}-reference.png",
        )
        for path, data in ((actual, actual_bytes), (reference, reference_bytes)):
            with path.open("xb") as stream:
                stream.write(data)
        input_hashes = {path: input_identity(path) for path in (actual, reference)}
        prompt = (
            scoring._scoring_prompt(config) + "\nRead these two images with the Read tool:\n"
            f"- FIRST implemented app: {actual.resolve()}\n"
            f"- SECOND approved reference: {reference.resolve()}\n"
            'Reply ONLY JSON: {"score": <number 0..1>, "reasoning": "<one sentence>"}.'
        )
        samples[state] = []
        for sample in range(1, 5):
            for row in prior:
                require(
                    file_hash(safe(allowance, row["path"])) == row["hash"],
                    "consumed attempt history changed",
                )
            number = reserve(allowance, judge.get("calibration_limit"))
            stem = f"quality-{state}-{sample}"
            require(
                all(input_identity(path) == snapshot for path, snapshot in input_hashes.items()),
                "sealed judge input changed before invocation",
            )
            command = judge_command(binary, prompt, judge["model"])
            publish(
                destination / (stem + ".request.json"),
                {
                    "invocation": number,
                    "requested_model": judge["model"],
                    "runtime": runtime,
                    "command": command,
                    "actual_hash": file_hash(actual),
                    "reference_hash": file_hash(reference),
                    "definition_hash": config["approved_content_hash"],
                    "batch_purpose": judge["batch_purpose"],
                },
            )
            try:
                result = subprocess.run(
                    command, capture_output=True, timeout=300, cwd=destination, check=False, env=env
                )
            except subprocess.TimeoutExpired as exc:
                (destination / (stem + ".stdout")).write_bytes(exc.stdout or b"")
                (destination / (stem + ".stderr")).write_bytes(exc.stderr or b"")
                raise ValueError(
                    "Claude judge timed out; invocation retained and consumed"
                ) from exc
            (destination / (stem + ".stdout")).write_bytes(result.stdout)
            (destination / (stem + ".stderr")).write_bytes(result.stderr)
            require(
                all(input_identity(path) == snapshot for path, snapshot in input_hashes.items()),
                "sealed judge input changed during invocation",
            )
            require(
                result.returncode == 0,
                f"Claude judge failed rc{result.returncode}; retained output",
            )
            parsed = parse_reply(json.loads(result.stdout), judge["model"])
            invocations.append(
                {**parsed, "invocation": number, "state": state, "response": stem + ".stdout"}
            )
            samples[state].append(parsed["score"])
    bounds = {
        state: scoring.aggregate_lower_bound(values, 1.0) for state, values in samples.items()
    }
    require(
        file_hash(config_path) == config_bytes_hash, "quality policy changed during calibration"
    )
    composite = sum(bounds.values()) / 2
    return {
        "mode": "live",
        "definition_hash": config["approved_content_hash"],
        "config_hash": config_bytes_hash,
        "runtime": runtime,
        "requested_model": judge["model"],
        "samples": samples,
        "lower_bounds": bounds,
        "composite": composite,
        "threshold": config["threshold"],
        "invocations": invocations,
        "completion_authority": "overall installed gate, not this quality record",
    }
