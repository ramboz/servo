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
# 027-02: capture-provider selector (env overrides config, mirroring
# SERVO_DESIGN_EVAL_CLAUDE_BIN). Environmental, never frozen (ADR-0031/0032 §6).
_CAPTURE_TRANSPORT_ENV = "SERVO_DESIGN_EVAL_CAPTURE_TRANSPORT"
_DEFAULT_CAPTURE_TRANSPORT = "web"

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
salient_stderr = _fe.salient_stderr
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

# 026-01 / ADR-0031: the preflight. Runs on the machine that actually fails —
# CI, a Routine, a detached loop — where no human is present to be asked.
_PREFLIGHT_SPECIFIER = "playwright"  # 026-02 is DEFERRED; this is the specifier.


def preflight_capture(base_dir: Path, specifier: str = _PREFLIGHT_SPECIFIER) -> None:
    """Probe node + the browser library before spawning capture; raise EnvError
    with an actionable remedy naming this machine's exact fix.

    FAILS OPEN (AC1/AC6): "library absent" is reported only on a token-confirmed
    MODULE_NOT_FOUND. Any other non-zero exit proceeds to capture, so a quirk
    such as NODE_OPTIONS=--input-type=module (which makes `require` undefined)
    can never be misreported as a missing library on a machine where capture
    would have succeeded. Performs NO browser launch (AC2/AC3).
    """
    if shutil.which("node") is None:
        raise EnvError(
            "node is not on PATH — design-eval captures screenshots with "
            "Playwright, which needs Node. Install Node, or set the capture "
            "component aside.")
    try:
        probe = subprocess.run(
            ["node", "-e", f"require.resolve({specifier!r})"],
            capture_output=True, text=True, timeout=30,
            cwd=str(base_dir),   # AC1: match capture_app's spawn, so CJS resolution
        )                        # walks the same chain as capture.mjs's ESM import
    except (OSError, subprocess.SubprocessError):
        return                   # fail open — let capture be authoritative
    if probe.returncode != 0 and "MODULE_NOT_FOUND" in (probe.stderr or ""):
        raise EnvError(
            f"{specifier!r} is not installed in this project — design-eval uses "
            f"the target's Playwright. Run:  npm i -D {specifier} && "
            f"npx playwright install chromium")


_ATTEST_MARKER = "##servo-capture:"


def parse_attestation(stdout: str) -> dict | None:
    """First marker line only — never `_extract_json` (026-03 AC1a).

    `capture.mjs` runs the ADOPTER's setup module in-process, so their
    `console.log` shares this stdout. Non-matching lines are DISCARDED, not
    treated as failure, so a rich setup script cannot decay provenance to
    `not_attested` and misattribute their logging to a Playwright problem.
    """
    for line in (stdout or "").splitlines():
        idx = line.find(_ATTEST_MARKER)
        if idx == -1:
            continue
        try:
            payload = json.loads(line[idx + len(_ATTEST_MARKER):])
        except (ValueError, TypeError):
            return None
        # An adopter can echo the marker (AC1a anticipates it). A non-object
        # payload would make `.get` raise AttributeError, which is NOT in
        # main()'s catch tuple — a raw traceback and a failed score, violating
        # AC4's "provenance is never load-bearing".
        return payload if isinstance(payload, dict) else None
    return None


def _run_stamp() -> str:
    """A per-run, filesystem-safe, human-sortable token for shot filenames.

    027-01 AC1: shots must be RETAINED, not clobbered — so each run's screenshot
    needs a unique name. Microsecond resolution makes two back-to-back `score()`
    calls collide-free without a new import; shots are unfrozen outputs (027-01
    DoR: no ADR, not part of the frozen definition), so a wall-clock stamp is
    fine. Kept human-readable on purpose — the point of retention is that an
    operator can open the exact image behind a low score.
    """
    t = time.time()
    return time.strftime("%Y%m%dT%H%M%S", time.localtime(t)) + f"-{int((t % 1) * 1e6):06d}"


