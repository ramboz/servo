#!/usr/bin/env python3
"""Runtime scorer for a frozen content-fidelity eval component (servo content-fidelity).

Copied into a target's ``.servo/content-fidelity/`` by ``content_fidelity.py
install`` and invoked by the ``score_content_fidelity`` oracle.sh component.
It validates the freeze, gathers the generated text under test per case,
judges fidelity against the frozen reference/rubric ``n`` times with a
**text** model, and prints a conservative lower-bound composite in ``[0.0,
1.0]`` (the oracle.sh contract).

Honesty (servo ADR-0005 / ADR-0024):
- a changed rubric / dataset / model / n / δ / threshold refuses as **stale**
  (exit 2) — never scores against a definition the author did not approve;
- a missing key / unreachable judge / artifact-gathering failure (missing
  file, non-zero command exit) is an **env_error** (exit 2), *never* a silent
  ``0.0`` (which would read as a real quality fail);
- the *definition* is frozen and hashed; the *sampled scores* are not — that
  is the whole point of the n-sample lower bound.

**Gather-once-per-run (ADR-0005 clause 3, this slice's AC3).** The artifact
under test is gathered exactly once per case per ``score()`` call — a file
read or a command execution — and that single gathered text is then judged
``n`` times. Re-gathering per sample would conflate judge stochasticity with
generator stochasticity and defeat the n-sample lower bound's entire purpose
(see the slice's AC3 for the full argument); this mirrors design-eval's
``capture_app`` single-screenshot-then-judge-n-times pattern exactly.

Python 3.9+ standard library only (servo constraint, ADR-0020).
"""
from __future__ import annotations

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
_FAKE_SCORES_ENV = "SERVO_CONTENT_FIDELITY_FAKE_SCORES"  # test/offline hook (no API/CLI)

# content-fidelity's case shape, passed to the shared module's generalized
# definition_hash/artifact_hashes/validate_freeze (ADR-0024).
_CASES_KEY = "cases"
# `artifact_hashes` treats every field here as an on-disk path to hash the
# *content* of — only `reference` is a genuine frozen on-disk artifact.
# `source` is deliberately excluded: it names how to *obtain* the generated
# text under test (a file to read or a command to run), and that target's
# content is expected to legitimately change between scoring runs (AC3's
# gather-once contract) — hashing "the file source.path currently points to"
# would either hash the moving target itself or blow up on a command source
# with no `path` at all.
_REFERENCE_FILE_FIELDS = ("reference",)
# `definition_hash`/`validate_freeze` instead pin each field's own *value*
# (whatever it holds, verbatim, via json.dumps(sort_keys=True) — this works
# for a nested dict like `source` too). AC2 requires the artifact source
# descriptor itself (its type + path/command) to be part of the frozen
# definition: silently swapping a case's `source` after freezing (e.g.
# file->command, or retargeting the path/run args) must refuse as stale,
# even though `source`'s target content is never hashed (see above).
_CASE_PIN_FIELDS = ("reference", "source")
# content-fidelity has no top-level fields beyond what the shared module
# already pins (judge/samples/threshold/cases) — no viewport/screenshot
# concept exists for text, so there is nothing extra to pin here.
_EXTRA_HASH_FIELDS: tuple = ()


