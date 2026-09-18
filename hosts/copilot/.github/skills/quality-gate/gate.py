"""
servo quality-gate — slices 002-01 + 002-02 + 002-03 + 002-04

Runtime wrapper around the scaffolded `<target>/oracle.sh`. Locates the oracle,
runs it via subprocess (with a bounded timeout — see slice 002-04), parses its
`composite=X threshold=Y` summary, and emits a normalized line (default) or
one-line JSON (`--json`). Closed 0/1/2 exit contract per ADR-0002 (unexpected
oracle exits remap to 2 with a structured reason). Refuses to run against a
target that lacks `.servo/install.json` (spec 001's manifest — see slice
002-03).

Usage:
    python3 gate.py <target>                 # invoke: structured summary
    python3 gate.py <target> --json          # invoke: one-line JSON payload
    python3 gate.py <target> --verbose       # invoke: + re-emit oracle output
    python3 gate.py <target> --timeout 60    # invoke: bound at 60s (0 = disable)
    python3 gate.py audit <target>           # audit: human summary of install.json
    python3 gate.py audit <target> --json    # audit: install.json verbatim

Reads SERVO_GATE_TIMEOUT env var as the default timeout when no `--timeout`
flag is supplied. The flag wins on conflict (clarify Q2 + slice 002-04 DoR).

Future slices add SKILL.md surface (002-05).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
import sys
from pathlib import Path
from typing import Optional

# JSON output schema version per ADR-0002. Bump on any field rename, type
# change, or semantic shift; pure additive changes MAY keep version=1.
SCHEMA_VERSION = 1

# Closed exit-code contract per ADR-0002.
EXIT_PASS = 0
EXIT_BELOW_THRESHOLD = 1
EXIT_ENV_ERROR = 2
ALLOWED_ORACLE_EXIT_CODES = frozenset({0, 1, 2})

STATUS_PASS = "pass"
STATUS_BELOW_THRESHOLD = "below_threshold"
STATUS_ENV_ERROR = "env_error"

# Oracle stdout format from templates/oracle.sh.template:
#   printf 'oracle: composite=%s threshold=%s\n' "$composite" "$THRESHOLD"
_ORACLE_SUMMARY_RE = re.compile(
    r"oracle:\s+composite=(\S+)\s+threshold=(\S+)"
)

# Oracle stderr format on missing-components path:
#   echo "oracle: missing components: ${missing[*]}" >&2
_ORACLE_MISSING_RE = re.compile(
    r"oracle:\s+missing components:\s+(.+?)\s*$",
    re.MULTILINE,
)

# Oracle.sh `COMPONENTS=( ... )` entries are quoted `"name:weight"` pairs.
# Used by `audit` to enrich the component list with weights (best-effort).
_ORACLE_COMPONENT_ENTRY_RE = re.compile(
    r'"([A-Za-z_][A-Za-z0-9_-]*):([0-9.]+)"'
)

# Required manifest keys per spec 001-03 schema. Other keys (`servo_version`,
# `timestamp`, `signals`) are loaded if present but not required by the gate.
_MANIFEST_REQUIRED_KEYS = ("installed_tier", "components")

# Slice 002-04: default timeout for oracle invocation, in seconds. Five
# minutes — long enough for real test suites, short enough that a wedged
# subprocess is caught well before the architecture.md cost ceiling.
DEFAULT_TIMEOUT_SECONDS = 300

# Grace period between SIGTERM and SIGKILL when killing a timed-out oracle.
_KILL_GRACE_SECONDS = 5

# Env var that overrides the default timeout when `--timeout` is not supplied.
# `--timeout 0` (or `SERVO_GATE_TIMEOUT=0`) disables the timeout entirely
# (clarify Q2: 0 means "no bound").
_TIMEOUT_ENV_VAR = "SERVO_GATE_TIMEOUT"


def _parse_oracle_summary(stdout: str) -> tuple[Optional[float], Optional[float]]:
    match = _ORACLE_SUMMARY_RE.search(stdout)
    if not match:
        return None, None
    try:
        composite = float(match.group(1))
        threshold = float(match.group(2))
    except ValueError:
        return None, None
    return composite, threshold


def _parse_missing_components(stderr: str) -> list[str]:
    match = _ORACLE_MISSING_RE.search(stderr)
    if not match:
        return []
    # Oracle joins missing component names with whitespace; split on any whitespace.
    return match.group(1).split()


def _parse_component_weights(oracle_path: Path) -> dict[str, float]:
    """Best-effort parse of oracle.sh's COMPONENTS array for name:weight pairs.

    Audit uses this to enrich the human-readable component list with weights;
    the manifest only carries component names. Falls back to an empty dict
    silently — audit text mode will then omit weights for unknown components.
    Coupling deferred to refinement-todo: a future manifest extension could
    carry weights directly and obsolete this parser.
    """
    if not oracle_path.exists():
        return {}
    try:
        text = oracle_path.read_text()
    except OSError:
        return {}
    block_match = re.search(r"COMPONENTS=\((.*?)\)", text, re.DOTALL)
    if not block_match:
        return {}
    weights: dict[str, float] = {}
    for entry_match in _ORACLE_COMPONENT_ENTRY_RE.finditer(block_match.group(1)):
        name, weight = entry_match.groups()
        try:
            weights[name] = float(weight)
        except ValueError:
            continue
    return weights


def _load_manifest(target: Path) -> dict:
    """Load and validate `<target>/.servo/install.json`.

    Raises:
      FileNotFoundError — manifest absent
      ValueError        — invalid JSON or wrong top-level type
      KeyError(name)    — required key missing (`installed_tier` or `components`)
    """
    manifest_path = target / ".servo" / "install.json"
    if not manifest_path.exists():
        raise FileNotFoundError(manifest_path)
    try:
        raw = manifest_path.read_text()
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON: {exc.msg} (line {exc.lineno})") from exc
    if not isinstance(data, dict):
        raise ValueError("manifest must be a JSON object")
    for key in _MANIFEST_REQUIRED_KEYS:
        if key not in data:
            raise KeyError(key)
    return data


def _resolve_timeout(flag_value: Optional[float]) -> Optional[float]:
    """Pick the effective timeout in seconds. Returns None for unbounded.

    Precedence: `--timeout` flag → `SERVO_GATE_TIMEOUT` env var → default.
    `0` (from either source) disables the timeout (clarify Q2: 0 = no bound).
    A malformed env var falls back to the default.
    """
    if flag_value is not None:
        return None if flag_value == 0 else flag_value
    env_value = os.environ.get(_TIMEOUT_ENV_VAR)
    if env_value is not None:
        try:
            parsed = float(env_value)
        except ValueError:
            sys.stderr.write(
                f"gate: ignoring malformed {_TIMEOUT_ENV_VAR}={env_value!r}; "
                f"using default {DEFAULT_TIMEOUT_SECONDS}s\n"
            )
            return float(DEFAULT_TIMEOUT_SECONDS)
        return None if parsed == 0 else parsed
    return float(DEFAULT_TIMEOUT_SECONDS)


def _run_oracle_bounded(
    oracle: Path, target: Path, timeout_seconds: Optional[float]
) -> tuple[str, str, int, bool]:
    """Invoke oracle.sh under an optional timeout.

    Returns `(stdout, stderr, returncode, timed_out)`. On timeout:
      1. SIGTERM the oracle's process group (covers any backgrounded children).
      2. Wait up to `_KILL_GRACE_SECONDS` for graceful exit.
      3. SIGKILL the process group if still alive.
    """
    proc = subprocess.Popen(
        [str(oracle)],
        cwd=str(target),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        # New session → child is its own process-group leader; killpg targets
        # the whole tree (oracle + any backgrounded subprocesses spawned by
        # components like `pytest &`).
        start_new_session=True,
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout_seconds)
        return stdout or "", stderr or "", proc.returncode, False
    except subprocess.TimeoutExpired:
        # Phase 1: SIGTERM the whole process group.
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass
        try:
            stdout, stderr = proc.communicate(timeout=_KILL_GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            # Phase 2: SIGKILL the whole process group.
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
            stdout, stderr = proc.communicate()
        # On timeout, the caller (run_gate) emits EXIT_ENV_ERROR unconditionally;
        # the actual oracle returncode is not surfaced. Return what the OS
        # reports so the field is always populated even though it's unused.
        rc = proc.returncode if proc.returncode is not None else -1
        return stdout or "", stderr or "", rc, True


def _check_manifest(
    target: Path, *, json_mode: bool, verbose: bool
) -> tuple[int, Optional[dict]]:
    """Check manifest precondition. Returns (exit_code, manifest_or_none)."""
    manifest_path = target / ".servo" / "install.json"
    try:
        manifest = _load_manifest(target)
    except FileNotFoundError:
        return (
            _refuse(
                f".servo/install.json not found at {manifest_path}; "
                f"run /servo:scaffold-init first",
                reason="manifest_missing",
                json_mode=json_mode,
                verbose=verbose,
            ),
            None,
        )
    except ValueError as exc:
        return (
            _refuse(
                f"manifest at {manifest_path} is malformed: {exc}",
                reason="manifest_malformed",
                json_mode=json_mode,
                verbose=verbose,
            ),
            None,
        )
    except KeyError as exc:
        missing_key = exc.args[0]
        return (
            _refuse(
                f"manifest at {manifest_path} missing required key: "
                f"'{missing_key}'",
                reason="manifest_invalid_key",
                json_mode=json_mode,
                verbose=verbose,
            ),
            None,
        )
    return 0, manifest


def _format_float(value: Optional[float]) -> str:
    if value is None:
        return "null"
    # Drop trailing zeros (0.7000 → 0.7) but preserve "0.0" / "1.0".
    text = f"{value:g}"
    if "." not in text and "e" not in text:
        text = f"{value:.1f}"
    return text


def _emit_summary(
    *,
    exit_code: int,
    status: str,
    composite: Optional[float],
    threshold: Optional[float],
    missing: list[str],
    reason: Optional[str],
    code: Optional[int],
    timeout_seconds: Optional[float] = None,
    raw_stdout: str,
    raw_stderr: str,
    json_mode: bool,
    verbose: bool,
) -> None:
    """Emit the gate's structured summary on stdout, plus optional raw passthrough."""
    if json_mode:
        payload: dict = {
            "schema_version": SCHEMA_VERSION,
            "exit_code": exit_code,
            "status": status,
            "composite": composite,
            "threshold": threshold,
            "missing": missing,
        }
        if reason is not None:
            payload["reason"] = reason
        if code is not None:
            payload["code"] = code
        if timeout_seconds is not None:
            # Named to match the `--timeout` flag and SERVO_GATE_TIMEOUT env
            # var. Conveys "the timeout budget that fired", not actual wall
            # elapsed (those can diverge by up to the SIGTERM→SIGKILL grace).
            payload["timeout_seconds"] = timeout_seconds
        if verbose:
            payload["raw"] = {"stdout": raw_stdout, "stderr": raw_stderr}
        sys.stdout.write(json.dumps(payload) + "\n")
    else:
        parts = [
            "gate:",
            f"composite={_format_float(composite)}",
            f"threshold={_format_float(threshold)}",
            f"status={status}",
            f"exit={exit_code}",
        ]
        if missing:
            parts.append(f"missing={','.join(missing)}")
        if reason is not None:
            parts.append(f"reason={reason}")
        if code is not None:
            parts.append(f"code={code}")
        if timeout_seconds is not None:
            parts.append(f"timeout={_format_float(timeout_seconds)}s")
        sys.stdout.write(" ".join(parts) + "\n")
        if verbose:
            if raw_stdout:
                sys.stdout.write(raw_stdout)
                if not raw_stdout.endswith("\n"):
                    sys.stdout.write("\n")
            if raw_stderr:
                sys.stderr.write(raw_stderr)
                if not raw_stderr.endswith("\n"):
                    sys.stderr.write("\n")


