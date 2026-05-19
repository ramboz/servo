"""
servo agent-loop — slice 003-01

Headless iteration driver. Subprocesses `claude -p --output-format json`
against a target N times under guardrails, and uses `gate.py --json`
(spec 002) as the truth-source after each iteration. Halts on (a) oracle
pass (composite ≥ threshold), or (b) iteration cap reached.

Usage:
    python3 loop.py <target> --prompt "<text>"
    python3 loop.py <target> --prompt "<text>" --max-iterations 3

Per-iteration JSON: one line per completed iteration on stdout.
Summary line: one JSON line on stdout after the last iteration (or refusal).

Spike-shape slice. Cost ceiling, context-fill gate, checkpoint/resume,
and stuck-loop detection land in 003-02..05 — this slice validates the
loop-driver-subprocesses-claude-code assumption end-to-end.

Reads/writes nothing to disk in 003-01. The `<target>/.servo/runs/<run-id>/`
directory is reserved (per ADR-0004) and the run-id appears in the summary
line, but the state file lands in slice 003-04.
"""

import argparse
import json
import os
import secrets
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# Schema version for every JSON line emitted on stdout. Mirrors gate.py's
# `schema_version` (ADR-0002) and ADR-0004's `state_schema_version`. Bump
# on any field rename, type change, or semantic shift; pure additive changes
# MAY keep version=1. Old consumers can refuse loudly on mismatch rather
# than silently mis-decoding fields they don't recognize.
SCHEMA_VERSION = 1

# Closed exit-code contract aligned with gate.py (ADR-0002):
#   0 — loop terminated normally (oracle pass or iteration cap)
#   2 — env error (preflight refusal, claude invocation failure)
# 003-01 never exits 1; below-threshold scoring drives more iterations, not
# a non-zero loop exit. 1 is reserved should a later slice find a use for it.
EXIT_OK = 0
EXIT_ENV_ERROR = 2

# Default iteration cap (per docs/architecture.md "Project vs servo-core split").
DEFAULT_MAX_ITERATIONS = 5

# Default per-invocation wall-clock cap for `claude -p`. 30 minutes is a
# generous upper bound — long enough for substantial agentic turns with
# tool use, short enough that an unattended loop won't hang for days if
# claude wedges. Tunable via the SERVO_CLAUDE_TIMEOUT env var (0 disables).
# Flagged in `docs/refinement-todo.md` for tuning with real-world data.
DEFAULT_CLAUDE_TIMEOUT_SECONDS = 1800

# Env var override for the per-invocation claude timeout. `0` disables the
# bound; malformed values fall back to DEFAULT_CLAUDE_TIMEOUT_SECONDS with a
# stderr breadcrumb. Mirrors gate.py's SERVO_GATE_TIMEOUT pattern.
_CLAUDE_TIMEOUT_ENV_VAR = "SERVO_CLAUDE_TIMEOUT"

# Status taxonomy for the summary line's `final_oracle_status`. Mirrors the
# gate.py status strings so consumers can pivot on the same values across
# both per-iteration and summary lines.
STATUS_PASS = "pass"
STATUS_BELOW_THRESHOLD = "below_threshold"
STATUS_ENV_ERROR = "env_error"

# Terminal-reason taxonomy emitted by 003-01. Slices 003-02..05 will extend
# this set (cost_ceiling_reached, context_full, oracle_plateau, interrupted,
# state_schema_mismatch, claude_version_mismatch, run_id_collision,
# verdict_schema_mismatch). Keep the strings stable — they are part of the
# loop's structured-output contract.
REASON_ORACLE_PASSED = "oracle_passed"
REASON_MAX_ITERATIONS_REACHED = "max_iterations_reached"
REASON_CLAUDE_INVOCATION_FAILED = "claude_invocation_failed"
REASON_GATE_INVOCATION_FAILED = "gate_invocation_failed"
REASON_TARGET_MISSING = "target_missing"
REASON_TARGET_NOT_DIRECTORY = "target_not_directory"
REASON_MANIFEST_MISSING = "manifest_missing"
REASON_ORACLE_MISSING = "oracle_missing"

# gate.py lives at a sibling skill path. Resolve once at import time so a
# repeated `subprocess.run` cost stays trivial.
GATE_PATH = Path(__file__).resolve().parent.parent / "quality-gate" / "gate.py"


