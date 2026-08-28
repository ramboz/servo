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
import hashlib
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


_pc = None  # 027-04 PNG cropper — loaded LAZILY on first native-provider use (below)


def _pngcrop():
    """Lazily load + cache the sibling stdlib PNG cropper (027-04).

    Loaded on demand — NOT at module import — because only the native (android/ios)
    providers crop, so `score.py` must import and run the web/command/fake-scores
    paths WITHOUT `pngcrop.py` present. (Regression fixed under 027-04 reopen: the
    original module-load `_pc = _load_pngcrop()` crashed every import lacking the
    sibling, breaking `_common/test_fidelity_eval.py::ImportResolutionTests`, which
    copy score.py + fidelity_eval.py alone.) `design_eval.py::init()` vends
    `pngcrop.py`, so it is a sibling in a real native install; a native run without
    it fails closed to `EnvError`, not a bare ModuleNotFoundError traceback."""
    global _pc
    if _pc is None:
        here = Path(__file__).resolve().parent
        candidate = here / "pngcrop.py"
        if not candidate.is_file():
            raise EnvError(
                "pngcrop.py not found next to score.py — the native capture providers "
                "need it for chrome-frame cropping (vended by design_eval.py init()).")
        spec = importlib.util.spec_from_file_location("pngcrop", candidate)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _pc = module
    return _pc


_fe = _load_fidelity_eval()

EnvError = _fe.EnvError
StaleError = _fe.StaleError
sha256_text = _fe.sha256_text
salient_stderr = _fe.salient_stderr
sha256_file = _fe.sha256_file

# 027-04: blessed Android provider env overrides (mirror SERVO_DESIGN_EVAL_CLAUDE_BIN).
_ADB_BIN_ENV = "SERVO_DESIGN_EVAL_ADB_BIN"
_ANDROID_SERIAL_ENV = "SERVO_DESIGN_EVAL_ANDROID_SERIAL"
# 027-05: blessed iOS provider env overrides.
_XCRUN_BIN_ENV = "SERVO_DESIGN_EVAL_XCRUN_BIN"
_IOS_UDID_ENV = "SERVO_DESIGN_EVAL_IOS_UDID"


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


def _shot_out_path(base_dir: Path, screen: dict, run_id: str | None) -> Path:
    """The retained, stamped shot path for a screen (027-01): stays DIRECTLY under
    ``shots/`` (path depth unchanged → preserves the `_judge_cli` cwd contract)."""
    stamp = run_id or _run_stamp()
    out = base_dir / "shots" / f"app-{screen['id']}-{stamp}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    return out


def _run_capture_subprocess(base_dir: Path, screen: dict, run_id: str | None,
                            command_prefix: list, *, label: str) -> tuple[Path, dict | None]:
    """Shared capture spawn for the subprocess-backed providers (web + command).

    Runs ``[*command_prefix, "--screen", <id>, "--out", <shot_path>]`` from the
    eval dir, consumes the PNG the command writes to ``--out``, and returns
    ``(png, attestation)``. One contract, two providers — the only difference is
    the leading argv (``node capture.mjs`` for web; the project command for the
    escape hatch), so retention (027-01), the `_judge_cli` cwd contract, salient
    stderr surfacing (026-01), and attestation parsing (026-03) are shared and
    identical across providers.
    """
    out = _shot_out_path(base_dir, screen, run_id)
    cmd = [*command_prefix, "--screen", screen["id"], "--out", str(out)]
    try:
        proc = subprocess.run(cmd, cwd=str(base_dir), capture_output=True, text=True, timeout=180)
    except FileNotFoundError as e:
        raise EnvError(f"{label} unavailable for capture: {e}") from e
    except subprocess.TimeoutExpired:
        raise EnvError(f"capture timed out for screen {screen['id']!r}") from None
    if proc.returncode != 0 or not out.is_file():
        # 026-01 AC4: salient-line surfacing, not a blind head slice. Applied to
        # subprocess stderr ONLY (AC4a) — the judge path at _judge_cli keeps
        # `[:200]` deliberately, since these predicates parse node's grammar.
        raise EnvError(
            f"capture failed for screen {screen['id']!r}: {salient_stderr(proc.stderr)}")
    return out, parse_attestation(proc.stdout)