def _refuse(
    message: str,
    *,
    reason: str,
    json_mode: bool,
    verbose: bool,
) -> int:
    """Print a human-readable stderr message and emit a structured env_error summary."""
    sys.stderr.write(f"gate: {message}\n")
    _emit_summary(
        exit_code=EXIT_ENV_ERROR,
        status=STATUS_ENV_ERROR,
        composite=None,
        threshold=None,
        missing=[],
        reason=reason,
        code=None,
        raw_stdout="",
        raw_stderr="",
        json_mode=json_mode,
        verbose=verbose,
    )
    return EXIT_ENV_ERROR


def run_gate(
    target: Path,
    *,
    json_mode: bool = False,
    verbose: bool = False,
    timeout_seconds: Optional[float] = None,
) -> int:
    """Invoke `<target>/oracle.sh`, parse its output, emit a structured summary."""
    if not target.exists():
        return _refuse(
            f"target does not exist: {target}",
            reason="target_missing", json_mode=json_mode, verbose=verbose,
        )
    if not target.is_dir():
        return _refuse(
            f"target is not a directory: {target}",
            reason="target_not_directory", json_mode=json_mode, verbose=verbose,
        )

    # Manifest precondition (002-03): refuse if not a servo-scaffolded install.
    rc, _manifest = _check_manifest(target, json_mode=json_mode, verbose=verbose)
    if rc != 0:
        return rc

    oracle = target / "oracle.sh"
    if not oracle.exists():
        return _refuse(
            f"oracle.sh not found at {oracle}; run /servo:scaffold-init first",
            reason="oracle_missing", json_mode=json_mode, verbose=verbose,
        )
    if not os.access(oracle, os.X_OK):
        return _refuse(
            f"oracle.sh at {oracle} is not executable; "
            f"run `chmod +x {oracle}` to recover",
            reason="oracle_not_executable", json_mode=json_mode, verbose=verbose,
        )

    try:
        raw_stdout, raw_stderr, oracle_rc, timed_out = _run_oracle_bounded(
            oracle, target, timeout_seconds
        )
    except OSError as exc:
        return _refuse(
            f"failed to invoke oracle.sh: {exc}",
            reason="invocation_failed", json_mode=json_mode, verbose=verbose,
        )

    composite, threshold = _parse_oracle_summary(raw_stdout)
    missing = _parse_missing_components(raw_stderr)

    # Slice 002-04: timeout → rc=2 with `reason=timeout timeout=<seconds>s`.
    if timed_out:
        sys.stderr.write(
            f"gate: oracle timed out after {timeout_seconds}s (killed via "
            f"SIGTERM → SIGKILL)\n"
        )
        _emit_summary(
            exit_code=EXIT_ENV_ERROR,
            status=STATUS_ENV_ERROR,
            composite=composite,
            threshold=threshold,
            missing=missing,
            reason="timeout",
            code=None,
            timeout_seconds=timeout_seconds,
            raw_stdout=raw_stdout,
            raw_stderr=raw_stderr,
            json_mode=json_mode,
            verbose=verbose,
        )
        return EXIT_ENV_ERROR

    # ADR-0002 closed contract: remap any non-{0,1,2} exit to 2.
    if oracle_rc not in ALLOWED_ORACLE_EXIT_CODES:
        sys.stderr.write(
            f"gate: oracle exited with unexpected code {oracle_rc} "
            f"(expected 0/1/2)\n"
        )
        _emit_summary(
            exit_code=EXIT_ENV_ERROR,
            status=STATUS_ENV_ERROR,
            composite=composite,
            threshold=threshold,
            missing=missing,
            reason="unexpected_exit",
            code=oracle_rc,
            raw_stdout=raw_stdout,
            raw_stderr=raw_stderr,
            json_mode=json_mode,
            verbose=verbose,
        )
        return EXIT_ENV_ERROR

    # AC #4: oracle exit 0 but no parseable summary → unparseable_oracle_output env error.
    if oracle_rc == EXIT_PASS and (composite is None or threshold is None):
        sys.stderr.write(
            "gate: oracle exited 0 but produced no parseable "
            "'composite=X threshold=Y' line\n"
        )
        # AC #4: surface the raw output on stderr so a human can diagnose
        # even without --verbose (this is the only refusal mode where the
        # raw output is the actual evidence of failure).
        if raw_stdout:
            sys.stderr.write("--- oracle stdout ---\n")
            sys.stderr.write(raw_stdout)
            if not raw_stdout.endswith("\n"):
                sys.stderr.write("\n")
        if raw_stderr:
            sys.stderr.write("--- oracle stderr ---\n")
            sys.stderr.write(raw_stderr)
            if not raw_stderr.endswith("\n"):
                sys.stderr.write("\n")
        _emit_summary(
            exit_code=EXIT_ENV_ERROR,
            status=STATUS_ENV_ERROR,
            composite=None,
            threshold=None,
            missing=missing,
            reason="unparseable_oracle_output",
            code=None,
            raw_stdout=raw_stdout,
            raw_stderr=raw_stderr,
            json_mode=json_mode,
            verbose=verbose,
        )
        return EXIT_ENV_ERROR

    # Happy paths: oracle_rc is in {0, 1, 2}.
    status = {
        EXIT_PASS: STATUS_PASS,
        EXIT_BELOW_THRESHOLD: STATUS_BELOW_THRESHOLD,
        EXIT_ENV_ERROR: STATUS_ENV_ERROR,
    }[oracle_rc]
    _emit_summary(
        exit_code=oracle_rc,
        status=status,
        composite=composite,
        threshold=threshold,
        missing=missing,
        reason=None,
        code=None,
        raw_stdout=raw_stdout,
        raw_stderr=raw_stderr,
        json_mode=json_mode,
        verbose=verbose,
    )
    return oracle_rc


