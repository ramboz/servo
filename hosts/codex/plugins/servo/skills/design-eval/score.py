#!/usr/bin/env python3
"""Runtime scorer for a frozen design-fidelity eval component (servo design-eval).

Copied into a target's ``.servo/design-eval/`` by ``design_eval.py install`` and
invoked by the ``score_design_fidelity`` oracle.sh component. It validates the
freeze, screenshots the running app per screen, judges fidelity against the
frozen reference ``n`` times with a vision model, and prints a conservative
lower-bound composite in ``[0.0, 1.0]`` (the oracle.sh contract).

Honesty (servo ADR-0005 / ADR-0006):
- a changed rubric / dataset / model / n / δ / threshold refuses as **stale**
  (exit 2) — never scores against a definition the author did not approve;
- a missing key / unreachable judge / browser failure is an **env_error**
  (exit 2), *never* a silent ``0.0`` (which would read as a real quality fail);
- the *definition* is frozen and hashed; the *sampled scores* are not — that is
  the whole point of the n-sample lower bound.

Python 3.9+ standard library only (servo constraint, ADR-0020).
"""
from __future__ import annotations

import base64
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time  # noqa: F401 — re-exposed as `score.time` for test monkeypatching (see _post_with_retry)
import urllib.error
import urllib.request
from pathlib import Path

EXIT_OK = 0
EXIT_ENV_ERROR = 2  # → oracle.sh treats rc=2 as a missing component → gate env_error
_FAKE_SCORES_ENV = "SERVO_DESIGN_EVAL_FAKE_SCORES"  # test/offline hook (no API/browser)

# design-eval's case shape, passed to the shared module's generalized
# definition_hash/artifact_hashes/validate_freeze (ADR-0024).
_CASES_KEY = "screens"
_CASE_FILE_FIELDS = ("reference", "setup")
# design-eval-specific top-level field pinned into the frozen definition hash
# (a vision/screenshot concept the shared module itself knows nothing about).
_EXTRA_HASH_FIELDS = ("viewport",)


def _load_fidelity_eval():
    """Two-candidate probe (servo ADR-0024 / 020-01 Assumption A1): this file
    is copied by ``design_eval.py::init()`` into an arbitrary target's
    ``.servo/design-eval/`` and must resolve its sibling shared module there,
    independent of CWD or how it was invoked (mirrors this file's own
    ``__file__``-relative ``base_dir`` resolution in ``main()`` below).

    - source layout: ``skills/design-eval/score.py`` next to
      ``skills/_common/fidelity_eval.py`` (one directory up, then across);
    - copied-target layout: both files copied flat into the same directory
      (``.servo/design-eval/score.py`` + ``.servo/design-eval/fidelity_eval.py``).
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
    return _fe.definition_hash(config, _CASES_KEY, _CASE_FILE_FIELDS, _EXTRA_HASH_FIELDS)


def artifact_hashes(config: dict, base_dir: Path) -> dict:
    return _fe.artifact_hashes(config, base_dir, _CASES_KEY, _CASE_FILE_FIELDS)


def validate_freeze(config: dict, base_dir: Path) -> None:
    _fe.validate_freeze(config, base_dir, _CASES_KEY, _CASE_FILE_FIELDS, _EXTRA_HASH_FIELDS)


def aggregate_lower_bound(samples, k: float) -> float:
    return _fe.aggregate_lower_bound(samples, k)


# --------------------------------------------------------------------------- #
# Capture + judge (the live path; bypassed by the fake-scores hook)
# --------------------------------------------------------------------------- #

def capture_app(base_dir: Path, screen: dict) -> Path:
    """Screenshot the running app at the screen's seeded state via capture.mjs."""
    out = base_dir / "shots" / f"app-{screen['id']}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["node", str(base_dir / "capture.mjs"), "--screen", screen["id"], "--out", str(out)]
    try:
        proc = subprocess.run(cmd, cwd=str(base_dir), capture_output=True, text=True, timeout=180)
    except FileNotFoundError as e:
        raise EnvError(f"node/playwright unavailable for capture: {e}") from e
    except subprocess.TimeoutExpired:
        raise EnvError(f"capture timed out for screen {screen['id']!r}") from None
    if proc.returncode != 0 or not out.is_file():
        raise EnvError(
            f"capture failed for screen {screen['id']!r}: {proc.stderr.strip()[:200]}")
    return out


