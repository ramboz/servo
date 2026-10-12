"""Read-only Copilot CLI evaluation transport; Python 3.9+ standard library."""
from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Sequence

_VERSION = r"\d+\.\d+\.\d+(?:-[A-Za-z0-9]+(?:[.-][A-Za-z0-9]+)*)?"
_VERSION_BANNER = re.compile(r"GitHub Copilot CLI (" + _VERSION + r")\.?")
_READONLY_FLAGS = (
    "--no-auto-update", "--no-custom-instructions", "--disable-builtin-mcps",
    "--disallow-temp-dir", "--no-ask-user", "--available-tools=view",
    "--deny-tool=write", "--deny-tool=shell", "--output-format=json",
)


class CopilotError(RuntimeError):
    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason


def resolve_binary(bin_env: Optional[str] = None) -> str:
    binary = (
        (os.environ.get(bin_env) if bin_env else None)
        or os.environ.get("SERVO_COPILOT_BIN")
        or shutil.which("copilot")
    )
    if not binary:
        raise CopilotError(
            "copilot_not_found", "Copilot CLI not found; set SERVO_COPILOT_BIN or add it to PATH"
        )
    return binary


def _run(command: list, *, timeout: int, cwd: Optional[Path] = None):
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=timeout,
            cwd=str(cwd) if cwd is not None else None,
        )
    except subprocess.TimeoutExpired as exc:
        raise CopilotError("copilot_timeout", f"Copilot timed out after {timeout}s") from exc
    except OSError as exc:
        raise CopilotError("copilot_not_executable", f"Cannot execute Copilot: {exc}") from exc
    if result.returncode != 0:
        diagnostic = result.stderr.strip()
        for key in ("COPILOT_GITHUB_TOKEN", "GH_TOKEN", "GITHUB_TOKEN"):
            secret = os.environ.get(key)
            if secret:
                diagnostic = diagnostic.replace(secret, "[redacted]")
        raise CopilotError(
            "copilot_invocation_failed",
            f"Copilot exited {result.returncode}: {diagnostic[:300]}",
        )
    return result


def _version(binary: str) -> str:
    result = _run([binary, "--no-auto-update", "--version"], timeout=30)
    lines = result.stdout.splitlines()
    match = _VERSION_BANNER.fullmatch(lines[0].strip()) if lines else None
    if not match:
        raise CopilotError("copilot_version_unavailable", "Cannot identify the Copilot CLI version")
    return match.group(1)


def runtime_version(bin_env: Optional[str] = None) -> str:
    return _version(resolve_binary(bin_env))


def _validate_choice(model, decoding_mode) -> None:
    if not isinstance(model, str) or not model.strip() or model.strip().lower() == "auto":
        raise CopilotError(
            "copilot_model_required", "A commanded non-auto Copilot model is required",
        )
    if model != model.strip():
        raise CopilotError(
            "copilot_model_required", "Copilot model must not contain edge whitespace",
        )
    if decoding_mode != "native-default":
        raise CopilotError(
            "copilot_decoding_consent_required",
            "Explicit decoding_mode='native-default' is required; numeric controls are unavailable",
        )


def validate_judge(judge: dict) -> None:
    if not isinstance(judge, dict) or judge.get("transport") != "copilot":
        raise CopilotError("copilot_invalid_config", "Expected a Copilot judge definition")
    controls = [name for name in ("temperature", "max_tokens") if name in judge]
    if controls:
        raise CopilotError(
            "copilot_unsupported_controls",
            "Copilot cannot enforce numeric decoding controls: " + ", ".join(controls),
        )
    _validate_choice(judge.get("model"), judge.get("decoding_mode"))
    version = judge.get("runtime_version")
    if not isinstance(version, str) or not re.fullmatch(_VERSION, version):
        raise CopilotError(
            "copilot_runtime_required", "An exact frozen Copilot runtime_version is required"
        )


def judge_definition(
    model: str, decoding_mode: str, bin_env: Optional[str] = None,
) -> dict:
    _validate_choice(model, decoding_mode)
    return {
        "transport": "copilot", "model": model, "decoding_mode": decoding_mode,
        "runtime_version": runtime_version(bin_env),
    }