def _generate_run_id() -> str:
    """Run-id per ADR-0004: timestamp prefix + short random suffix.

    Shape `YYYYMMDDTHHMMSS-XXXX` (15 + 1 + 4 = 20 chars). Human-readable,
    sortable across runs without parsing, collision-resistant under spec
    005's parallel-variant scenario. Slice 003-04 lands the bounded-retry
    collision policy on `mkdir(.../runs/<run-id>/, exist_ok=False)`; 003-01
    doesn't create the directory yet, so collisions are not yet observable.
    """
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    suffix = secrets.token_hex(2)  # 4 hex chars ≈ 16 bits ≈ 65k entropy
    return f"{ts}-{suffix}"


def _emit_json(payload: dict) -> None:
    """Emit a single JSON line on stdout, flushed immediately.

    Every emission is auto-prefixed with `schema_version` (matching gate.py's
    ADR-0002 contract and ADR-0004's state-file framing) so callers can't
    forget. Per-iteration consumers (and the spec 005 race driver) are
    line-oriented; flushing makes the loop's stdout safe to pipe through
    `tee` / `jq -c` / a watching shell loop without buffering surprises.
    """
    out = {"schema_version": SCHEMA_VERSION, **payload}
    sys.stdout.write(json.dumps(out) + "\n")
    sys.stdout.flush()


def _resolve_claude_timeout() -> Optional[float]:
    """Pick the effective `claude -p` timeout in seconds. None = unbounded.

    Precedence: SERVO_CLAUDE_TIMEOUT env var → DEFAULT_CLAUDE_TIMEOUT_SECONDS.
    `0` (env var) disables the bound entirely — useful for tests or callers
    enforcing a wall-clock budget out-of-band. Malformed env var falls back
    to the default with a stderr breadcrumb. Mirrors gate.py's
    `_resolve_timeout` pattern.
    """
    env_value = os.environ.get(_CLAUDE_TIMEOUT_ENV_VAR)
    if env_value is None:
        return float(DEFAULT_CLAUDE_TIMEOUT_SECONDS)
    try:
        parsed = float(env_value)
    except ValueError:
        sys.stderr.write(
            f"loop: ignoring malformed {_CLAUDE_TIMEOUT_ENV_VAR}={env_value!r}; "
            f"using default {DEFAULT_CLAUDE_TIMEOUT_SECONDS}s\n"
        )
        return float(DEFAULT_CLAUDE_TIMEOUT_SECONDS)
    return None if parsed == 0 else parsed


def _refuse_preflight(*, run_id: str, reason: str, message: str) -> int:
    """Emit a stderr breadcrumb + a summary JSON line; return rc=2.

    No per-iteration line is emitted because preflight refusal happens
    before iteration 1 runs. The summary line still carries `run_id` so a
    caller can correlate the refusal with whatever orchestration context
    invoked the loop.
    """
    sys.stderr.write(f"loop: {message}\n")
    _emit_json({
        "terminal_reason": reason,
        "iterations_completed": 0,
        "cumulative_cost_usd": 0.0,
        "final_oracle_status": STATUS_ENV_ERROR,
        "run_id": run_id,
    })
    return EXIT_ENV_ERROR


def _preflight(target: Path, run_id: str) -> Optional[int]:
    """Validate target / manifest / oracle exist. Return rc on refusal, None on pass.

    Reason strings mirror gate.py's taxonomy (`target_missing`,
    `target_not_directory`, `manifest_missing`, `oracle_missing`) per
    AC4: the loop defers to gate.py's vocabulary so downstream consumers
    can pivot on the same strings whether they're reading gate or loop
    output. Existence-only check — malformed manifest, non-executable
    oracle, etc., surface from gate.py during iteration 1 and feed the
    per-iteration `oracle_status=env_error` rather than a loop-level
    refusal.
    """
    if not target.exists():
        return _refuse_preflight(
            run_id=run_id,
            reason=REASON_TARGET_MISSING,
            message=f"target does not exist: {target}",
        )
    if not target.is_dir():
        return _refuse_preflight(
            run_id=run_id,
            reason=REASON_TARGET_NOT_DIRECTORY,
            message=f"target is not a directory: {target}",
        )
    manifest_path = target / ".servo" / "install.json"
    if not manifest_path.exists():
        return _refuse_preflight(
            run_id=run_id,
            reason=REASON_MANIFEST_MISSING,
            message=(
                f".servo/install.json not found at {manifest_path}; "
                f"run /servo:scaffold-init first"
            ),
        )
    oracle_path = target / "oracle.sh"
    if not oracle_path.exists():
        return _refuse_preflight(
            run_id=run_id,
            reason=REASON_ORACLE_MISSING,
            message=(
                f"oracle.sh not found at {oracle_path}; "
                f"run /servo:scaffold-init first"
            ),
        )
    return None