def judge(app_png: Path, ref_png: Path, config: dict) -> float:
    """One vision-judge sample → [0,1]. Dispatches on the frozen ``judge.transport``:
    ``"api"`` (Messages API + ANTHROPIC_API_KEY) or ``"cli"`` (headless ``claude -p``,
    which runs on a Claude subscription with no API key)."""
    transport = (config.get("judge") or {}).get("transport", "api")
    if transport == "cli":
        return _judge_cli(app_png, ref_png, config)
    if transport != "api":
        raise EnvError(f"unknown judge.transport: {transport!r} (expected 'api' or 'cli')")
    return _judge_api(app_png, ref_png, config)


def _resolve_claude() -> str | None:
    """The ``claude`` CLI path: explicit ``SERVO_DESIGN_EVAL_CLAUDE_BIN`` override, else PATH."""
    return os.environ.get("SERVO_DESIGN_EVAL_CLAUDE_BIN") or shutil.which("claude")


def _judge_cli(app_png: Path, ref_png: Path, config: dict) -> float:
    """One vision-judge sample via headless ``claude -p`` (subscription auth, no API
    key): Claude reads the two PNGs by path and returns the score as JSON."""
    claude = _resolve_claude()
    if not claude:
        raise EnvError(
            "`claude` CLI not found — set SERVO_DESIGN_EVAL_CLAUDE_BIN or add it to PATH")
    prompt = (
        config["rubric"].rstrip()
        + "\n\nRead these two images with the Read tool:\n"
        f"- FIRST (the implemented app screen): {app_png.resolve()}\n"
        f"- SECOND (the design reference): {ref_png.resolve()}\n\n"
        "Then reply with ONLY a JSON object, no other text: "
        '{"score": <number 0..1>, "reasoning": "<one sentence>"}.'
    )
    cmd = [claude, "-p", prompt, "--model", config["judge"]["model"],
           "--allowedTools", "Read", "--output-format", "json"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300,
                              cwd=str(app_png.parent.parent))
    except FileNotFoundError as e:
        raise EnvError(f"claude CLI not executable: {e}") from e
    except subprocess.TimeoutExpired:
        raise EnvError("claude judge timed out") from None
    if proc.returncode != 0:
        raise EnvError(f"claude judge failed (rc={proc.returncode}): {proc.stderr.strip()[:200]}")
    try:
        envelope = json.loads(proc.stdout)
        if envelope.get("is_error"):
            raise EnvError(f"claude judge error: {str(envelope.get('result'))[:200]}")
        obj = json.loads(_extract_json(envelope.get("result", "")))
        return max(0.0, min(1.0, float(obj["score"])))
    except (KeyError, ValueError, TypeError, json.JSONDecodeError) as e:
        raise EnvError(f"unparseable claude judge response: {e}") from e


def _post_with_retry(req, timeout: int, attempts: int = 3) -> dict:
    """POST ``req`` via the shared HTTP-retry wrapper (module-level ``urllib``/
    ``time`` stay imported here, not just in ``_fe``, so tests can monkeypatch
    ``score.urllib.request.urlopen``/``score.time.sleep`` — both point at the
    same singleton stdlib modules ``_fe`` calls through, so the patch applies
    either way)."""
    return _fe._post_with_retry(req, timeout, attempts)


