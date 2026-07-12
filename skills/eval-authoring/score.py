#!/usr/bin/env python3
"""Generic judge-scorer core for a servo-authored eval component
(`/servo:eval-authoring`, slice 008-02).

Grows across 008-02 -> 008-04: this slice (008-02) ships only the **judge
path** — turn a rubric plus one candidate string into a judge call, and parse
its reply into the richer structured output `{score, reasoning, strengths,
weaknesses}` this generic surface targets (a broader schema than
`content-fidelity/score.py`'s `{score, reasoning}` — AC2). The n-sample
composite (`score()`), the artifact-gather step, the `validate_freeze` call
site, the ledger, and the `oracle.sh` install splice all build on the
primitives below once the dataset (008-03) and frozen parameters (008-04)
exist to drive them — deliberately not built here (see the module-end note).

Honesty (servo ADR-0005): a malformed/unparseable/unreachable judge reply
raises `EnvError` — **never a silent 0.0** (mirrors content-fidelity's own
contract exactly; see AC2 and this module's tests in
`test_eval_authoring.py`).

Reuses `skills/_common/fidelity_eval.py` (ADR-0024) for `_extract_json` /
`_post_with_retry` / `EnvError` / the freeze+hash primitives, so a rubric
authored here slots into the exact shape the harness already hashes/freezes
(AC5) — no reshaping when 008-04 emits the final definition or spec-006
compiles it.

Python 3.9+ standard library only (servo constraint, ADR-0020).
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import time  # noqa: F401 — re-exposed as `score.time` for test monkeypatching (see _post_with_retry)
import urllib.error
import urllib.request
from pathlib import Path

# Reserved for 008-04's n-sample composite scorer (mirrors content-fidelity's
# `_FAKE_SCORES_ENV` offline-test hook); this slice's tests monkeypatch
# `_post_with_retry` directly since there is no composite to bypass yet.
_FAKE_SCORES_ENV = "SERVO_EVAL_AUTHORING_FAKE_SCORES"

# The case shape this generic surface targets mirrors content-fidelity's
# (`reference` + `source`) — the closest existing precedent for a
# text-judged case (AC5); 008-03 fills in the actual case list.
_CASES_KEY = "cases"
_REFERENCE_FILE_FIELDS = ("reference",)
_CASE_PIN_FIELDS = ("reference", "source")
_EXTRA_HASH_FIELDS: tuple = ()


def _load_fidelity_eval():
    """Two-candidate probe (mirrors `content-fidelity/score.py`'s own): this
    file may eventually be copied into a target's `.servo/<eval>/` directory
    (a future install path) and must resolve its sibling shared module there,
    independent of CWD or how it was invoked.

    - source layout: `skills/eval-authoring/score.py` next to
      `skills/_common/fidelity_eval.py` (one directory up, then across);
    - copied-target layout: both files copied flat into the same directory.
    """
    here = Path(__file__).resolve().parent
    for candidate in (here.parent / "_common" / "fidelity_eval.py", here / "fidelity_eval.py"):
        if candidate.is_file():
            spec = importlib.util.spec_from_file_location("fidelity_eval", candidate)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
    raise ModuleNotFoundError(
        "fidelity_eval.py not found next to score.py nor at ../_common/fidelity_eval.py")


_fe = _load_fidelity_eval()

EnvError = _fe.EnvError
StaleError = _fe.StaleError
sha256_text = _fe.sha256_text
sha256_file = _fe.sha256_file


def definition_hash(config: dict) -> str:
    """AC5: the exact harness definition hash — judge/samples/threshold/
    cases, unchanged shape, so 008-04 can freeze this and spec-006 can
    compile it with no reshaping."""
    return _fe.definition_hash(config, _CASES_KEY, _CASE_PIN_FIELDS, _EXTRA_HASH_FIELDS)


def artifact_hashes(config: dict, base_dir: Path) -> dict:
    return _fe.artifact_hashes(config, base_dir, _CASES_KEY, _REFERENCE_FILE_FIELDS)


def validate_freeze(config: dict, base_dir: Path) -> None:
    _fe.validate_freeze(config, base_dir, _CASES_KEY, _CASE_PIN_FIELDS, _EXTRA_HASH_FIELDS)


# --------------------------------------------------------------------------- #
# Judge (AC2 — the structured-output contract; text-only, no case gathering
# yet — that is 008-03/008-04's job)
# --------------------------------------------------------------------------- #

def judge(candidate: str, config: dict) -> dict:
    """One judge sample against `config["rubric"]`, dispatched on the frozen
    `judge.transport`: `"api"` (Messages API + ANTHROPIC_API_KEY) or `"cli"`
    (headless `claude -p`, subscription auth, no API key) — the same two
    transports `content-fidelity/score.py` supports.

    Returns the structured reply `{"score": float in [0,1], "reasoning": str,
    "strengths": [str], "weaknesses": [str]}` (AC2's richer schema). Never
    returns a silent `0.0` — a malformed/unreachable/unparseable reply raises
    `EnvError` instead (ADR-0005).
    """
    transport = (config.get("judge") or {}).get("transport", "api")
    if transport == "cli":
        return _judge_cli(candidate, config)
    if transport != "api":
        raise EnvError(f"unknown judge.transport: {transport!r} (expected 'api' or 'cli')")
    return _judge_api(candidate, config)


def _resolve_claude() -> str:
    """The `claude` CLI path: explicit `SERVO_EVAL_AUTHORING_CLAUDE_BIN`
    override, else PATH."""
    return os.environ.get("SERVO_EVAL_AUTHORING_CLAUDE_BIN") or shutil.which("claude")


def _prompt(candidate: str, config: dict) -> str:
    """The judge prompt: the authored rubric plus the candidate text under
    test, asking for AC2's four-field structured JSON reply."""
    return (
        config["rubric"].rstrip()
        + "\n\nCANDIDATE UNDER TEST:\n" + candidate.rstrip()
        + "\n\nReply with ONLY a JSON object, no other text: "
        '{"score": <number 0..1>, "reasoning": "<one or two sentences>", '
        '"strengths": ["<short phrase>", ...], "weaknesses": ["<short phrase>", ...]}.'
    )


def _parse_judge_reply(text: str) -> dict:
    """Parse a judge reply into AC2's structured shape. `score` is the one
    load-bearing field — required, and clamped to `[0,1]`; a missing or
    non-numeric `score` raises `EnvError`. `reasoning`/`strengths`/
    `weaknesses` are captured verbatim (defaulting to an empty value when the
    judge omits them). Any parse failure raises `EnvError` — never a silent
    `0.0` (ADR-0005 / AC2)."""
    try:
        obj = json.loads(_extract_json(text))
        clamped_score = max(0.0, min(1.0, float(obj["score"])))
    except (KeyError, ValueError, TypeError, json.JSONDecodeError) as e:
        raise EnvError(f"unparseable judge response: {e}") from e
    return {
        "score": clamped_score,
        "reasoning": str(obj.get("reasoning", "")),
        "strengths": list(obj.get("strengths") or []),
        "weaknesses": list(obj.get("weaknesses") or []),
    }


def _judge_cli(candidate: str, config: dict) -> dict:
    """One judge sample via headless `claude -p` (subscription auth, no API
    key)."""
    claude = _resolve_claude()
    if not claude:
        raise EnvError(
            "`claude` CLI not found — set SERVO_EVAL_AUTHORING_CLAUDE_BIN or add it to PATH")
    prompt = _prompt(candidate, config)
    cmd = [claude, "-p", prompt, "--model", config["judge"]["model"], "--output-format", "json"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except FileNotFoundError as e:
        raise EnvError(f"claude CLI not executable: {e}") from e
    except subprocess.TimeoutExpired:
        raise EnvError("claude judge timed out") from None
    if proc.returncode != 0:
        raise EnvError(f"claude judge failed (rc={proc.returncode}): {proc.stderr.strip()[:200]}")
    try:
        envelope = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise EnvError(f"unparseable claude judge envelope: {e}") from e
    if envelope.get("is_error"):
        raise EnvError(f"claude judge error: {str(envelope.get('result'))[:200]}")
    return _parse_judge_reply(envelope.get("result", ""))


def _post_with_retry(req, timeout: int, attempts: int = 3) -> dict:
    """POST `req` via the shared HTTP-retry wrapper (module-level `urllib`/
    `time` stay imported here, not just in `_fe`, so tests can monkeypatch
    `score.urllib.request.urlopen`/`score.time.sleep` — both point at the
    same singleton stdlib modules `_fe` calls through, so the patch applies
    either way)."""
    return _fe._post_with_retry(req, timeout, attempts)


def _judge_api(candidate: str, config: dict) -> dict:
    """One judge sample via the Anthropic Messages API (x-api-key), sampled
    at low temperature (AC2)."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvError("ANTHROPIC_API_KEY unset — cannot run the judge")
    base = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com").rstrip("/")
    j = config["judge"]
    prompt = _prompt(candidate, config)

    body = {
        "model": j["model"],
        "max_tokens": int(j.get("max_tokens", 1024)),
        "temperature": float(j.get("temperature", 0.0)),
        "messages": [{"role": "user", "content": prompt}],
    }
    req = urllib.request.Request(
        base + "/v1/messages",
        data=json.dumps(body).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
    )
    payload = _post_with_retry(req, timeout=180)
    text = "".join(
        b.get("text", "") for b in payload.get("content", []) if b.get("type") == "text")
    return _parse_judge_reply(text)


def _extract_json(text: str) -> str:
    return _fe._extract_json(text)


# --------------------------------------------------------------------------- #
# Seam for 008-04: the n-sample composite (`score()`), the artifact-gather
# step, the `validate_freeze` call site, the ledger, and the `oracle.sh`
# install splice all build on the primitives above once the dataset (008-03)
# and frozen parameters (008-04) exist to drive them. Deliberately not built
# here — see the module docstring.
# --------------------------------------------------------------------------- #
