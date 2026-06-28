#!/usr/bin/env python3
"""
servo edd-suitability — slice 015-01 (verdict-contract).

The first step of Servo Compile: decide whether an engineering spec is suitable
for Evaluation-Driven Development, emitting the ADR-0015 **suitability verdict** —
a closed three-state gate (`suitable` / `needs_evidence` / `unsuitable`), not a
score.

Usage
-----
    python3 suitability.py analyze <target> --spec <spec-path>

Reads the target's detected signals (`<target>/.servo/install.json`, from spec
001) and the spec's AC classification (via spec 006's `oracle_plan.py classify`,
subprocessed — the established servo idiom, never imported), runs a deterministic
ordered rule table, and writes the verdict to
`<target>/.servo/suitability/<spec-id>.json` (atomic).

Design — deterministic in v1
----------------------------
The verdict is a pure, ordered, first-match rule table over three inputs: the
target's test/CI signal, and the count of evaluable vs residual-judgment ACs.
No clock / network / randomness enters the decision, so the verdict is
reproducible. ADR-0015's optional model-assisted pass is a documented extension
point (spec 015-04), not built here.

Exit codes (ADR-0002 closed contract)
-------------------------------------
    0  verdict emitted (including a non-`suitable` verdict — that is a
       successful analysis, not an error)
    2  environment error (missing spec / missing-or-malformed manifest /
       unreadable classification); a structured reason is printed to stderr and
       no artifact is written.

Never exits 1; never leaves a torn artifact.
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 1

# Subprocess seam for spec 006's classifier. Defaults to the sibling skill path
# (mirrors heartbeat.py's GATE_PY_PATH idiom); the SERVO_* env override is the
# established test hook so a test injects a deterministic stand-in.
ORACLE_PLAN_ENV = "SERVO_SUITABILITY_ORACLE_PLAN"
DEFAULT_ORACLE_PLAN = (
    Path(__file__).resolve().parent.parent / "spec-oracle" / "oracle_plan.py"
)

# Only tests / CI count as a compilable "oracle signal" in v1. Lint alone is a
# weak code-quality signal — not sufficient on its own to call work EDD-evaluable
# (it surfaces as a missing_evidence item in 015-02 instead).
_SIGNAL_KEYS = ("tests", "ci")


class EnvError(Exception):
    """An environment error mapped to a closed `reason` + exit 2."""

    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason


def iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Decision — pure, deterministic, ordered first-match rule table
# ---------------------------------------------------------------------------

def decide(signals: dict, *, n_evaluable: int, n_residual: int) -> dict:
    """Return ``{"verdict": ..., "reasons": [{"code", "message"}]}``.

    Pure: no IO, no clock. The only `suitable` path requires BOTH an evaluable
    AC and a compilable signal; everything else is fail-closed (a non-`suitable`
    verdict). The table is ordered and first-match — exactly one rule fires and
    names itself in `reasons`.
    """
    has_signal = any(bool(signals.get(k)) for k in _SIGNAL_KEYS)
    facts = (
        f"{n_evaluable} evaluable AC(s), {n_residual} residual AC(s), "
        f"{'a test/CI signal' if has_signal else 'no test/CI signal'}"
    )

    # (predicate, verdict, code, message) — ordered, first match wins. The final
    # rule's predicate is True: the fail-closed catch-all (ADR-0015).
    rules = [
        (
            n_evaluable >= 1 and has_signal,
            "suitable",
            "evaluable_acs_with_signal",
            "EDD-shaped: evaluable ACs and a compilable test/CI signal are both "
            "present",
        ),
        (
            n_evaluable >= 1 and not has_signal,
            "needs_evidence",
            "evaluable_acs_no_signal",
            "evaluable ACs exist but there is no test/CI signal to compile an "
            "oracle against",
        ),
        (
            n_evaluable == 0 and has_signal,
            "needs_evidence",
            "signal_without_evaluable_acs",
            "a test/CI signal exists but no evaluable ACs to gate on",
        ),
        (
            n_evaluable == 0 and n_residual >= 1 and not has_signal,
            "unsuitable",
            "all_acs_residual_no_signal",
            "every AC is residual judgment and there is no signal: success is "
            "irreducibly human taste, not EDD-shaped",
        ),
        (
            True,
            "needs_evidence",
            "no_evidence_no_acs",
            "no evaluable ACs and no signal: write testable ACs and add a "
            "test/CI signal, then re-analyze",
        ),
    ]

    for matched, verdict, code, message in rules:
        if matched:
            return {
                "verdict": verdict,
                "reasons": [{"code": code, "message": f"{message} ({facts})"}],
            }
    # Unreachable: the last rule's predicate is True.
    raise AssertionError("rule table is not exhaustive")  # pragma: no cover


# ---------------------------------------------------------------------------
# Inputs — signals (001) + AC classification (006)
# ---------------------------------------------------------------------------

def _load_signals(target: Path) -> dict:
    """Read `<target>/.servo/install.json` → its `signals` object."""
    manifest = target / ".servo" / "install.json"
    if not manifest.is_file():
        raise EnvError(
            "manifest_missing",
            f".servo/install.json not found at {target}; "
            "run /servo:scaffold-init first",
        )
    try:
        data = json.loads(manifest.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        raise EnvError(
            "manifest_malformed", f".servo/install.json is not valid JSON: {exc}"
        ) from exc
    signals = data.get("signals")
    if not isinstance(signals, dict):
        raise EnvError(
            "manifest_malformed",
            ".servo/install.json has no 'signals' object",
        )
    return signals


def _classify(spec_path: Path, oracle_plan_path: Path) -> dict:
    """Obtain the 006 AC classification for `spec_path` via subprocess.

    Returns the plan payload (with `checks` + `residual_judgment`). Raises
    EnvError(`spec_missing`) / EnvError(`plan_unreadable`).
    """
    if not spec_path.is_file():
        raise EnvError("spec_missing", f"spec not found: {spec_path}")
    try:
        proc = subprocess.run(
            [sys.executable, str(oracle_plan_path), "classify", str(spec_path)],
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        raise EnvError(
            "plan_unreadable", f"could not run oracle_plan classify: {exc}"
        ) from exc
    if proc.returncode != 0:
        raise EnvError(
            "plan_unreadable",
            f"oracle_plan classify exited {proc.returncode}: "
            f"{proc.stderr.strip()}",
        )
    try:
        plan = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise EnvError(
            "plan_unreadable",
            f"oracle_plan classify emitted unparseable output: {exc}",
        ) from exc
    if not isinstance(plan, dict) or "checks" not in plan \
            or "residual_judgment" not in plan:
        raise EnvError(
            "plan_unreadable",
            "oracle_plan classify output missing checks / residual_judgment",
        )
    return plan


# ---------------------------------------------------------------------------
# Analysis + persistence
# ---------------------------------------------------------------------------

def analyze(target: Path, spec_path: Path, *, oracle_plan_path: Path) -> tuple:
    """Run the analysis. Returns ``(spec_id, artifact_dict)``.

    Raises EnvError before any artifact is written (the caller persists only on
    success, so a failed analysis never leaves a torn artifact).
    """
    signals = _load_signals(target)
    plan = _classify(spec_path, oracle_plan_path)
    n_evaluable = len(plan.get("checks", []))
    n_residual = len(plan.get("residual_judgment", []))
    spec_id = plan.get("spec_id") or spec_path.parent.name

    decision = decide(signals, n_evaluable=n_evaluable, n_residual=n_residual)

    artifact = {
        "schema_version": SCHEMA_VERSION,
        "verdict": decision["verdict"],
        "reasons": decision["reasons"],
        # Reserved here (always empty); populated by slice 015-02.
        "missing_evidence": [],
        "spec_id": spec_id,
        "analyzed_at": iso_now(),
        # Echoed inputs for auditability / the 015-04 `--explain` view.
        "inputs": {
            "signals": {
                k: signals.get(k) for k in ("tests", "lint", "ci", "language")
            },
            "ac_counts": {"evaluable": n_evaluable, "residual": n_residual},
        },
    }
    return spec_id, artifact


def write_artifact(target: Path, spec_id: str, artifact: dict) -> Path:
    """Atomically write the verdict artifact; return its path."""
    out_dir = target / ".servo" / "suitability"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{spec_id}.json"
    tmp = out_dir / f".{spec_id}.json.tmp"
    tmp.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
    os.replace(tmp, out_path)
    return out_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _run_analyze(args: argparse.Namespace) -> int:
    target = Path(args.target).resolve()
    spec_path = Path(args.spec).resolve()
    oracle_plan_path = Path(
        os.environ.get(ORACLE_PLAN_ENV) or DEFAULT_ORACLE_PLAN
    )

    try:
        spec_id, artifact = analyze(
            target, spec_path, oracle_plan_path=oracle_plan_path
        )
    except EnvError as exc:
        print(f"servo: {exc.reason}: {exc}", file=sys.stderr)
        return 2

    out_path = write_artifact(target, spec_id, artifact)
    print(
        f"servo: suitability verdict for {spec_id}: "
        f"{artifact['verdict']} -> {out_path}"
    )
    return 0


def main(argv: list | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="suitability.py",
        description="servo edd-suitability — the ADR-0015 suitability gate.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    analyze_p = sub.add_parser(
        "analyze", help="emit the ADR-0015 suitability verdict for a spec"
    )
    analyze_p.add_argument("target", help="target project directory")
    analyze_p.add_argument(
        "--spec", dest="spec", required=True, help="path to the spec.md to judge"
    )

    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    if args.command == "analyze":
        return _run_analyze(args)
    parser.error(f"unknown command: {args.command}")  # pragma: no cover
    return 2  # pragma: no cover


if __name__ == "__main__":
    sys.exit(main())