def _capture_web(base_dir: Path, screen: dict, run_id: str | None = None,
                 config: dict | None = None) -> tuple[Path, dict | None]:
    """The **web** capture provider (027-02): the original Playwright path, spawning
    ``node capture.mjs``. `config` is accepted for the uniform provider signature
    and ignored — web needs nothing from it.
    """
    return _run_capture_subprocess(
        base_dir, screen, run_id,
        ["node", str(base_dir / "capture.mjs")], label="node/playwright")


def _capture_command(base_dir: Path, screen: dict, run_id: str | None = None,
                     config: dict | None = None) -> tuple[Path, dict | None]:
    """The **custom-command** capture provider (027-03): the escape hatch for any
    non-web stack. Runs the project's ``capture.command`` argv, appending
    ``--screen <id> --out <path>``. The command owns state + framing (ADR-0032
    §4/§5); servo passes only id + out and consumes the PNG. Failure fails closed
    to `EnvError`. A command that emits no ``##servo-capture:`` line is honestly
    recorded as `not_attested` (via the shared attestation parse).
    """
    command = _capture_command_argv(config or {})
    return _run_capture_subprocess(
        base_dir, screen, run_id, list(command), label="capture command")


def _capture_command_argv(config: dict) -> list:
    """The project's ``capture.command`` argv, validated. Missing / empty / non-list
    fails **closed** to `EnvError` (→ rc 2) — never a silent fall-through."""
    command = (config.get("capture") or {}).get("command")
    if not command or not isinstance(command, list):
        raise EnvError(
            "capture.transport is 'command' but capture.command is missing or empty "
            "(expected a non-empty argv list)")
    return command


# --------------------------------------------------------------------------- #
# 027-04: blessed Android provider (adb screencap + deep-link seed + stdlib crop)
# --------------------------------------------------------------------------- #

def _resolve_adb() -> str:
    """The ``adb`` path: explicit ``SERVO_DESIGN_EVAL_ADB_BIN`` override, else PATH.
    Absent → fail closed (`EnvError`)."""
    adb = os.environ.get(_ADB_BIN_ENV) or shutil.which("adb")
    if not adb:
        raise EnvError(
            "`adb` not found — the Android capture provider needs the Android "
            "platform-tools. Install them, or set SERVO_DESIGN_EVAL_ADB_BIN.")
    return adb


def _android_cfg(config: dict) -> dict:
    return ((config or {}).get("capture") or {}).get("android") or {}