def run_audit(target: Path, *, json_mode: bool = False) -> int:
    """Print the servo install manifest without invoking the oracle."""
    if not target.exists():
        return _refuse(
            f"target does not exist: {target}",
            reason="target_missing", json_mode=json_mode, verbose=False,
        )
    if not target.is_dir():
        return _refuse(
            f"target is not a directory: {target}",
            reason="target_not_directory", json_mode=json_mode, verbose=False,
        )

    rc, manifest = _check_manifest(target, json_mode=json_mode, verbose=False)
    if rc != 0:
        return rc
    assert manifest is not None  # _check_manifest returns 0 → non-None.

    if json_mode:
        # AC #4: emit manifest verbatim as JSON. One-line for shape-consistency
        # with the invocation `--json` payload (002-02 AC #2) and with the
        # refusal-mode JSON emitted by `_emit_summary`.
        sys.stdout.write(json.dumps(manifest) + "\n")
    else:
        # AC #3: human-readable summary.
        weights = _parse_component_weights(target / "oracle.sh")
        sys.stdout.write(f"servo install at {target}\n")
        sys.stdout.write(f"  tier:        {manifest.get('installed_tier', '?')}\n")
        sys.stdout.write(f"  installed:   {manifest.get('timestamp', '?')}\n")
        signals = manifest.get("signals", {})
        if isinstance(signals, dict) and signals:
            # Lowercase booleans to match JSON convention (true/false, not
            # Python's True/False). Other types stringified as-is.
            sigparts = " ".join(
                f"{k}={'true' if v is True else 'false' if v is False else v}"
                for k, v in signals.items()
            )
            sys.stdout.write(f"  signals:     {sigparts}\n")
        else:
            sys.stdout.write("  signals:     (none)\n")
        components = manifest.get("components", [])
        if components:
            sys.stdout.write(f"  components:  ({len(components)})\n")
            for name in components:
                weight = weights.get(name)
                if weight is not None:
                    sys.stdout.write(f"    - {name} (weight {weight:g})\n")
                else:
                    sys.stdout.write(f"    - {name}\n")
        else:
            sys.stdout.write("  components:  (none)\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    # Hand-rolled subcommand dispatch (mirrors scaffold.py's `detect` shape).
    # Keeps the bare `gate.py <target>` form working alongside `gate.py audit <target>`.
    if argv and argv[0] == "audit":
        audit_parser = argparse.ArgumentParser(
            prog="gate.py audit",
            description="Print the servo install manifest without invoking the oracle.",
        )
        audit_parser.add_argument(
            "target",
            type=Path,
            help="Path to the servo-scaffolded target project.",
        )
        audit_parser.add_argument(
            "--json",
            action="store_true",
            dest="json_mode",
            help="Emit the manifest verbatim as JSON instead of the human summary.",
        )
        args = audit_parser.parse_args(argv[1:])
        return run_audit(args.target.resolve(), json_mode=args.json_mode)

    parser = argparse.ArgumentParser(
        prog="gate.py",
        description=(
            "Run the scaffolded oracle.sh against a target and emit a "
            "closed-contract exit code (0 = pass, 1 = below threshold, "
            "2 = env error) with a structured stdout summary."
        ),
    )
    parser.add_argument(
        "target",
        type=Path,
        help="Path to the target project (contains oracle.sh and .servo/install.json).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_mode",
        help="Emit one-line JSON instead of the default text summary.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Re-emit the oracle's raw stdout/stderr beneath the summary.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        metavar="SECONDS",
        help=(
            "Bound the oracle's runtime in seconds. 0 disables the timeout. "
            f"Defaults to ${_TIMEOUT_ENV_VAR} env var, or "
            f"{DEFAULT_TIMEOUT_SECONDS}s if neither is set."
        ),
    )
    args = parser.parse_args(argv)
    timeout_seconds = _resolve_timeout(args.timeout)
    return run_gate(
        args.target.resolve(),
        json_mode=args.json_mode,
        verbose=args.verbose,
        timeout_seconds=timeout_seconds,
    )


if __name__ == "__main__":
    sys.exit(main())