def _capture_web(base_dir: Path, screen: dict, run_id: str | None = None) -> tuple[Path, dict | None]:
    """The **web** capture provider (027-02): the original Playwright path, spawning
    ``node capture.mjs`` — unchanged in behaviour, now one provider behind the seam.

    026-03 AC2c: the attestation is RETURNED, never stashed in a module global —
    a global would be last-write-wins across screens and silently re-create the
    single-field collapse per-screen provenance exists to prevent.

    027-01 AC1: the shot filename is stamped (`app-<id>-<run_id>.png`) so a later
    run does not overwrite it, and stays DIRECTLY under `shots/` (path depth
    unchanged) to preserve the `_judge_cli` cwd contract (`app_png.parent.parent`
    == base_dir). `run_id` defaults to a fresh per-call stamp so the standalone
    callers (and tests) that pass only `(base_dir, screen)` still get retention;
    `score()` passes one shared stamp so all screens in a run group together.
    """
    stamp = run_id or _run_stamp()
    out = base_dir / "shots" / f"app-{screen['id']}-{stamp}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["node", str(base_dir / "capture.mjs"), "--screen", screen["id"], "--out", str(out)]
    try:
        proc = subprocess.run(cmd, cwd=str(base_dir), capture_output=True, text=True, timeout=180)
    except FileNotFoundError as e:
        raise EnvError(f"node/playwright unavailable for capture: {e}") from e
    except subprocess.TimeoutExpired:
        raise EnvError(f"capture timed out for screen {screen['id']!r}") from None
    if proc.returncode != 0 or not out.is_file():
        # 026-01 AC4: salient-line surfacing, not a blind head slice. Applied to
        # node-produced stderr ONLY (AC4a) — the judge path at _judge_cli keeps
        # `[:200]` deliberately, since these predicates parse node's grammar.
        raise EnvError(
            f"capture failed for screen {screen['id']!r}: {salient_stderr(proc.stderr)}")
    return out, parse_attestation(proc.stdout)


# 027-02: the capture-provider seam. Each provider is invoked per screen and
# returns (png, attestation) with the same contract as the old `capture_app`.
# Later slices (027-03..05) register `command` / `android` / `ios` here without
# touching the scoring path. Web is the default and the only provider today.
_CAPTURE_PROVIDERS = {
    "web": _capture_web,
}


def _resolve_capture_transport(config: dict) -> str:
    """Which capture provider to use, by precedence: the
    ``SERVO_DESIGN_EVAL_CAPTURE_TRANSPORT`` env var, then ``config.capture.transport``,
    then the ``"web"`` default. Name resolution only — validity is checked at
    dispatch (`capture_app`) / run start (`score`), so an unknown name fails
    closed rather than silently defaulting to web."""
    return (
        os.environ.get(_CAPTURE_TRANSPORT_ENV)
        or (config.get("capture") or {}).get("transport")
        or _DEFAULT_CAPTURE_TRANSPORT
    )


def capture_app(base_dir: Path, screen: dict, run_id: str | None = None,
                provider: str = _DEFAULT_CAPTURE_TRANSPORT) -> tuple[Path, dict | None]:
    """Screenshot the app at the screen's seeded state; return (png, attestation).

    027-02: dispatches to the selected capture provider. `provider` defaults to
    ``"web"`` so the standalone callers (and tests) that pass only
    ``(base_dir, screen[, run_id])`` keep the original behaviour. An unknown
    provider fails **closed** to `EnvError` (→ rc 2 env_error) — never a silent
    fall-through to web.
    """
    fn = _CAPTURE_PROVIDERS.get(provider)
    if fn is None:
        known = ", ".join(sorted(_CAPTURE_PROVIDERS))
        raise EnvError(f"unknown capture provider {provider!r} (known: {known})")
    return fn(base_dir, screen, run_id)


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
    except (KeyError, ValueError, TypeError) as e:  # JSONDecodeError ⊂ ValueError
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
    except (KeyError, ValueError, TypeError) as e:  # JSONDecodeError ⊂ ValueError
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
    # 027-02: capture provider selected once per run (env > config > "web").
    # None on the fake arm — no capture ran, so no provider is exercised.
    provider = None
    if fake is None:
        transport = (config.get("judge") or {}).get("transport", "api")
        if transport == "api" and not os.environ.get("ANTHROPIC_API_KEY"):
            raise EnvError("ANTHROPIC_API_KEY unset — cannot run the vision judge")
        if transport == "cli" and not _resolve_claude():
            raise EnvError(
                "`claude` CLI not found — set SERVO_DESIGN_EVAL_CLAUDE_BIN or add it to PATH")
        # 027-02 AC4: resolve + validate the provider up front, so an unknown one
        # fails closed (env_error) BEFORE any preflight or capture — never a
        # silent 0.0, never a fall-through to web.
        provider = _resolve_capture_transport(config)
        if provider not in _CAPTURE_PROVIDERS:
            known = ", ".join(sorted(_CAPTURE_PROVIDERS))
            raise EnvError(f"unknown capture provider {provider!r} (known: {known})")
        # 027-02: the node/Playwright preflight is the WEB provider's precheck;
        # a non-web provider brings its own environment, so gate it to web.
        # AC5 (027-01): live-capture arm only, so the fake-scores path is
        # unaffected. AC2 (026-01): once per run, not per screen — no latch here.
        if provider == "web":
            preflight_capture(base_dir)

    # 027-01 AC1: one stamp per run, shared across screens, so a run's shots
    # group together and never clobber a prior run's.
    run_id = _run_stamp()
    per_screen = []
    for screen in config["screens"]:
        if fake is not None:
            if screen["id"] not in fake:
                raise EnvError(f"fake scores missing screen {screen['id']!r}")
            samples = [float(x) for x in fake[screen["id"]]]
            attestation = None   # no browser ran at all -> not_captured
            shot = None          # 027-01 AC3: no browser ran -> no shot, honestly
        else:
            app_png, attestation = capture_app(base_dir, screen, run_id, provider)
            # 027-01 AC2: record the exact PNG this screen was judged on, as a
            # path relative to base_dir (the ledger's own root).
            shot = app_png.relative_to(base_dir).as_posix()
            ref_png = base_dir / screen["reference"]
            if not ref_png.is_file():
                raise EnvError(f"reference missing: {screen['reference']}")
            samples = [judge(app_png, ref_png, config) for _ in range(n)]
        per_screen.append(
            (screen, samples, aggregate_lower_bound(samples, k), attestation, shot))

    total_w = sum(float(s.get("weight", 1.0)) for s, _, _, _, _ in per_screen)
    if total_w <= 0:
        raise EnvError("total screen weight is zero")
    composite = sum(lb * float(s.get("weight", 1.0)) for s, _, lb, _a, _sh in per_screen) / total_w
    _ledger(base_dir, config, per_screen, composite,
            fake_run=fake is not None, provider=provider)
    return max(0.0, min(1.0, composite))