def _resolve_android_serial(config: dict) -> str:
    """Resolve a CONCRETE device serial, precedence: ``capture.android.serial`` →
    ``SERVO_DESIGN_EVAL_ANDROID_SERIAL`` → the single connected device. No device,
    or an ambiguous multi-device set with no serial, fails closed to `EnvError`."""
    serial = _android_cfg(config).get("serial") or os.environ.get(_ANDROID_SERIAL_ENV)
    if serial:
        return serial
    adb = _resolve_adb()
    try:
        proc = subprocess.run([adb, "devices"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as e:
        raise EnvError(f"`adb devices` failed: {e}") from e
    # Lines after the header: "<serial>\t<state>"; count only ready devices.
    devices = []
    for line in (proc.stdout or "").splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            devices.append(parts[0])
    if not devices:
        raise EnvError(
            "no Android device/emulator connected (`adb devices` shows none ready) "
            "— boot one, or set capture.android.serial / SERVO_DESIGN_EVAL_ANDROID_SERIAL")
    if len(devices) > 1:
        raise EnvError(
            f"multiple Android devices connected ({', '.join(devices)}); set "
            "capture.android.serial or SERVO_DESIGN_EVAL_ANDROID_SERIAL to pick one")
    return devices[0]


def _android_screencap_argv(config: dict) -> list:
    """The resolved screencap argv (device identity for the ledger). Also the
    up-front fail-closed check: `adb` present + a concrete device resolvable."""
    return [_resolve_adb(), "-s", _resolve_android_serial(config),
            "exec-out", "screencap", "-p"]


def _crop_insets(crop: dict | None, *, where: str = "crop") -> dict:
    """Validate + coerce a ``{top,bottom,left,right}`` crop block to ints (shared by
    the native providers). A non-integer inset fails closed to `EnvError`; ``where``
    names the config path for a clear message (e.g. ``capture.android.crop``)."""
    crop = crop or {}
    insets = {}
    for k in ("top", "bottom", "left", "right"):
        v = crop.get(k, 0)
        try:
            insets[k] = int(v)
        except (TypeError, ValueError) as e:
            raise EnvError(f"{where}.{k} must be an integer, got {v!r}") from e
    return insets


def _capture_android(base_dir: Path, screen: dict, run_id: str | None = None,
                     config: dict | None = None) -> tuple[Path, dict | None]:
    """The **Android** capture provider (027-04): `adb exec-out screencap` for
    pixels, an optional per-screen deep-link seed, and a stdlib crop of the device
    chrome to the reference frame. Any failure fails closed to `EnvError`. adb
    emits no ``##servo-capture:`` line, so provenance is honestly `not_attested`.
    """
    config = config or {}
    adb = _resolve_adb()
    serial = _resolve_android_serial(config)
    # Optional deep-link state seed (the common declarative case; complex flows
    # use the `command` provider).
    deeplink = screen.get("deeplink")
    if deeplink:
        try:
            proc = subprocess.run(
                [adb, "-s", serial, "shell", "am", "start", "-a",
                 "android.intent.action.VIEW", "-d", deeplink],
                capture_output=True, text=True, timeout=60)
        except (OSError, subprocess.SubprocessError) as e:
            raise EnvError(f"adb deep-link failed for screen {screen['id']!r}: {e}") from e
        if proc.returncode != 0:
            raise EnvError(
                f"adb deep-link failed for screen {screen['id']!r}: "
                f"{salient_stderr(proc.stderr)}")
        time.sleep(2)  # bounded settle before the shot
    # Screencap (binary PNG on stdout → capture bytes, not text).
    try:
        proc = subprocess.run(
            [adb, "-s", serial, "exec-out", "screencap", "-p"],
            capture_output=True, timeout=180)
    except FileNotFoundError as e:
        raise EnvError(f"adb unavailable for capture: {e}") from e
    except subprocess.TimeoutExpired:
        raise EnvError(f"android screencap timed out for screen {screen['id']!r}") from None
    if proc.returncode != 0 or not proc.stdout:
        err = salient_stderr(proc.stderr.decode("utf-8", "replace") if proc.stderr else "")
        raise EnvError(f"android screencap failed for screen {screen['id']!r}: {err}")
    # Chrome-frame normalization (stdlib crop). An out-of-bounds crop fails closed.
    pc = _pngcrop()
    try:
        cropped = pc.crop_png(
            proc.stdout, **_crop_insets(_android_cfg(config).get("crop"),
                                        where="capture.android.crop"))
    except pc.PngCropError as e:
        raise EnvError(f"android frame crop failed for screen {screen['id']!r}: {e}") from e
    out = _shot_out_path(base_dir, screen, run_id)
    out.write_bytes(cropped)
    return out, None  # no attestation channel from adb → not_attested


# --------------------------------------------------------------------------- #
# 027-05: blessed iOS provider (xcrun simctl screenshot + openurl seed + crop)
# --------------------------------------------------------------------------- #

def _resolve_xcrun() -> str:
    """The ``xcrun`` path: ``SERVO_DESIGN_EVAL_XCRUN_BIN`` override, else PATH.
    Absent → fail closed (`EnvError`)."""
    xcrun = os.environ.get(_XCRUN_BIN_ENV) or shutil.which("xcrun")
    if not xcrun:
        raise EnvError(
            "`xcrun` not found — the iOS capture provider needs Xcode's command-line "
            "tools (simctl). Install Xcode, or set SERVO_DESIGN_EVAL_XCRUN_BIN.")
    return xcrun


def _ios_cfg(config: dict) -> dict:
    return ((config or {}).get("capture") or {}).get("ios") or {}


def _resolve_ios_target(config: dict) -> str:
    """The simulator target, precedence: ``capture.ios.udid`` →
    ``SERVO_DESIGN_EVAL_IOS_UDID`` → the literal ``"booted"`` (simctl's
    single-booted-device selector; simctl itself fails closed if none/ambiguous)."""
    return _ios_cfg(config).get("udid") or os.environ.get(_IOS_UDID_ENV) or "booted"


def _ios_screenshot_argv(config: dict) -> list:
    """The resolved screenshot argv WITHOUT the per-screen out path (device
    identity for the ledger). Also the up-front fail-closed check: `xcrun` present.
    The per-screen call appends the shot path."""
    return [_resolve_xcrun(), "simctl", "io", _resolve_ios_target(config), "screenshot"]


def _capture_ios(base_dir: Path, screen: dict, run_id: str | None = None,
                 config: dict | None = None) -> tuple[Path, dict | None]:
    """The **iOS** capture provider (027-05): `xcrun simctl io <target> screenshot`
    writes a PNG to a FILE (unlike adb's stdout), an optional per-screen
    `simctl openurl` seed, then the shared stdlib crop applied in place. Any
    failure fails closed to `EnvError`. simctl emits no ``##servo-capture:`` line,
    so provenance is honestly `not_attested`.
    """
    config = config or {}
    xcrun = _resolve_xcrun()
    target = _resolve_ios_target(config)
    deeplink = screen.get("deeplink")
    if deeplink:
        try:
            proc = subprocess.run([xcrun, "simctl", "openurl", target, deeplink],
                                  capture_output=True, text=True, timeout=60)
        except (OSError, subprocess.SubprocessError) as e:
            raise EnvError(f"simctl openurl failed for screen {screen['id']!r}: {e}") from e
        if proc.returncode != 0:
            raise EnvError(
                f"simctl openurl failed for screen {screen['id']!r}: "
                f"{salient_stderr(proc.stderr)}")
        time.sleep(2)  # bounded settle before the shot
    out = _shot_out_path(base_dir, screen, run_id)
    try:
        proc = subprocess.run([xcrun, "simctl", "io", target, "screenshot", str(out)],
                              capture_output=True, text=True, timeout=180)
    except FileNotFoundError as e:
        raise EnvError(f"xcrun unavailable for capture: {e}") from e
    except subprocess.TimeoutExpired:
        raise EnvError(f"ios screenshot timed out for screen {screen['id']!r}") from None
    if proc.returncode != 0:
        raise EnvError(
            f"ios screenshot failed for screen {screen['id']!r}: {salient_stderr(proc.stderr)}")
    if not out.is_file():
        # rc 0 but simctl wrote nothing — a distinct, cause-naming message (its
        # stderr is empty here, so the generic "failed: <stderr>" would be blank).
        raise EnvError(f"ios screenshot produced no output file for screen {screen['id']!r}")
    # Chrome-frame normalization (stdlib crop, in place). Out-of-bounds fails closed.
    pc = _pngcrop()
    try:
        cropped = pc.crop_png(out.read_bytes(),
                              **_crop_insets(_ios_cfg(config).get("crop"),
                                             where="capture.ios.crop"))
    except pc.PngCropError as e:
        raise EnvError(f"ios frame crop failed for screen {screen['id']!r}: {e}") from e
    out.write_bytes(cropped)
    return out, None  # no attestation channel from simctl → not_attested


# --------------------------------------------------------------------------- #
# 029-01: manual human-supplied capture provider (ADR-0035). For non-automatable
# targets (an in-game overlay, a Windows-only plugin on a Mac host) there is no
# command that drives + shoots the app — the only real capture is a human staging
# a screenshot. This provider consumes that staged PNG. It does NOT drive or shoot;
# state-seeding and framing are the human's job (like the `command` provider). The
# doctored-image residual is inherent and NOT closed (ADR-0035 §6) — the honesty
# gain over the fake-scores hook is a real, retained, hashed image plus a loud
# stderr advisory on every run (masquerade-prevention, not doctoring-detection).
# --------------------------------------------------------------------------- #

_MANUAL_PROVENANCE = "manual_capture"  # 029-01: distinct ledger provenance token
_PNG_MAGIC = b"\x89PNG"


def _manual_staged_path(base_dir: Path, screen: dict) -> Path:
    """The staged-shot path a human places the screenshot at (029-01 DoR: fixed
    convention ``manual/<screen-id>.png`` under the eval dir — discoverable next to
    ``refs/`` and ``shots/``; no template knob in v1)."""
    return base_dir / "manual" / f"{screen['id']}.png"


def _capture_manual(base_dir: Path, screen: dict, run_id: str | None = None,
                    config: dict | None = None) -> tuple[Path, dict | None]:
    """The **manual** capture provider (029-01 / ADR-0035): consume the PNG a human
    staged at ``manual/<screen-id>.png``, optionally chrome-crop it, retain it as
    this run's shot, and return it with a ``manual_capture`` attestation carrying
    the input's sha256 + mtime (the audit trail). Absent / unreadable / non-PNG
    input fails **closed** to `EnvError` — never a silent 0.0, never a fall-through.
    """
    config = config or {}
    staged = _manual_staged_path(base_dir, screen)
    if not staged.is_file():
        raise EnvError(
            f"manual capture: no staged shot for screen {screen['id']!r} at "
            f"{staged.relative_to(base_dir).as_posix()} — stage the screenshot there "
            "(capture.transport is 'manual'; servo does not capture it for you).")
    data = staged.read_bytes()
    if not data.startswith(_PNG_MAGIC):
        raise EnvError(
            f"manual capture: staged shot for screen {screen['id']!r} is not a PNG "
            f"({staged.relative_to(base_dir).as_posix()}).")
    # Attest the input the HUMAN SUPPLIED (AC3): hash it once, here, BEFORE any crop
    # — one read (no double-read / TOCTOU), and `manual_sha256` names the bytes the
    # human staged, not the retained shot. When `capture.manual.crop` is set the
    # retained/judged shot below is the cropped derivative, so the hash and the shot
    # legitimately differ; `source` links the ledger row back to the staged input.
    att = {
        "provenance": _MANUAL_PROVENANCE,
        "sha256": hashlib.sha256(data).hexdigest(),
        "mtime": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(staged.stat().st_mtime)),
        "source": staged.relative_to(base_dir).as_posix(),
    }
    # Optional chrome-crop (parallels the native providers). Only when configured,
    # so a plain already-framed screenshot needs no pngcrop sibling.
    crop = ((config.get("capture") or {}).get("manual") or {}).get("crop")
    if crop:
        pc = _pngcrop()
        try:
            data = pc.crop_png(data, **_crop_insets(crop, where="capture.manual.crop"))
        except pc.PngCropError as e:
            raise EnvError(
                f"manual frame crop failed for screen {screen['id']!r}: {e}") from e
    out = _shot_out_path(base_dir, screen, run_id)
    out.write_bytes(data)   # retained shot = the bytes actually judged (cropped when set)
    return out, att


# 027-02: the capture-provider seam. Each provider is invoked per screen as
# ``fn(base_dir, screen, run_id, config)`` and returns (png, attestation).
# 027-03 adds `command`; 027-04 adds `android`; 027-05 adds `ios`; 029-01 adds
# `manual`, all without touching the scoring path. Web is the default.
_CAPTURE_PROVIDERS = {
    "web": _capture_web,
    "command": _capture_command,
    "android": _capture_android,
    "ios": _capture_ios,
    "manual": _capture_manual,
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
                provider: str = _DEFAULT_CAPTURE_TRANSPORT,
                config: dict | None = None) -> tuple[Path, dict | None]:
    """Screenshot the app at the screen's seeded state; return (png, attestation).

    027-02: dispatches to the selected capture provider. `provider` defaults to
    ``"web"`` so the standalone callers (and tests) that pass only
    ``(base_dir, screen[, run_id])`` keep the original behaviour. An unknown
    provider fails **closed** to `EnvError` (→ rc 2 env_error) — never a silent
    fall-through to web. 027-03: `config` is threaded to providers that need it
    (the command provider reads ``capture.command``); web ignores it.
    """
    fn = _CAPTURE_PROVIDERS.get(provider)
    if fn is None:
        known = ", ".join(sorted(_CAPTURE_PROVIDERS))
        raise EnvError(f"unknown capture provider {provider!r} (known: {known})")
    return fn(base_dir, screen, run_id, config)


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
    capture_command = None
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
        # 027-03 AC3: for the command provider, validate `capture.command` up front
        # (missing/empty → env_error before any capture), and capture its identity
        # for the ledger (AC4).
        if provider == "command":
            capture_command = _capture_command_argv(config)
        # 027-04 AC1/AC4: for android, resolve adb + a concrete device ONCE up front
        # (absent/ambiguous → env_error before any capture). Pin the resolved serial
        # into the in-memory config so the per-screen provider reuses it (no N+1
        # `adb devices` queries) and record the screencap argv as the ledger identity.
        elif provider == "android":
            serial = _resolve_android_serial(config)
            config.setdefault("capture", {}).setdefault("android", {})["serial"] = serial
            capture_command = _android_screencap_argv(config)
        # 027-05 AC1/AC4: for ios, validate xcrun up front and record the resolved
        # screenshot argv as the ledger identity. (Device readiness is checked by
        # simctl at capture time — the "booted" selector fails closed there.)
        elif provider == "ios":
            capture_command = _ios_screenshot_argv(config)
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
            app_png, attestation = capture_app(base_dir, screen, run_id, provider, config)
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
            fake_run=fake is not None, provider=provider, capture_command=capture_command)
    composite = max(0.0, min(1.0, composite))
    _emit_honesty_advisories(config, composite, fake_run=fake is not None,
                             provider=provider, per_screen=per_screen)
    return composite