def _load_fidelity_eval():
    """Two-candidate probe (servo ADR-0024 / 020-01 Assumption A1): this file
    is copied by ``content_fidelity.py::init()`` into an arbitrary target's
    ``.servo/content-fidelity/`` and must resolve its sibling shared module
    there, independent of CWD or how it was invoked (mirrors this file's own
    ``__file__``-relative ``base_dir`` resolution in ``main()`` below).

    - source layout: ``skills/content-fidelity/score.py`` next to
      ``skills/_common/fidelity_eval.py`` (one directory up, then across);
    - copied-target layout: both files copied flat into the same directory
      (``.servo/content-fidelity/score.py`` +
      ``.servo/content-fidelity/fidelity_eval.py``).
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
    return _fe.definition_hash(config, _CASES_KEY, _CASE_PIN_FIELDS, _EXTRA_HASH_FIELDS)


def artifact_hashes(config: dict, base_dir: Path) -> dict:
    return _fe.artifact_hashes(config, base_dir, _CASES_KEY, _REFERENCE_FILE_FIELDS)


def validate_freeze(config: dict, base_dir: Path) -> None:
    _fe.validate_freeze(config, base_dir, _CASES_KEY, _CASE_PIN_FIELDS, _EXTRA_HASH_FIELDS)


def aggregate_lower_bound(samples, k: float) -> float:
    return _fe.aggregate_lower_bound(samples, k)


# --------------------------------------------------------------------------- #
# Gather (the artifact under test — AC6: file or command; AC3: once per run)
# --------------------------------------------------------------------------- #

def gather_text(base_dir: Path, case: dict) -> str:
    """Gather the generated text under test for ``case``, per its configured
    ``source`` (``{"type": "file", "path": ...}`` or ``{"type": "command",
    "run": [...]}``). Called exactly once per case per ``score()`` call — see
    the module docstring and AC3. Missing file / non-zero command exit is an
    ``EnvError`` (never a silent ``0.0``, consistent with AC4)."""
    source = case.get("source") or {}
    kind = source.get("type")
    if kind == "file":
        rel = source.get("path")
        if not rel:
            raise EnvError(f"case {case.get('id')!r}: source.type=file missing 'path'")
        f = base_dir / rel
        if not f.is_file():
            raise EnvError(f"case {case.get('id')!r}: artifact file missing: {rel}")
        return f.read_text()
    if kind == "command":
        cmd = source.get("run")
        if not cmd:
            raise EnvError(f"case {case.get('id')!r}: source.type=command missing 'run'")
        try:
            proc = subprocess.run(
                cmd, cwd=str(base_dir), capture_output=True, text=True, timeout=180)
        except OSError as e:
            raise EnvError(
                f"case {case.get('id')!r}: generator command could not start: {e}"
            ) from e
        except subprocess.TimeoutExpired:
            raise EnvError(f"case {case.get('id')!r}: generator command timed out") from None
        if proc.returncode != 0:
            raise EnvError(
                f"case {case.get('id')!r}: generator command failed "
                f"(rc={proc.returncode}): {proc.stderr.strip()[:200]}")
        return proc.stdout
    raise EnvError(f"case {case.get('id')!r}: unknown source.type: {kind!r} (expected "
                    "'file' or 'command')")


def _reference_text(base_dir: Path, case: dict) -> str:
    """The case's reference: either inline ``reference`` text or, if it names
    a file that exists under ``base_dir``, that file's contents."""
    ref = case.get("reference", "")
    f = base_dir / ref
    if ref and f.is_file():
        return f.read_text()
    return ref


# --------------------------------------------------------------------------- #
# Judge (the live path; bypassed by the fake-scores hook) — text-only
# --------------------------------------------------------------------------- #

def judge(generated: str, reference: str, config: dict) -> float:
    """One text-judge sample → [0,1]. Dispatches on the frozen
    ``judge.transport``: ``"api"`` (Messages API + ANTHROPIC_API_KEY) or
    ``"cli"`` (headless ``claude -p``, which runs on a Claude subscription
    with no API key). No image content blocks anywhere — the prompt is the
    rubric plus the reference text plus the generated text under test."""
    transport = (config.get("judge") or {}).get("transport", "api")
    if transport == "cli":
        return _judge_cli(generated, reference, config)
    if transport != "api":
        raise EnvError(f"unknown judge.transport: {transport!r} (expected 'api' or 'cli')")
    return _judge_api(generated, reference, config)


def _resolve_claude() -> str:
    """The ``claude`` CLI path: explicit ``SERVO_CONTENT_FIDELITY_CLAUDE_BIN``
    override, else PATH."""
    return os.environ.get("SERVO_CONTENT_FIDELITY_CLAUDE_BIN") or shutil.which("claude")