def _invoke_claude(
    prompt: str, target: Path, *, timeout_seconds: Optional[float] = None,
) -> tuple[Optional[dict], Optional[str]]:
    """Invoke `claude -p --output-format json "<prompt>"` in the target cwd.

    Returns `(parsed_json, None)` on success or `(None, breadcrumb)` on any
    failure (AC9). The breadcrumb string is the stderr-friendly cause that
    `loop:` will prefix; tests assert against the literal text.

    `timeout_seconds=None` means unbounded (used by tests that lower the
    bound to 1s via SERVO_CLAUDE_TIMEOUT to avoid 30-minute waits). On
    `subprocess.TimeoutExpired`, Python sends SIGKILL to claude. Grandchildren
    (tool-use subprocesses) may leak; spike-shape acceptable, deferred to
    slice 003-04+ if it surfaces in practice.
    """
    cmd = ["claude", "-p", "--output-format", "json", prompt]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(target),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        # AC9-adjacent: timeout is a kind of OS-level failure. Reuse the
        # uniform `claude_invocation_failed` terminal_reason (per AC9's
        # uniformity rule) and surface the cause in the breadcrumb.
        return None, f"claude -p timed out after {timeout_seconds}s (killed)"
    except FileNotFoundError:
        # Binary not on PATH — Python's execvp raises this before the child
        # process gets a chance to run.
        return None, "claude not on PATH"
    except OSError as exc:
        return None, f"OS error invoking claude: {exc}"

    if proc.returncode != 0:
        # AC9 breadcrumb. Non-zero exit is treated uniformly as failure —
        # 003-01 doesn't pass `--max-budget-usd`, so claude shouldn't be
        # exiting non-zero except in genuine failure modes (auth, network,
        # crash). The breadcrumb keeps AC9's literal "without JSON output"
        # wording even when stdout was non-empty-but-unparseable; the
        # simplification is documented in the deviation log. Slice 003-02
        # will need to revisit when `--max-budget-usd` gets added and
        # budget-exceeded paths might surface a non-zero exit with JSON.
        return None, f"claude -p exited {proc.returncode} without JSON output"

    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        return None, f"claude JSON parse error: {exc.msg} (line {exc.lineno})"

    if not isinstance(data, dict):
        return None, "claude JSON parse error: output is not a JSON object"

    return data, None