def invoke(
    prompt: str, *, model: Optional[str] = None, frozen_version: Optional[str] = None,
    attachments: Sequence[Path] = (), cwd: Optional[Path] = None,
    bin_env: Optional[str] = None, timeout: int = 300,
) -> dict:
    images = [Path(path).resolve() for path in attachments]
    for image in images:
        if not image.is_file():
            raise CopilotError("copilot_attachment_missing", f"Attachment missing: {image}")
    binary = resolve_binary(bin_env)
    version = _version(binary)
    if frozen_version is not None and version != frozen_version:
        raise CopilotError(
            "copilot_runtime_mismatch",
            f"Copilot runtime {version} differs from frozen {frozen_version}; review and re-freeze",
        )
    command = [binary, *_READONLY_FLAGS]
    if model is not None:
        if not isinstance(model, str) or not model.strip() or model.strip().lower() == "auto":
            raise CopilotError("copilot_model_required", "A non-auto model must be commanded")
        command.append("--model=" + model)
    command.extend("--attachment=" + str(image) for image in images)
    command.extend(["-p", prompt])
    result = _run(command, timeout=timeout, cwd=cwd)
    reply = parse_response(result.stdout, expected_model=model)
    reply["runtime_version"] = version
    reply["cost_usd"] = None
    return reply


def parse_score(text: str) -> dict:
    start, end = text.find("{"), text.rfind("}")
    try:
        value = json.loads(text[start:end + 1]) if start >= 0 and end >= start else None
    except json.JSONDecodeError as exc:
        raise CopilotError("copilot_invalid_score", "Copilot judge response is not JSON") from exc
    score = value.get("score") if isinstance(value, dict) else None
    if isinstance(score, bool) or not isinstance(score, (int, float)):
        raise CopilotError("copilot_invalid_score", "Copilot judge score must be numeric")
    if not 0 <= score <= 1 or not math.isfinite(score):
        raise CopilotError(
            "copilot_invalid_score", "Copilot judge score must be finite and in [0,1]",
        )
    return value


def judge(
    prompt: str, definition: dict, *, attachments: Sequence[Path] = (),
    cwd: Optional[Path] = None, bin_env: Optional[str] = None,
) -> dict:
    validate_judge(definition)
    reply = invoke(
        prompt, model=definition["model"], frozen_version=definition["runtime_version"],
        attachments=attachments, cwd=cwd, bin_env=bin_env,
    )
    return parse_score(reply["text"])


def parse_response(stdout: str, expected_model: Optional[str] = None) -> dict:
    if not isinstance(stdout, str):
        raise CopilotError("copilot_malformed_response", "Copilot output is not text")
    message = None
    terminal = None
    for number, line in enumerate(stdout.splitlines(), 1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise CopilotError(
                "copilot_malformed_response", f"Copilot output line {number} is not JSON"
            ) from exc
        if not isinstance(event, dict) or not isinstance(event.get("type"), str):
            raise CopilotError("copilot_malformed_response", "Copilot event has no type")
        kind = event["type"]
        if kind in {"error", "session.error"} or event.get("is_error"):
            raise CopilotError("copilot_invocation_failed", f"Copilot emitted {kind}")
        if kind == "assistant.message":
            data = event.get("data")
            if isinstance(data, dict) and data.get("phase") == "final_answer":
                if data.get("toolRequests"):
                    raise CopilotError(
                        "copilot_incomplete_reply", "Copilot final answer still requests tool work",
                    )
                text = data.get("content")
                model = data.get("model")
                if not isinstance(text, str) or not text.strip():
                    raise CopilotError("copilot_missing_reply", "Copilot final answer is empty")
                if not isinstance(model, str) or not model:
                    raise CopilotError(
                        "copilot_missing_model", "Copilot supplied no model identity",
                    )
                message = {"text": text, "model": model}
        elif kind == "result":
            terminal = event
    if terminal is None:
        raise CopilotError("copilot_missing_result", "Copilot supplied no terminal result")
    code = terminal.get("exitCode")
    if isinstance(code, bool) or not isinstance(code, int) or code != 0:
        raise CopilotError("copilot_invocation_failed", "Copilot terminal result was unsuccessful")
    session = terminal.get("sessionId")
    if not isinstance(session, str) or not session:
        raise CopilotError("copilot_missing_session", "Copilot supplied no session identity")
    if message is None:
        raise CopilotError("copilot_missing_reply", "Copilot supplied no completed final answer")
    if expected_model is not None and message["model"] != expected_model:
        raise CopilotError(
            "copilot_model_mismatch", "Copilot used a different model than the commanded model"
        )
    return dict(message, session_id=session)