def _judge_api(app_png: Path, ref_png: Path, config: dict) -> float:
    """One vision-judge sample via the Anthropic Messages API (x-api-key)."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvError("ANTHROPIC_API_KEY unset — cannot run the vision judge")
    base = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com").rstrip("/")
    j = config["judge"]
    prompt = (
        config["rubric"].rstrip()
        + "\n\nThe FIRST image is the implemented app screen; the SECOND is the "
        "design reference. Reply with ONLY a JSON object: "
        '{"score": <number 0..1>, "reasoning": "<one sentence>"}.'
    )

    def img(p: Path) -> dict:
        data = base64.b64encode(p.read_bytes()).decode("ascii")
        return {"type": "image",
                "source": {"type": "base64", "media_type": "image/png", "data": data}}

    body = {
        "model": j["model"],
        "max_tokens": int(j.get("max_tokens", 1024)),
        "temperature": float(j.get("temperature", 0.0)),
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                img(app_png),
                img(ref_png),
            ],
        }],
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
    try:
        text = "".join(
            b.get("text", "") for b in payload.get("content", []) if b.get("type") == "text")
        obj = json.loads(_extract_json(text))
        return max(0.0, min(1.0, float(obj["score"])))
    except (KeyError, ValueError, TypeError, json.JSONDecodeError) as e:
        raise EnvError(f"unparseable judge response: {e}") from e


def _extract_json(text: str) -> str:
    return _fe._extract_json(text)


# --------------------------------------------------------------------------- #
# Score (the composite)
# --------------------------------------------------------------------------- #

def _fake_scores():
    raw = os.environ.get(_FAKE_SCORES_ENV)
    return json.loads(raw) if raw else None


def score(base_dir: Path) -> float:
    """Composite design-fidelity score for the frozen eval in ``base_dir``."""
    config = json.loads((base_dir / "config.json").read_text())
    validate_freeze(config, base_dir)  # StaleError → exit 2

    n = int(config["samples"]["n"])
    k = float(config["samples"].get("k", 1.0))
    fake = _fake_scores()
    if fake is None:
        transport = (config.get("judge") or {}).get("transport", "api")
        if transport == "api" and not os.environ.get("ANTHROPIC_API_KEY"):
            raise EnvError("ANTHROPIC_API_KEY unset — cannot run the vision judge")
        if transport == "cli" and not _resolve_claude():
            raise EnvError(
                "`claude` CLI not found — set SERVO_DESIGN_EVAL_CLAUDE_BIN or add it to PATH")

    per_screen = []
    for screen in config["screens"]:
        if fake is not None:
            if screen["id"] not in fake:
                raise EnvError(f"fake scores missing screen {screen['id']!r}")
            samples = [float(x) for x in fake[screen["id"]]]
        else:
            app_png = capture_app(base_dir, screen)
            ref_png = base_dir / screen["reference"]
            if not ref_png.is_file():
                raise EnvError(f"reference missing: {screen['reference']}")
            samples = [judge(app_png, ref_png, config) for _ in range(n)]
        per_screen.append((screen, samples, aggregate_lower_bound(samples, k)))

    total_w = sum(float(s.get("weight", 1.0)) for s, _, _ in per_screen)
    if total_w <= 0:
        raise EnvError("total screen weight is zero")
    composite = sum(lb * float(s.get("weight", 1.0)) for s, _, lb in per_screen) / total_w
    _ledger(base_dir, config, per_screen, composite)
    return max(0.0, min(1.0, composite))


def _ledger(base_dir: Path, config: dict, per_screen, composite: float) -> None:
    record = {
        "at": _fe.iso_now(),
        "model": config["judge"]["model"],
        "transport": (config.get("judge") or {}).get("transport", "api"),
        "composite": round(composite, 4),
        "definition_hash": config.get("approved_content_hash"),
        "screens": [
            {"id": s["id"], "samples": [round(x, 4) for x in samp], "lower_bound": round(lb, 4)}
            for s, samp, lb in per_screen
        ],
    }
    _fe.write_ledger(base_dir, record)


def main(argv=None) -> int:
    # The component invokes `score.py <target>`, but the frozen eval lives beside
    # this file, so the base dir is always this script's directory (the arg is
    # accepted for the oracle.sh contract and intentionally ignored). `argv` stays
    # in the signature so tests can call `main([])` without touching `sys.argv`.
    base_dir = Path(__file__).resolve().parent
    try:
        composite = score(base_dir)
    except StaleError as e:
        print(f"design-eval: stale — {e}", file=sys.stderr)
        return EXIT_ENV_ERROR
    except EnvError as e:
        print(f"design-eval: env_error — {e}", file=sys.stderr)
        return EXIT_ENV_ERROR
    print(f"{composite:.4f}")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