def _prompt(generated: str, reference: str, config: dict) -> str:
    return (
        config["rubric"].rstrip()
        + "\n\nREFERENCE (the rubric/spec text this should match):\n" + reference.rstrip()
        + "\n\nGENERATED TEXT UNDER TEST:\n" + generated.rstrip()
        + "\n\nReply with ONLY a JSON object, no other text: "
        '{"score": <number 0..1>, "reasoning": "<one sentence>"}.'
    )


def _judge_cli(generated: str, reference: str, config: dict) -> float:
    """One text-judge sample via headless ``claude -p`` (subscription auth,
    no API key)."""
    claude = _resolve_claude()
    if not claude:
        raise EnvError(
            "`claude` CLI not found — set SERVO_CONTENT_FIDELITY_CLAUDE_BIN or add it to PATH")
    prompt = _prompt(generated, reference, config)
    cmd = [claude, "-p", prompt, "--model", config["judge"]["model"],
           "--output-format", "json"]
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


def _judge_api(generated: str, reference: str, config: dict) -> float:
    """One text-judge sample via the Anthropic Messages API (x-api-key)."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvError("ANTHROPIC_API_KEY unset — cannot run the text judge")
    base = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com").rstrip("/")
    j = config["judge"]
    prompt = _prompt(generated, reference, config)

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
    """Composite content-fidelity score for the frozen eval in ``base_dir``."""
    config = json.loads((base_dir / "config.json").read_text())
    validate_freeze(config, base_dir)  # StaleError → exit 2

    n = int(config["samples"]["n"])
    k = float(config["samples"].get("k", 1.0))
    fake = _fake_scores()
    if fake is None:
        transport = (config.get("judge") or {}).get("transport", "api")
        if transport == "api" and not os.environ.get("ANTHROPIC_API_KEY"):
            raise EnvError("ANTHROPIC_API_KEY unset — cannot run the text judge")
        if transport == "cli" and not _resolve_claude():
            raise EnvError(
                "`claude` CLI not found — set SERVO_CONTENT_FIDELITY_CLAUDE_BIN or add it "
                "to PATH")

    per_case = []
    for case in config["cases"]:
        if fake is not None:
            if case["id"] not in fake:
                raise EnvError(f"fake scores missing case {case['id']!r}")
            samples = [float(x) for x in fake[case["id"]]]
        else:
            # Gather exactly once per case per run (AC3) — the same gathered
            # text is judged n times below, never re-gathered per sample.
            generated = gather_text(base_dir, case)
            reference = _reference_text(base_dir, case)
            samples = [judge(generated, reference, config) for _ in range(n)]
        per_case.append((case, samples, aggregate_lower_bound(samples, k)))

    total_w = sum(float(c.get("weight", 1.0)) for c, _, _ in per_case)
    if total_w <= 0:
        raise EnvError("total case weight is zero")
    composite = sum(lb * float(c.get("weight", 1.0)) for c, _, lb in per_case) / total_w
    _ledger(base_dir, config, per_case, composite)
    return max(0.0, min(1.0, composite))


def _ledger(base_dir: Path, config: dict, per_case, composite: float) -> None:
    record = {
        "at": _fe.iso_now(),
        "model": config["judge"]["model"],
        "transport": (config.get("judge") or {}).get("transport", "api"),
        "composite": round(composite, 4),
        "definition_hash": config.get("approved_content_hash"),
        "cases": [
            {"id": c["id"], "samples": [round(x, 4) for x in samp], "lower_bound": round(lb, 4)}
            for c, samp, lb in per_case
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
        print(f"content-fidelity: stale — {e}", file=sys.stderr)
        return EXIT_ENV_ERROR
    except EnvError as e:
        print(f"content-fidelity: env_error — {e}", file=sys.stderr)
        return EXIT_ENV_ERROR
    print(f"{composite:.4f}")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