def _invoke_gate(target: Path) -> Optional[dict]:
    """Invoke `gate.py <target> --json`. Return parsed JSON dict or None on parse failure.

    gate.py emits exactly one JSON line on stdout regardless of exit code
    (per ADR-0002). We don't pass through gate's exit code as the loop's
    exit code — the loop's exit code is governed by the iteration outcome,
    not by gate's pass/fail/env-error signal on any single iteration.
    """
    cmd = [sys.executable, str(GATE_PATH), str(target), "--json"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        # Truncate the diagnostic dump — a misbehaving gate could otherwise
        # spam megabytes into our stderr. 500 chars each is enough to ID the
        # failure shape without flooding the log.
        sys.stderr.write(
            f"loop: gate.py emitted unparseable output (rc={proc.returncode}); "
            f"stdout[:500]={proc.stdout[:500]!r} stderr[:500]={proc.stderr[:500]!r}\n"
        )
        return None


def run_loop(target: Path, *, prompt: str, max_iterations: int) -> int:
    run_id = _generate_run_id()

    rc = _preflight(target, run_id)
    if rc is not None:
        return rc

    claude_timeout_seconds = _resolve_claude_timeout()

    cumulative_cost_usd = 0.0
    iterations_completed = 0
    final_oracle_status = STATUS_ENV_ERROR
    terminal_reason = REASON_MAX_ITERATIONS_REACHED

    halted_on_pass = False
    for iteration in range(1, max_iterations + 1):
        claude_data, error = _invoke_claude(
            prompt, target, timeout_seconds=claude_timeout_seconds,
        )
        if claude_data is None:
            sys.stderr.write(f"loop: {error}\n")
            _emit_json({
                "terminal_reason": REASON_CLAUDE_INVOCATION_FAILED,
                "iterations_completed": iterations_completed,
                "cumulative_cost_usd": cumulative_cost_usd,
                "final_oracle_status": final_oracle_status,
                "run_id": run_id,
            })
            return EXIT_ENV_ERROR

        session_id = str(claude_data.get("session_id", ""))
        try:
            cost_usd = float(claude_data.get("total_cost_usd", 0.0) or 0.0)
        except (TypeError, ValueError):
            cost_usd = 0.0
        claude_terminal_reason = str(claude_data.get("terminal_reason", ""))
        cumulative_cost_usd += cost_usd

        gate_data = _invoke_gate(target)
        if gate_data is None:
            # gate.py is part of servo and shouldn't emit unparseable output
            # in practice (ADR-0002 says it always emits JSON, even on the
            # env-error path). This branch is defensive — if it fires, the
            # underlying gate.py is broken; surface as env error with a
            # distinct reason so a forensic reader can tell loop vs gate
            # vs claude apart.
            _emit_json({
                "terminal_reason": REASON_GATE_INVOCATION_FAILED,
                "iterations_completed": iterations_completed,
                "cumulative_cost_usd": cumulative_cost_usd,
                "final_oracle_status": STATUS_ENV_ERROR,
                "run_id": run_id,
            })
            return EXIT_ENV_ERROR

        oracle_exit_code = int(gate_data.get("exit_code", 2))
        oracle_status = str(gate_data.get("status", STATUS_ENV_ERROR))
        oracle_composite = gate_data.get("composite")
        oracle_threshold = gate_data.get("threshold")

        _emit_json({
            "iteration": iteration,
            "session_id": session_id,
            "cost_usd": cost_usd,
            "cumulative_cost_usd": cumulative_cost_usd,
            "terminal_reason": claude_terminal_reason,
            "oracle_exit_code": oracle_exit_code,
            "oracle_status": oracle_status,
            "oracle_composite": oracle_composite,
            "oracle_threshold": oracle_threshold,
            "run_id": run_id,
        })

        iterations_completed = iteration
        final_oracle_status = oracle_status

        if oracle_exit_code == 0:
            terminal_reason = REASON_ORACLE_PASSED
            halted_on_pass = True
            break

    if not halted_on_pass:
        terminal_reason = REASON_MAX_ITERATIONS_REACHED

    _emit_json({
        "terminal_reason": terminal_reason,
        "iterations_completed": iterations_completed,
        "cumulative_cost_usd": cumulative_cost_usd,
        "final_oracle_status": final_oracle_status,
        "run_id": run_id,
    })
    return EXIT_OK


def main(argv: Optional[list[str]] = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    parser = argparse.ArgumentParser(
        prog="loop.py",
        description=(
            "Headless iteration driver. Subprocesses `claude -p "
            "--output-format json` against a target, scores via `gate.py "
            "--json` after each iteration, halts on oracle pass or "
            "iteration cap. Per-invocation claude timeout defaults to "
            f"{DEFAULT_CLAUDE_TIMEOUT_SECONDS}s; override via "
            f"${_CLAUDE_TIMEOUT_ENV_VAR} env var (0 disables)."
        ),
    )
    parser.add_argument(
        "target",
        type=Path,
        help="Path to the servo-scaffolded target project.",
    )
    parser.add_argument(
        "--prompt",
        required=True,
        help="Seed prompt passed to claude -p on each iteration.",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=DEFAULT_MAX_ITERATIONS,
        help=(
            f"Iteration cap; loop halts when reached. "
            f"Default {DEFAULT_MAX_ITERATIONS}."
        ),
    )
    args = parser.parse_args(argv)
    if args.max_iterations < 1:
        parser.error("--max-iterations must be >= 1")
    return run_loop(
        args.target.resolve(),
        prompt=args.prompt,
        max_iterations=args.max_iterations,
    )


if __name__ == "__main__":
    sys.exit(main())
