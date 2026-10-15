"""Bounded live CLI calibration using the existing reviewed design-eval policy."""

import json
import math
import subprocess
from pathlib import Path

import score as scoring
from card_bundle import file_hash, load, publish, require


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
    require(type(limit) is int and 1 <= limit <= 8, "unapproved calibration allowance")
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    for number in range(1, limit + 1):
        try:
            with (directory / f"{number}.claim").open("xb") as stream:
                stream.write(b"reserved before live invocation\n")
            return number
        except FileExistsError:
            continue
    raise ValueError("first-calibration allowance exhausted; explicit new approval required")


def run(config_path, shots, destination, allowance):
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
    require(not scoring._fake_scores(), "fake quality is not live fidelity")
    runtime = judge.get("runtime")
    require(
        type(runtime) is dict and set(runtime) == {"binary", "hash", "version"},
        "missing reviewed Claude runtime identity",
    )
    binary = Path(runtime["binary"])
    require(file_hash(binary) == runtime["hash"], "Claude executable changed")
    version = subprocess.run(
        [str(binary), "--version"], capture_output=True, text=True, timeout=30, check=False
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
        {s["id"] for s in config["screens"]} == {"normal", "open"} and len(config["screens"]) == 2,
        "quality screen inventory mismatch",
    )
    samples, invocations = {}, []
    for screen in config["screens"]:
        state = screen["id"]
        actual, reference = Path(shots[state]), config_path.parent / screen["reference"]
        require(
            actual.is_file() and reference.is_file(), "missing actual/reference quality capture"
        )
        prompt = (
            scoring._scoring_prompt(config) + "\nRead these two images with the Read tool:\n"
            f"- FIRST implemented app: {actual.resolve()}\n"
            f"- SECOND approved reference: {reference.resolve()}\n"
            'Reply ONLY JSON: {"score": <number 0..1>, "reasoning": "<one sentence>"}.'
        )
        samples[state] = []
        for sample in range(1, 5):
            number = reserve(allowance, judge.get("calibration_limit"))
            stem = f"quality-{state}-{sample}"
            command = [
                str(binary),
                "-p",
                prompt,
                "--model",
                judge["model"],
                "--allowedTools",
                "Read",
                "--output-format",
                "json",
                "--no-session-persistence",
            ]
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
                },
            )
            try:
                result = subprocess.run(
                    command, capture_output=True, timeout=300, cwd=destination, check=False
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