def _emit_honesty_advisories(config: dict, composite: float, *, fake_run: bool,
                             provider: str | None = None, per_screen=None) -> None:
    """Operator-facing warnings on **stderr** (never stdout — oracle.sh parses
    stdout as the single composite float, ``score="$(score_design_fidelity)"``).
    These facts are in ``ledger.jsonl`` too, but the ledger is not surfaced in a
    loop / CI / Routine log; stderr is — so a synthetic or coin-flip run stops
    reading as a clean measurement at the point a human actually looks.

    Two advisories:
    - **fake-scores** (field-report point 4): a ``SERVO_DESIGN_EVAL_FAKE_SCORES``
      run is byte-identical on stdout to a real one; the only prior tell was
      ``provenance: not_captured`` buried in the ledger.
    - **within-noise-of-threshold** (point 5): ``0.7998`` vs ``0.80`` presents as
      a decisive fail but is a coin flip; ``δ`` (already frozen) is exactly the
      band width that makes it a tie.
    """
    if fake_run:
        print(
            "design-eval: FAKE SCORES — SERVO_DESIGN_EVAL_FAKE_SCORES is set; no "
            "capture and no judge ran. The composite is INJECTED, not a "
            "measurement (ledger provenance: not_captured).",
            file=sys.stderr)
    # 029-01 (ADR-0035 §3): a MANUAL run's tell lives in the loud channel humans
    # read (stderr), not only the ledger — per screen, naming the sha256 of the
    # image the human supplied. Masquerade-prevention (this is not servo-captured),
    # NOT doctoring-detection — nothing can flag a doctored image as fabricated.
    if provider == "manual" and per_screen:
        for s, _samp, _lb, att, _shot in per_screen:
            sha = (att or {}).get("sha256") or "unknown"
            print(
                f"design-eval: MANUAL CAPTURE — the shot for screen {s['id']!r} was "
                f"human-supplied (sha256 {sha[:12]}…), not captured by servo; the "
                "score reflects whatever image was staged.",
                file=sys.stderr)
    threshold = config.get("threshold")
    delta = (config.get("samples") or {}).get("delta")
    if threshold is not None and delta:
        try:
            near = abs(float(composite) - float(threshold)) < float(delta)
        except (TypeError, ValueError):
            near = False   # a non-numeric threshold/δ is a config problem, not ours to raise here
        if near:
            print(
                f"design-eval: composite {composite:.4f} is within noise "
                f"(δ={delta}) of threshold {threshold} — a statistical tie, not "
                "a decisive pass/fail. Do not read the verdict as settled.",
                file=sys.stderr)


