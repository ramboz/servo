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

Python 3.10+ standard library only (servo constraint).
"""
from __future__ import annotations

import base64
import hashlib
import json
import math
import os
import shutil
import statistics
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

EXIT_OK = 0
EXIT_ENV_ERROR = 2  # → oracle.sh treats rc=2 as a missing component → gate env_error
_FAKE_SCORES_ENV = "SERVO_DESIGN_EVAL_FAKE_SCORES"  # test/offline hook (no API/browser)


class EnvError(RuntimeError):
    """Infrastructure failure — must surface as exit 2, never a 0.0 score."""


class StaleError(RuntimeError):
    """The frozen definition changed — refuse until re-frozen (exit 2)."""


# --------------------------------------------------------------------------- #
# Freeze (mirrors spec-oracle's 006-04 approval model for the eval case)
# --------------------------------------------------------------------------- #

def sha256_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def definition_hash(config: dict) -> str:
    """Hash the *frozen definition* (ADR-0005 clause 2): judge model + decoding,
    sample count / aggregation / δ, threshold, and the screen set. Excludes the
    hash-bearing/bookkeeping fields so it is stable and self-consistent.
    """
    definition = {
        "judge": config.get("judge"),
        "samples": config.get("samples"),
        "threshold": config.get("threshold"),
        "viewport": config.get("viewport"),
        "app_url": config.get("app_url"),
        "screens": [
            {
                "id": s["id"],
                "reference": s["reference"],
                "setup": s.get("setup"),
                "weight": s.get("weight", 1.0),
            }
            for s in config.get("screens", [])
        ],
    }
    return sha256_text(json.dumps(definition, sort_keys=True))


def artifact_hashes(config: dict, base_dir: Path) -> dict:
    """The rubric (inline) plus every reference + setup file, by relative path."""
    hashes = {"rubric": sha256_text(config.get("rubric", ""))}
    for s in config.get("screens", []):
        for rel in (s.get("reference"), s.get("setup")):
            if rel:
                f = base_dir / rel
                if f.is_file():
                    hashes[rel] = sha256_file(f)
    return hashes


def validate_freeze(config: dict, base_dir: Path) -> None:
    """Refuse (StaleError) unless approved and every frozen part still matches."""
    if config.get("approval_status") != "approved":
        raise StaleError(
            "not approved (approval_status != 'approved') — run `design_eval.py freeze`")
    if definition_hash(config) != config.get("approved_content_hash"):
        raise StaleError(
            "definition changed since freeze (model / n / δ / threshold / screens) — re-freeze")
    frozen = config.get("hashes", {})
    if not frozen:
        raise StaleError("no frozen artifact hashes — re-freeze")
    if frozen.get("rubric") != sha256_text(config.get("rubric", "")):
        raise StaleError("rubric changed since freeze — re-freeze")
    for rel, want in frozen.items():
        if rel == "rubric":
            continue
        f = base_dir / rel
        if not f.is_file():
            raise StaleError(f"frozen artifact missing: {rel} — re-freeze")
        if sha256_file(f) != want:
            raise StaleError(f"frozen artifact changed: {rel} — re-freeze")


# --------------------------------------------------------------------------- #
# Aggregation (ADR-0005 clause 3 — within-run anti-flap)
# --------------------------------------------------------------------------- #

def aggregate_lower_bound(samples, k: float) -> float:
    """Conservative lower bound of the sampled scores: ``mean − k·stderr``,
    clamped to ``[0,1]``. A single sample has stderr 0. This is what makes a
    wobbling judge contribute a high score only when it is *confident across
    samples* — scores within the band read as "not yet" rather than flapping.
    """
    vals = [float(s) for s in samples]
    if not vals:
        raise EnvError("no samples to aggregate")
    mean = statistics.fmean(vals)
    stderr = 0.0 if len(vals) < 2 else statistics.stdev(vals) / math.sqrt(len(vals))
    return max(0.0, min(1.0, mean - k * stderr))


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
        raise EnvError(f"node/playwright unavailable for capture: {e}")
    except subprocess.TimeoutExpired:
        raise EnvError(f"capture timed out for screen {screen['id']!r}")
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
        raise EnvError(f"claude CLI not executable: {e}")
    except subprocess.TimeoutExpired:
        raise EnvError("claude judge timed out")
    if proc.returncode != 0:
        raise EnvError(f"claude judge failed (rc={proc.returncode}): {proc.stderr.strip()[:200]}")
    try:
        envelope = json.loads(proc.stdout)
        if envelope.get("is_error"):
            raise EnvError(f"claude judge error: {str(envelope.get('result'))[:200]}")
        obj = json.loads(_extract_json(envelope.get("result", "")))
        return max(0.0, min(1.0, float(obj["score"])))
    except (KeyError, ValueError, TypeError, json.JSONDecodeError) as e:
        raise EnvError(f"unparseable claude judge response: {e}")


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

    def b64(p: Path) -> str:
        return base64.b64encode(p.read_bytes()).decode("ascii")

    body = {
        "model": j["model"],
        "max_tokens": int(j.get("max_tokens", 1024)),
        "temperature": float(j.get("temperature", 0.0)),
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": b64(app_png)}},
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": b64(ref_png)}},
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
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            payload = json.loads(resp.read())
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise EnvError(f"vision judge request failed: {e}")
    try:
        text = "".join(
            b.get("text", "") for b in payload.get("content", []) if b.get("type") == "text")
        obj = json.loads(_extract_json(text))
        return max(0.0, min(1.0, float(obj["score"])))
    except (KeyError, ValueError, TypeError, json.JSONDecodeError) as e:
        raise EnvError(f"unparseable judge response: {e}")


def _extract_json(text: str) -> str:
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("no JSON object in judge reply")
    return text[start:end + 1]


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
        "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "model": config["judge"]["model"],
        "composite": round(composite, 4),
        "definition_hash": config.get("approved_content_hash"),
        "screens": [
            {"id": s["id"], "samples": [round(x, 4) for x in samp], "lower_bound": round(lb, 4)}
            for s, samp, lb in per_screen
        ],
    }
    try:
        with (base_dir / "ledger.jsonl").open("a") as f:
            f.write(json.dumps(record) + "\n")
    except OSError:
        pass  # ledger is best-effort — never fail the score on a write error


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    # The component invokes `score.py <target>`; the frozen eval lives beside this
    # file, so the base dir is always this script's directory.
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
