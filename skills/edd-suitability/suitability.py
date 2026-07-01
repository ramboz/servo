#!/usr/bin/env python3
"""
servo edd-suitability — slices 015-01 (verdict-contract) + 015-02
(missing-evidence).

The first step of Servo Compile: decide whether an engineering spec is suitable
for Evaluation-Driven Development, emitting the ADR-0015 **suitability verdict** —
a closed three-state gate (`suitable` / `needs_evidence` / `unsuitable`), not a
score. For a `needs_evidence` verdict the artifact carries an actionable
`missing_evidence` checklist keyed to a closed `kind` taxonomy (015-02).

Usage
-----
    python3 suitability.py analyze <target> --spec <spec-path> [--json] [--explain]

Default output is a concise human summary (the verdict + each blocking
`missing_evidence` item); `--json` emits the full ADR-0015 verdict JSON; and
`--explain` shows the ordered rule trace — which rules were evaluated, which
fired, and the inputs they keyed on — so a verdict is debuggable without reading
the rule-table source. The persisted artifact is always the clean ADR-0015 shape;
`--explain` adds the trace as a stdout-only view, never to the file.

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

from __future__ import annotations

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
# (it surfaces as a missing_evidence item below).
_SIGNAL_KEYS = ("tests", "ci")

# Closed `kind` taxonomy for missing_evidence items (slice 015-02), mirroring
# ADR-0002's closed-`reason` posture. An input that maps to no known kind is
# never emitted as an open string — the set is extended only by a deliberate
# schema bump. The tuple order is also the stable display order (ADR-0015
# re-runnability): items sort by (taxonomy index, detail).
MISSING_EVIDENCE_KINDS = ("tests", "lint", "ci", "oracle_signal", "reference_set")


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

def _missing_evidence(signals: dict, *, has_signal: bool,
                      n_evaluable: int) -> list:
    """Deterministic, actionable `missing_evidence` items (slice 015-02).

    Pure: no IO, no clock. Every item points at a *concrete absent input* (never
    a vague "needs more") and carries the closed `{kind, detail, blocking}`
    shape. ``blocking=True`` marks the gap that *caused* the `needs_evidence`
    verdict; ``blocking=False`` items are how-to / quality nudges. Items are
    returned in the stable order ADR-0015 requires (taxonomy index, then detail)
    so re-analysis over unchanged inputs is byte-stable.
    """
    items: list = []
    if not has_signal:
        items.append({
            "kind": "oracle_signal",
            "detail": "no test or CI signal detected in .servo/install.json; "
                      "add a test command or CI workflow so the oracle has a "
                      "deterministic gate to evaluate against",
            "blocking": True,
        })
        items.append({
            "kind": "tests",
            "detail": "no test signal detected; add a test command (e.g. a "
                      "test runner target) so the oracle has a deterministic "
                      "gate",
            "blocking": False,
        })
        items.append({
            "kind": "ci",
            "detail": "no CI signal detected; add a CI workflow that runs the "
                      "project's checks so the oracle has a reproducible gate",
            "blocking": False,
        })
    if not bool(signals.get("lint")):
        items.append({
            "kind": "lint",
            "detail": "no lint signal detected; adding one strengthens the "
                      "oracle but is not required for suitability on its own",
            "blocking": False,
        })
    if n_evaluable == 0:
        items.append({
            "kind": "reference_set",
            "detail": "no evaluable acceptance criteria detected; add at least "
                      "one deterministically-checkable AC (or a reference set) "
                      "so the oracle has something to gate on",
            "blocking": True,
        })
    kind_rank = {k: i for i, k in enumerate(MISSING_EVIDENCE_KINDS)}
    items.sort(key=lambda it: (kind_rank[it["kind"]], it["detail"]))
    return items


def _facts(n_evaluable: int, n_residual: int, has_signal: bool) -> str:
    return (
        f"{n_evaluable} evaluable AC(s), {n_residual} residual AC(s), "
        f"{'a test/CI signal' if has_signal else 'no test/CI signal'}"
    )


def _rule_table(n_evaluable: int, n_residual: int, has_signal: bool) -> list:
    """The ordered, first-match suitability rule table (ADR-0015 / 015-01).

    Returns ``[(matched, verdict, code, message), ...]``. The final rule's
    predicate is ``True`` — the fail-closed catch-all. Shared by `decide()`
    (which takes the first match) and `build_trace()` (which renders every rule
    for `--explain`), so the table is defined exactly once.
    """
    return [
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


def build_trace(signals: dict, *, n_evaluable: int, n_residual: int) -> dict:
    """Ordered rule trace for `--explain` (slice 015-04 AC3).

    Renders every rule in table order with its boolean predicate and marks the
    single rule that `decide()` would act on (`decided: true` — the first match).
    Pure; carries the inputs the rules keyed on so a verdict is debuggable
    without reading the rule-table source.
    """
    has_signal = any(bool(signals.get(k)) for k in _SIGNAL_KEYS)
    rules = _rule_table(n_evaluable, n_residual, has_signal)
    rendered = []
    decided = False
    for matched, verdict, code, _message in rules:
        is_decision = bool(matched) and not decided
        if is_decision:
            decided = True
        rendered.append({
            "code": code,
            "verdict": verdict,
            "matched": bool(matched),
            "decided": is_decision,
        })
    return {
        "inputs": {
            "n_evaluable": n_evaluable,
            "n_residual": n_residual,
            "has_signal": has_signal,
            "signals": {
                k: signals.get(k) for k in ("tests", "lint", "ci", "language")
            },
        },
        "rules": rendered,
    }


def decide(signals: dict, *, n_evaluable: int, n_residual: int) -> dict:
    """Return ``{"verdict", "reasons": [...], "missing_evidence": [...]}``.

    Pure: no IO, no clock. The only `suitable` path requires BOTH an evaluable
    AC and a compilable signal; everything else is fail-closed (a non-`suitable`
    verdict). The table is ordered and first-match — exactly one rule fires and
    names itself in `reasons`.

    The `missing_evidence` list is load-bearing only for `needs_evidence`: a
    `suitable` or `unsuitable` verdict carries an empty list (an unsuitable spec
    is not fixable by acquiring evidence). For `needs_evidence`, every blocking
    item's `kind` is also reflected back into `reasons` so the verdict and the
    list can never disagree (slice 015-02 AC3).
    """
    has_signal = any(bool(signals.get(k)) for k in _SIGNAL_KEYS)
    facts = _facts(n_evaluable, n_residual, has_signal)
    rules = _rule_table(n_evaluable, n_residual, has_signal)

    for matched, verdict, code, message in rules:
        if matched:
            reasons = [{"code": code, "message": f"{message} ({facts})"}]
            missing = (
                _missing_evidence(
                    signals, has_signal=has_signal, n_evaluable=n_evaluable
                )
                if verdict == "needs_evidence"
                else []
            )
            # Reflect each blocking gap's kind into `reasons` so a consumer
            # reading the top-level reasons sees the same gaps as the list.
            for item in missing:
                if item["blocking"]:
                    reasons.append({
                        "code": f"missing_{item['kind']}",
                        "message": item["detail"],
                    })
            return {
                "verdict": verdict,
                "reasons": reasons,
                "missing_evidence": missing,
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
        # Load-bearing for `needs_evidence`; empty for suitable/unsuitable
        # (slice 015-02).
        "missing_evidence": decision["missing_evidence"],
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
# Rendering — human summary + `--explain` rule trace (slice 015-04)
# ---------------------------------------------------------------------------

_VERDICT_HEADLINE = {
    "suitable": "SUITABLE — EDD-shaped with compilable evidence; ready to compile",
    "needs_evidence": "NEEDS_EVIDENCE — EDD-shaped but missing blocking evidence",
    "unsuitable": "UNSUITABLE — not EDD-shaped (success is human-residual)",
}


def render_human(artifact: dict, out_path: Path) -> str:
    """A concise human summary: the verdict + one line per *blocking* gap.

    Non-blocking advisory items are summarized as a count (the actionable next
    step is the blocking set). A `needs_evidence` verdict ends with the re-run
    hint ADR-0015 names.
    """
    verdict = artifact["verdict"]
    lines = [
        f"servo: {artifact['spec_id']} — "
        f"{_VERDICT_HEADLINE.get(verdict, verdict)}"
    ]
    missing = artifact.get("missing_evidence", [])
    blocking = [it for it in missing if it.get("blocking")]
    advisory = [it for it in missing if not it.get("blocking")]
    if verdict == "needs_evidence":
        for it in blocking:
            lines.append(f"  ✗ blocking [{it['kind']}] {it['detail']}")
        if advisory:
            lines.append(
                f"  · plus {len(advisory)} advisory item"
                f"{'' if len(advisory) == 1 else 's'} (run --json to see them)"
            )
        lines.append(
            "  → acquire the blocking evidence above, then re-run "
            "`analyze` — the verdict flips to `suitable` once the gaps close."
        )
    elif verdict == "unsuitable":
        for reason in artifact.get("reasons", []):
            lines.append(f"  · {reason['message']}")
        lines.append("  → route to a human / jig; this is not EDD-shaped.")
    lines.append(f"  artifact → {out_path}")
    return "\n".join(lines)


def render_trace(trace: dict) -> str:
    """Render the ordered rule trace (`--explain`) as a human-readable block."""
    inp = trace["inputs"]
    lines = [
        "  rule trace (ordered, first-match):",
        f"    inputs: evaluable={inp['n_evaluable']} residual={inp['n_residual']} "
        f"has_signal={inp['has_signal']} "
        f"(tests={inp['signals'].get('tests')} ci={inp['signals'].get('ci')} "
        f"lint={inp['signals'].get('lint')})",
    ]
    for r in trace["rules"]:
        mark = "✓ DECIDED" if r["decided"] else ("·  matched" if r["matched"]
                                                 else "   ——")
        lines.append(f"    [{mark}] {r['code']} → {r['verdict']}")
    return "\n".join(lines)


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
        # Env errors stay on stderr + exit 2 regardless of --json (no artifact,
        # no torn output) — the closed ADR-0002 contract from 015-01.
        print(f"servo: {exc.reason}: {exc}", file=sys.stderr)
        return 2

    out_path = write_artifact(target, spec_id, artifact)

    trace = None
    if args.explain:
        inputs = artifact["inputs"]["ac_counts"]
        trace = build_trace(
            artifact["inputs"]["signals"],
            n_evaluable=inputs["evaluable"],
            n_residual=inputs["residual"],
        )

    if args.json:
        # The persisted artifact stays the clean ADR-0015 shape; --explain adds
        # the trace as a stdout-only view (a superset), never to the file.
        payload = dict(artifact)
        if trace is not None:
            payload["rule_trace"] = trace
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(render_human(artifact, out_path))
        if trace is not None:
            print(render_trace(trace))
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
    analyze_p.add_argument(
        "--json", action="store_true",
        help="emit the full ADR-0015 verdict JSON (default: a human summary)",
    )
    analyze_p.add_argument(
        "--explain", action="store_true",
        help="show the ordered rule trace (which rules fired and why)",
    )

    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    if args.command == "analyze":
        return _run_analyze(args)
    parser.error(f"unknown command: {args.command}")  # pragma: no cover
    return 2  # pragma: no cover


if __name__ == "__main__":
    sys.exit(main())