def _provenance(att, *, fake_run: bool) -> dict:
    """Reason tokens, not a bare "unknown" (026-03 AC5): `not_captured` (no
    browser ran — the fake-scores path still writes a row) must stay
    distinguishable from `not_attested` (capture happened, identity
    unavailable), because the remedies differ."""
    base = {"engine": None, "engine_version": None, "capture_transport": None,
            "provenance": None, "provenance_error": None}
    if att is not None and att.get("provenance") == _MANUAL_PROVENANCE:
        # 029-01 (ADR-0035): a human-staged shot. Distinct from `attested` (servo
        # captured it) and from `not_captured`/`not_attested`; carries the input
        # sha256 + mtime + source so a later auditor can open exactly what scored.
        return {**base, "provenance": _MANUAL_PROVENANCE,
                "manual_sha256": att.get("sha256"), "manual_mtime": att.get("mtime"),
                "manual_source": att.get("source")}
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
            *, fake_run: bool, provider: str | None, capture_command: list | None) -> None:
    # `fake_run` is keyword-only and REQUIRED on purpose: a default would let a
    # future caller silently get `not_attested` on a synthetic run — the same
    # class of error as deriving it from `att`, which this replaced. `provider`
    # and `capture_command` are likewise required keyword-only (027-02/03).
    record = {
        "at": _fe.iso_now(),
        "model": config["judge"]["model"],
        "transport": (config.get("judge") or {}).get("transport", "api"),
        # 027-02 AC5: which capture provider produced this run's shots — advisory,
        # never hashed (ADR-0032 §6). `null` on the fake arm (no capture ran).
        "capture_provider": provider,
        # 027-03 AC4: the resolved custom-command argv (identity), for the command
        # provider only; `null` otherwise. Advisory, never hashed.
        "capture_command": capture_command,
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