def _provenance(att, *, fake_run: bool) -> dict:
    """Reason tokens, not a bare "unknown" (026-03 AC5): `not_captured` (no
    browser ran — the fake-scores path still writes a row) must stay
    distinguishable from `not_attested` (capture happened, identity
    unavailable), because the remedies differ."""
    base = {"engine": None, "engine_version": None, "capture_transport": None,
            "provenance": None, "provenance_error": None}
    if att is None:
        # `fake_run` is passed in from score() — NOT derived from `att`, which
        # would make this branch and the next indistinguishable and silently
        # report a real capture's missing line as "no browser ran".
        return {**base, "provenance": "not_captured" if fake_run else "not_attested"}
    if not att.get("engine"):
        return {**base, "capture_transport": att.get("transport"),
                "provenance": "not_attested", "provenance_error": att.get("error")}
    return {**base, "engine": att.get("engine"), "engine_version": att.get("version"),
            "capture_transport": att.get("transport"), "provenance": "attested"}


def _ledger(base_dir: Path, config: dict, per_screen, composite: float,
            *, fake_run: bool, provider: str | None) -> None:
    # `fake_run` is keyword-only and REQUIRED on purpose: a default would let a
    # future caller silently get `not_attested` on a synthetic run — the same
    # class of error as deriving it from `att`, which this replaced. `provider`
    # is likewise required keyword-only for the same reason (027-02).
    record = {
        "at": _fe.iso_now(),
        "model": config["judge"]["model"],
        "transport": (config.get("judge") or {}).get("transport", "api"),
        # 027-02 AC5: which capture provider produced this run's shots — advisory,
        # never hashed (ADR-0032 §6). `null` on the fake arm (no capture ran).
        "capture_provider": provider,
        "composite": round(composite, 4),
        "definition_hash": config.get("approved_content_hash"),
        # 026-03 AC2/AC2a: provenance is PER SCREEN (capture_app runs once per
        # screen, so a row has N attestations), under `capture_transport` —
        # distinct from the top-level `transport`, which means the JUDGE
        # transport in every historical row.
        "screens": [
            {
                "id": s["id"],
                "samples": [round(x, 4) for x in samp],
                "lower_bound": round(lb, 4),
                # 027-01 AC2/AC3: the exact shot this screen was judged on
                # (relative to base_dir), or null when no browser ran.
                "shot": shot,
                **_provenance(att, fake_run=fake_run),
            }
            for s, samp, lb, att, shot in per_screen
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
    except (OSError, ValueError, KeyError, TypeError) as e:
        # A malformed/missing config.json, or one lacking `judge`/`screens`,
        # would otherwise escape as a raw traceback. oracle.sh maps any non-zero
        # rc to env_error anyway, so honesty was never at risk — but the operator
        # deserves the same `design-eval: env_error — …` line as every other
        # failure, not a stack trace.
        print(f"design-eval: env_error — malformed eval definition: {e}", file=sys.stderr)
        return EXIT_ENV_ERROR
    print(f"{composite:.4f}")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
